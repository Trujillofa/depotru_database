"""
Base module for AI package.

Contains configuration, security utilities, and the AIVanna base class.
"""

import inspect
import math
import os
import re
import sys
import time
import warnings
from functools import wraps
from typing import Callable, List

# Optional dotenv import
try:
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:
    pass

from vanna.legacy.chromadb.chromadb_vector import ChromaDB_VectorStore
from vanna.legacy.openai import OpenAI_Chat

try:
    from openai import OpenAI
except ImportError:
    OpenAI = None

from business_analyzer.core.query_cache import (
    MemoryQueryCache,
    SimpleQueryCache,
    create_query_cache,
)

from .circuit_breaker import CircuitBreakerError, with_circuit_breaker

# =============================================================================
# CONSTANTS
# =============================================================================

# Maximum stack depth to search for test file indicators (safety limit)
MAX_STACK_FRAME_DEPTH = 20

# Supported AI providers
SUPPORTED_PROVIDERS = ["grok", "openai", "anthropic", "ollama"]
DEFAULT_PROVIDER = "grok"


# =============================================================================
# SECURITY - Required Environment Variables (No Defaults!)
# =============================================================================


def require_env(name: str, validation_func=None, error_msg: str = None) -> str:
    """
    Get required environment variable with optional validation.
    Exits immediately if missing or invalid - no defaults allowed!
    """
    value = os.getenv(name)

    if not value:
        print(f"❌ ERROR: Variable de entorno requerida faltante: {name}")
        if error_msg:
            print(f"   {error_msg}")
        else:
            print("   Agrega a tu archivo .env:")
        print(f"   {name}=tu-valor-aqui")
        print("\n   Ejemplo .env completo:")
        print("   GROK_API_KEY=xai-tu-clave")
        print("   DB_HOST=tu-servidor")
        print("   DB_NAME=SmartBusiness")
        print("   DB_USER=tu-usuario")
        print("   DB_PASSWORD=tu-contraseña")
        sys.exit(1)

    if validation_func and not validation_func(value):
        print(f"❌ ERROR: {name} tiene un valor inválido: {value}")
        if error_msg:
            print(f"   {error_msg}")
        sys.exit(1)

    return value


def _is_testing_env() -> bool:
    """
    Detect if we're running in a testing environment.
    Checks multiple indicators to be robust across different test runners.
    """
    # Check if pytest is imported
    if "pytest" in sys.modules:
        return True

    # Check for TESTING environment variable
    if os.getenv("TESTING", "false").lower() == "true":
        return True

    # Check if running from a test file (using inspect for safety)
    current_frame = None
    try:
        current_frame = inspect.currentframe()
        frame = current_frame
        depth = 0
        while frame and depth < MAX_STACK_FRAME_DEPTH:
            filename = frame.f_globals.get("__file__", "")
            if "test" in filename.lower() or "pytest" in filename.lower():
                return True
            frame = frame.f_back
            depth += 1
    except (AttributeError, ValueError):
        pass
    finally:
        if current_frame is not None:
            del current_frame

    return False


def get_env_or_test_default(
    name: str,
    test_default: str,
    validation_func=None,
    error_msg: str = None,
    warn_on_test_default: bool = True,
) -> str:
    """
    Get environment variable with testing support.

    In production: uses require_env() with validation and exits on failure.
    In testing: returns environment variable or test default with optional warning.

    Args:
        name: Environment variable name
        test_default: Default value to use in testing mode
        validation_func: Validation function (production mode only)
        error_msg: Error message for validation failures (production mode only)
        warn_on_test_default: If True, issue warning when using test default

    Returns:
        Environment variable value (validated in production, raw in testing)
    """
    is_testing = _is_testing_env()

    if is_testing:
        value = os.getenv(name, test_default)
        if warn_on_test_default and value == test_default:
            warnings.warn(
                f"Testing mode: Using default value for {name}",
                category=UserWarning,
                stacklevel=2,
            )
        return value
    else:
        return require_env(name, validation_func, error_msg)


# =============================================================================
# CONFIGURATION
# =============================================================================


class Config:
    """Configuration class for AI providers and database connections."""

    # AI Provider selection (grok, openai, anthropic, ollama)
    AI_PROVIDER = os.getenv("AI_PROVIDER", DEFAULT_PROVIDER).lower()

    # Validate provider
    if AI_PROVIDER not in SUPPORTED_PROVIDERS:
        print(f"❌ ERROR: AI_PROVIDER '{AI_PROVIDER}' no es válido.")
        print(f"   Proveedores soportados: {', '.join(SUPPORTED_PROVIDERS)}")
        print(f"   Ejemplo: AI_PROVIDER=grok")
        sys.exit(1)

    # Provider-specific API keys (only required for chosen provider)
    # Only load the API key for the selected provider to avoid requiring all keys
    if AI_PROVIDER == "grok":
        GROK_API_KEY = get_env_or_test_default(
            "GROK_API_KEY",
            test_default="xai-test-key-for-ci-only",
            validation_func=lambda x: x.startswith("xai-"),
            error_msg="La clave de Grok debe comenzar con 'xai-'",
            warn_on_test_default=True,
        )
        OPENAI_API_KEY = None
        ANTHROPIC_API_KEY = None
    elif AI_PROVIDER == "openai":
        OPENAI_API_KEY = get_env_or_test_default(
            "OPENAI_API_KEY",
            test_default="sk-test-key-for-ci-only",
            validation_func=lambda x: x.startswith("sk-"),
            error_msg="La clave de OpenAI debe comenzar con 'sk-'",
            warn_on_test_default=True,
        )
        GROK_API_KEY = None
        ANTHROPIC_API_KEY = None
    elif AI_PROVIDER == "anthropic":
        ANTHROPIC_API_KEY = get_env_or_test_default(
            "ANTHROPIC_API_KEY",
            test_default="sk-ant-test-key-for-ci-only",
            validation_func=lambda x: x.startswith("sk-ant-"),
            error_msg="La clave de Anthropic debe comenzar con 'sk-ant-'",
            warn_on_test_default=True,
        )
        GROK_API_KEY = None
        OPENAI_API_KEY = None
    else:  # ollama
        GROK_API_KEY = None
        OPENAI_API_KEY = None
        ANTHROPIC_API_KEY = None

    # Ollama configuration (local, no API key needed)
    OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://localhost:11434")
    OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "mistral")

    # Database configuration - using same names as core config
    DB_HOST = get_env_or_test_default("DB_HOST", test_default="test-host")
    DB_PORT = int(get_env_or_test_default("DB_PORT", "1433"))
    DB_NAME = get_env_or_test_default("DB_NAME", test_default="TestDB")
    DB_USER = get_env_or_test_default("DB_USER", test_default="test_user")
    DB_PASSWORD = get_env_or_test_default("DB_PASSWORD", test_default="test_password")

    # Server configuration
    PORT = int(os.getenv("PORT", "8084"))
    # nosec B104: Binding to 0.0.0.0 is intentional for the web server
    # This allows the server to be accessible from other machines on the network
    HOST = os.getenv("HOST", "0.0.0.0")  # nosec B104

    # Feature toggles
    ENABLE_AI_INSIGHTS = os.getenv("ENABLE_AI_INSIGHTS", "true").lower() == "true"
    INSIGHTS_MAX_ROWS = int(os.getenv("INSIGHTS_MAX_ROWS", "15"))
    MAX_DISPLAY_ROWS = int(os.getenv("MAX_DISPLAY_ROWS", "100"))


# =============================================================================
# ERROR HANDLING - Retry Logic
# =============================================================================


def retry_on_failure(max_attempts: int = 3, delay: int = 2, backoff: int = 2):
    """
    Decorator for retrying failed API calls with exponential backoff.

    Args:
        max_attempts: Maximum retry attempts (default 3)
        delay: Initial delay in seconds (default 2)
        backoff: Backoff multiplier (default 2 = exponential)
    """

    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            import time

            current_delay = delay

            for attempt in range(max_attempts):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    if attempt == max_attempts - 1:
                        raise

                    print(f"⚠️ Intento {attempt + 1}/{max_attempts} falló: {e}")
                    print(f"   Reintentando en {current_delay}s...")
                    time.sleep(current_delay)
                    current_delay *= backoff

            return None

        return wrapper

    return decorator


# =============================================================================
# AI PROVIDER FACTORY
# =============================================================================


def create_ai_client(provider: str = None):
    """
    Create AI client based on provider selection.

    Args:
        provider: AI provider name (grok, openai, anthropic, ollama)
                 Defaults to Config.AI_PROVIDER

    Returns:
        Tuple of (client, config_dict, provider_type) for Vanna initialization
    """
    if provider is None:
        provider = Config.AI_PROVIDER

    if provider == "grok":
        client = OpenAI(api_key=Config.GROK_API_KEY, base_url="https://api.x.ai/v1")
        config = {
            "model": "grok-4-1-fast-non-reasoning",
            "base_url": "https://api.x.ai/v1",
        }
        return client, config, "openai"

    elif provider == "openai":
        client = OpenAI(api_key=Config.OPENAI_API_KEY)
        config = {"model": "gpt-4", "api_key": Config.OPENAI_API_KEY}
        return client, config, "openai"

    elif provider == "anthropic":
        config = {
            "api_key": Config.ANTHROPIC_API_KEY,
            "model": "claude-3-sonnet-20240229",
        }
        return None, config, "anthropic"

    elif provider == "ollama":
        config = {"model": Config.OLLAMA_MODEL, "ollama_host": Config.OLLAMA_HOST}
        return None, config, "ollama"

    else:
        raise ValueError(f"Proveedor no soportado: {provider}")


# =============================================================================
# BASE VANNA CLASS
# =============================================================================


class AIVanna(ChromaDB_VectorStore, OpenAI_Chat):
    """
    Multi-provider Vanna AI class supporting Grok, OpenAI, Anthropic, and Ollama.

    Provider selection via AI_PROVIDER environment variable:
    - grok (default): xAI Grok
    - openai: OpenAI GPT-4
    - anthropic: Anthropic Claude
    - ollama: Local Ollama instance
    """

    def __init__(self):
        self.provider = Config.AI_PROVIDER
        self._query_cache = create_query_cache(
            int(os.getenv("CACHE_TTL_SECONDS", "300"))
        )
        self.ai_client, ai_config, provider_type = create_ai_client(self.provider)

        # 1. ChromaDB for RAG (local, private, fast)
        ChromaDB_VectorStore.__init__(self, config={})

        # 2. Initialize based on provider type
        if provider_type == "openai":
            OpenAI_Chat.__init__(self, client=self.ai_client, config=ai_config)
        elif provider_type == "anthropic":
            try:
                from vanna.legacy.anthropic import Anthropic_Chat

                Anthropic_Chat.__init__(self, config=ai_config)
            except ImportError:
                print("❌ ERROR: Anthropic support requires 'anthropic' package")
                print("   Instala con: pip install anthropic")
                sys.exit(1)
        elif provider_type == "ollama":
            try:
                from vanna.legacy.ollama import Ollama

                Ollama.__init__(self, config=ai_config)
            except ImportError:
                print("❌ ERROR: Ollama support requires 'ollama' package")
                print("   Instala con: pip install ollama")
                sys.exit(1)

        print(f"✓ Proveedor AI configurado: {self.provider.upper()}")

    @staticmethod
    def _normalize_currency_symbols(text: str) -> str:
        if not text:
            return text
        normalized = text.replace("₡", "$").replace("CRC ", "$").replace("COP ", "$")
        return AIVanna._normalize_scientific_notation(normalized)

    @staticmethod
    def _normalize_scientific_notation(text: str) -> str:
        scientific_number_pattern = re.compile(
            r"(?P<prefix>\$\s*)?(?P<number>[+-]?\d+(?:\.\d+)?[eE][+-]?\d+)"
        )

        def _replace(match: re.Match[str]) -> str:
            number_text = match.group("number")
            prefix = match.group("prefix") or ""
            try:
                value = float(number_text)
            except ValueError:
                return match.group(0)

            if not math.isfinite(value):
                return match.group(0)

            if value.is_integer():
                formatted = f"{int(value):,}".replace(",", ".")
            else:
                formatted = (
                    f"{value:,.2f}".replace(",", "TEMP")
                    .replace(".", ",")
                    .replace("TEMP", ".")
                )

            return f"{prefix}{formatted}"

        return scientific_number_pattern.sub(_replace, text)

    @staticmethod
    def _is_brand_profit_question(question: str) -> bool:
        lower = (question or "").lower()
        has_brand = "marca" in lower or "marcas" in lower
        has_profit = any(
            token in lower for token in ("rentable", "rentables", "ganancia", "margen")
        )
        return has_brand and has_profit

    @staticmethod
    def _extract_vendor_brands(question: str) -> List[str]:
        """Pull known vendor/brand tokens from a natural-language question."""
        lower = (question or "").lower()
        catalog = (
            "pavco",
            "euroceramica",
            "cemex",
            "sika",
            "acesco",
            "hylsa",
            "corona",
            "pintuco",
            "holcim",
        )
        found = [name.upper() for name in catalog if name in lower]
        for match in re.finditer(
            r"\b([a-záéíóúñ]{4,})\b",
            lower,
        ):
            token = match.group(1).upper()
            if token in {"VENTAS", "PRODUCTOS", "MARCA", "PROVEEDOR", "TOTAL"}:
                continue
            if " O " in f" {lower} " and token not in found:
                found.append(token)
        # de-duplicate preserving order
        seen = set()
        ordered: List[str] = []
        for brand in found:
            if brand not in seen:
                seen.add(brand)
                ordered.append(brand)
        return ordered

    @staticmethod
    def _is_multi_vendor_sales_question(question: str) -> bool:
        lower = (question or "").lower()
        has_sales = any(
            token in lower
            for token in ("venta", "ventas", "factur", "ingreso", "vendido")
        )
        brands = AIVanna._extract_vendor_brands(question)
        return has_sales and len(brands) >= 1

    @staticmethod
    def _multi_vendor_sales_sql_template(brands: List[str]) -> str:
        """Aggregate sales by vendor/brand with master-data enrichment."""
        safe_brands = [
            re.sub(r"[^A-Z0-9]", "", brand.upper()) for brand in brands if brand
        ]
        if not safe_brands:
            return ""
        in_list = ", ".join(f"'{brand}'" for brand in safe_brands)
        name_cases = "\n".join(
            f"            WHEN UPPER(bd.ArticulosNombre) LIKE '%{brand}%' "
            f"THEN '{brand}'"
            for brand in safe_brands
        )
        return f"""
SELECT
    Marca_Proveedor,
    SUM(TotalMasIva) AS Ventas_Totales,
    COUNT(*) AS Numero_Transacciones,
    SUM(TotalSinIva - ValorCosto) AS Ganancia
FROM (
    SELECT
        bd.TotalMasIva,
        bd.TotalSinIva,
        bd.ValorCosto,
        CASE
            WHEN UPPER(LTRIM(RTRIM(COALESCE(bd.proveedor, pa.proveedor_descripcion, ''))))
                 IN ({in_list})
                THEN UPPER(LTRIM(RTRIM(COALESCE(bd.proveedor, pa.proveedor_descripcion))))
            WHEN UPPER(LTRIM(RTRIM(COALESCE(bd.marca, pa.producto_marca, ''))))
                 IN ({in_list})
                THEN UPPER(LTRIM(RTRIM(COALESCE(bd.marca, pa.producto_marca))))
{name_cases}
            ELSE NULL
        END AS Marca_Proveedor
    FROM banco_datos bd
    LEFT JOIN productos_adicional pa ON bd.ArticulosCodigo = pa.producto_codigo
    WHERE bd.DocumentosCodigo NOT IN ('XY', 'AS', 'TS', 'YX', 'ISC')
) AS ventas_marca
WHERE Marca_Proveedor IS NOT NULL
GROUP BY Marca_Proveedor
ORDER BY Ventas_Totales DESC
        """.strip()

    @staticmethod
    def _insert_before_tail(sql: str, fragment: str) -> str:
        """Insert SQL fragment before GROUP/ORDER/HAVING/LIMIT clauses."""
        lower = sql.lower()
        positions = [
            pos
            for pos in (
                lower.find(" group by "),
                lower.find(" order by "),
                lower.find(" having "),
                lower.find(" limit "),
            )
            if pos != -1
        ]

        insert_at = min(positions) if positions else len(sql)
        head = sql[:insert_at].rstrip()
        tail = sql[insert_at:]

        if head.endswith(";"):
            head = head[:-1].rstrip()

        return f"{head} {fragment}{tail}"

    @staticmethod
    def _ensure_document_exclusion(sql: str) -> str:
        """Guarantee exclusion filter for banco_datos queries."""
        if not sql:
            return sql

        canonical_filter = "DocumentosCodigo NOT IN ('XY', 'AS', 'TS', 'YX', 'ISC')"
        normalized_sql = re.sub(
            r"DocumentosCodigo\s+NOT\s+IN\s*\([^\)]*\)",
            canonical_filter,
            sql,
            flags=re.IGNORECASE,
        )

        lower = sql.lower()
        normalized_lower = normalized_sql.lower()
        if "from banco_datos" not in lower:
            return normalized_sql

        if "documentoscodigo" in normalized_lower:
            return normalized_sql

        if " where " in lower:
            return AIVanna._insert_before_tail(
                normalized_sql, f"AND {canonical_filter}"
            )

        return AIVanna._insert_before_tail(normalized_sql, f"WHERE {canonical_filter}")

    @staticmethod
    def _brand_profit_sql_template() -> str:
        return """
SELECT TOP 10
    Marca,
    SUM(TotalSinIva - ValorCosto) AS Ganancia,
    SUM(TotalMasIva) AS Ventas,
    COUNT(*) AS Transacciones
FROM (
    SELECT
        UPPER(LTRIM(RTRIM(NULLIF(proveedor, '')))) AS Marca,
        TotalSinIva,
        ValorCosto,
        TotalMasIva
    FROM banco_datos
    WHERE DocumentosCodigo NOT IN ('XY', 'AS', 'TS', 'YX', 'ISC')
      AND NULLIF(LTRIM(RTRIM(proveedor)), '') IS NOT NULL
) AS marcas_norm
WHERE Marca NOT LIKE '%MATERIALES%'
  AND Marca NOT LIKE '%SERVICIO%'
  AND Marca NOT LIKE '%HERRAMIENAS%'
  AND Marca NOT LIKE '%REVESTIMIENTO%'
  AND Marca NOT LIKE '%PRODUCTOS EXCLUIDOS%'
  AND LEN(Marca) > 2
GROUP BY Marca
ORDER BY Ganancia DESC
        """.strip()

    @staticmethod
    def _is_weekday_sales_question(question: str) -> bool:
        lower = (question or "").lower()
        return (
            "día de la semana" in lower
            or "dias de la semana" in lower
            or "días de la semana" in lower
        )

    @staticmethod
    def _is_sika_center_branch_question(question: str) -> bool:
        lower = (question or "").lower()
        return "sika center" in lower

    @staticmethod
    def _month_number_from_question(question: str) -> int:
        lower = (question or "").lower()
        numeric_month = re.search(
            r"month\s*\(\s*fecha\s*\)\s*=\s*(1[0-2]|[1-9])", lower
        )
        if numeric_month:
            return int(numeric_month.group(1))

        month_names = {
            "enero": 1,
            "febrero": 2,
            "marzo": 3,
            "abril": 4,
            "mayo": 5,
            "junio": 6,
            "julio": 7,
            "agosto": 8,
            "septiembre": 9,
            "setiembre": 9,
            "octubre": 10,
            "noviembre": 11,
            "diciembre": 12,
        }
        for month_name, month_number in month_names.items():
            if month_name in lower:
                return month_number
        return 0

    @staticmethod
    def _sika_center_branch_sql_template(question: str = "") -> str:
        month_number = AIVanna._month_number_from_question(question)
        month_filter = f"\n  AND MONTH(Fecha) = {month_number}" if month_number else ""

        return """
SELECT
    YEAR(Fecha) AS Año,
    MONTH(Fecha) AS Mes,
    DATENAME(MONTH, Fecha) AS Nombre_Mes,
    SUM(TotalMasIva) AS Ventas_Totales,
    SUM(TotalSinIva - ValorCosto) AS Ganancia,
    COUNT(*) AS Numero_Transacciones
FROM banco_datos
WHERE DocumentosCodigo = 'FEF'
  AND YEAR(Fecha) = YEAR(GETDATE()){month_filter}
GROUP BY YEAR(Fecha), MONTH(Fecha), DATENAME(MONTH, Fecha)
ORDER BY Mes
        """.strip().format(
            month_filter=month_filter
        )

    @staticmethod
    def _repair_sika_center_customer_sql(sql: str) -> str:
        if not sql:
            return sql

        lower = sql.lower()
        references_sika_customer = (
            "tercerosnombres" in lower
            and "sika" in lower
            and "from banco_datos" in lower
        )
        if not references_sika_customer:
            return sql

        return AIVanna._sika_center_branch_sql_template(sql)

    @staticmethod
    def _weekday_sales_sql_template() -> str:
        return """
WITH ventas_por_dia AS (
    SELECT
        ((DATEPART(WEEKDAY, Fecha) + @@DATEFIRST + 5) % 7) + 1 AS Dia_Orden,
        TotalMasIva,
        TotalSinIva,
        ValorCosto
    FROM banco_datos
    WHERE DocumentosCodigo NOT IN ('XY', 'AS', 'TS')
      AND Fecha >= DATEADD(MONTH, -3, GETDATE())
)
SELECT
    CASE Dia_Orden
        WHEN 1 THEN 'Lunes'
        WHEN 2 THEN 'Martes'
        WHEN 3 THEN 'Miércoles'
        WHEN 4 THEN 'Jueves'
        WHEN 5 THEN 'Viernes'
        WHEN 6 THEN 'Sábado'
        WHEN 7 THEN 'Domingo'
    END AS Dia_Semana,
    Dia_Orden,
    SUM(TotalMasIva) AS Ventas_Totales,
    SUM(TotalSinIva - ValorCosto) AS Ganancia,
    COUNT(*) AS Numero_Transacciones
FROM ventas_por_dia
GROUP BY Dia_Orden
ORDER BY Dia_Orden
        """.strip()

    def connect_to_mssql(self, **kwargs):
        """Connect to MSSQL database using pyodbc or pymssql."""
        try:
            super().connect_to_mssql(**kwargs)
        except AttributeError:
            import pymssql

            login_timeout = int(os.getenv("DB_LOGIN_TIMEOUT", "30"))
            query_timeout = int(os.getenv("DB_TIMEOUT", "180"))
            self.connection = pymssql.connect(
                server=Config.DB_HOST,
                user=Config.DB_USER,
                password=Config.DB_PASSWORD,
                database=Config.DB_NAME,
                port=int(os.getenv("DB_PORT", "1433")),
                login_timeout=login_timeout,
                timeout=query_timeout,
                as_dict=True,
            )
            self.run_sql_is_set = True
            print("✓ MSSQL connected via pymssql fallback!")

    def generate_sql(
        self, question: str, allow_llm_to_see_data: bool = True, **kwargs
    ) -> str:
        """
        Generate SQL with circuit breaker and retry logic.
        """
        try:
            cached = self._query_cache.get(question)
            if cached:
                if self._is_multi_vendor_sales_question(question):
                    if "productos_adicional" not in cached.lower():
                        brands = self._extract_vendor_brands(question)
                        template = self._multi_vendor_sales_sql_template(brands)
                        if template:
                            self._query_cache.set(question, template)
                            return template
                return cached

            if self._is_multi_vendor_sales_question(question):
                brands = self._extract_vendor_brands(question)
                template = self._multi_vendor_sales_sql_template(brands)
                if template:
                    self._query_cache.set(question, template)
                    return template
            # Apply circuit breaker based on provider
            decorator = with_circuit_breaker(self.provider)
            decorated_gen = decorator(super().generate_sql)
            generated = decorated_gen(
                question=question, allow_llm_to_see_data=allow_llm_to_see_data, **kwargs
            )
            if isinstance(generated, str):
                normalized = generated.strip().upper()
                if (
                    normalized
                    and "SELECT" not in normalized
                    and "WITH" not in normalized
                ):
                    print(
                        "⚠️ Model returned non-SQL response; skipping execution for this question."
                    )
                    return None

                if self._is_brand_profit_question(question):
                    generated_lower = generated.lower()
                    if "from banco_datos" in generated_lower:
                        post_candidate = self._brand_profit_sql_template()
                        self._query_cache.set(question, post_candidate)
                        return post_candidate
                if self._is_weekday_sales_question(question):
                    generated_lower = generated.lower()
                    if "from banco_datos" in generated_lower:
                        post_candidate = self._weekday_sales_sql_template()
                        self._query_cache.set(question, post_candidate)
                        return post_candidate
                if self._is_sika_center_branch_question(question):
                    generated_lower = generated.lower()
                    if "from banco_datos" in generated_lower:
                        post_candidate = self._sika_center_branch_sql_template(question)
                        self._query_cache.set(question, post_candidate)
                        return post_candidate
                repaired_generated = self._repair_sika_center_customer_sql(generated)
                post_candidate = self._ensure_document_exclusion(repaired_generated)
                self._query_cache.set(question, post_candidate)
                return post_candidate
            return generated
        except CircuitBreakerError as e:
            print(f"🛑 AI Provider {self.provider.upper()} is currently offline: {e}")
            return None
        except Exception as e:
            print(f"⚠️ Error generating SQL with {self.provider.upper()}: {e}")
            raise

    def run_sql(self, sql: str, **kwargs):
        """Execute SQL via shared Database layer (pooling, timeouts, retry)."""
        import pandas as pd

        from business_analyzer.core.db_factory import (
            get_database,
            release_thread_connections,
        )

        if not sql:
            return pd.DataFrame()

        sql = self._repair_sika_center_customer_sql(sql)
        sql = self._ensure_document_exclusion(sql)

        def _with_customer_space_normalization(query: str) -> str:
            normalized = query.replace(
                "TercerosNombres LIKE",
                "REPLACE(REPLACE(TercerosNombres, '  ', ' '), '  ', ' ') LIKE",
            )
            normalized = normalized.replace(
                "tercerosnombres like",
                "REPLACE(REPLACE(tercerosnombres, '  ', ' '), '  ', ' ') like",
            )
            return normalized

        def _is_transient_connection_error(error: Exception) -> bool:
            message = str(error).lower()
            transient_markers = [
                "08s01",
                "10060",
                "0x274c",
                "sqlexecdirectw",
                "tcp provider",
                "communication link failure",
                "connection timed out",
                "connection reset",
                "broken pipe",
            ]
            return any(marker in message for marker in transient_markers)

        def _execute_via_database(query: str) -> pd.DataFrame:
            db = get_database(reuse=True)
            if not db.is_connected():
                db.connect()
            rows = db.execute_query(query)
            if not isinstance(rows, list):
                return pd.DataFrame()
            return pd.DataFrame(rows) if rows else pd.DataFrame()

        max_attempts = int(os.getenv("DB_QUERY_RETRIES", "2")) + 1
        last_error: Exception | None = None

        for attempt in range(max_attempts):
            try:
                df = _execute_via_database(sql)
                if (
                    df.empty
                    and "tercerosnombres" in sql.lower()
                    and " like " in sql.lower()
                ):
                    normalized_sql = _with_customer_space_normalization(sql)
                    if normalized_sql != sql:
                        normalized_df = _execute_via_database(normalized_sql)
                        if not normalized_df.empty:
                            return normalized_df
                return df
            except Exception as e:
                last_error = e
                if _is_transient_connection_error(e) and attempt < max_attempts - 1:
                    print(
                        f"⚠️ Conexión DB inestable (intento {attempt + 1}/{max_attempts}); "
                        "reintentando…"
                    )
                    release_thread_connections()
                    time.sleep(1.5 * (attempt + 1))
                    continue
                break

        if last_error is not None:
            print(f"❌ Database error executing SQL: {last_error}")
        return pd.DataFrame()

    def connect_to_mssql_odbc(self):
        """Connect & test via ODBC (Vanna's go-to for MSSQL)"""
        login_timeout = int(os.getenv("DB_LOGIN_TIMEOUT", "30"))
        query_timeout = int(os.getenv("DB_TIMEOUT", "180"))
        odbc_str = (
            f"DRIVER={{ODBC Driver 17 for SQL Server}};"
            f"SERVER={Config.DB_HOST};"
            f"DATABASE={Config.DB_NAME};"
            f"UID={Config.DB_USER};"
            f"PWD={Config.DB_PASSWORD};"
            f"TrustServerCertificate=yes;"
            f"Encrypt=yes;"
            f"Connection Timeout={login_timeout};"
            f"Query Timeout={query_timeout};"
        )
        try:
            self.connect_to_mssql(odbc_conn_str=odbc_str)
            df = self.run_sql("SELECT 1 AS ping;")
            if df is not None and not df.empty:
                print("✓ MSSQL connected & ping successful!")
            else:
                raise ValueError("Ping returned empty—check DB access")
        except (ImportError, Exception) as e:
            print(f"⚠️  pyodbc method failed ({e}), trying pymssql fallback...")
            import pymssql

            self.connection = pymssql.connect(
                server=Config.DB_HOST,
                user=Config.DB_USER,
                password=Config.DB_PASSWORD,
                database=Config.DB_NAME,
                port=int(os.getenv("DB_PORT", "1433")),
                login_timeout=login_timeout,
                timeout=query_timeout,
                as_dict=True,
            )
            self.run_sql_is_set = True
            df = self.run_sql("SELECT 1 AS ping;")
            if df is not None and not df.empty:
                print("✓ MSSQL connected via pymssql fallback!")
            else:
                raise ValueError("Ping returned empty—check DB access")

    def get_ai_client(self):
        """Get the AI client for insights generation."""
        if self.provider in ["grok", "openai"]:
            return self.ai_client
        elif self.provider == "anthropic":
            try:
                from anthropic import Anthropic

                return Anthropic(api_key=Config.ANTHROPIC_API_KEY)
            except ImportError:
                print("⚠️  Anthropic package not installed, skipping insights")
                return None
        elif self.provider == "ollama":
            return None
        return None

    def generate_summary(self, question: str, df, **kwargs) -> str:
        if df is None:
            return (
                "⚠️ No se pudo generar el resumen porque la consulta no devolvió "
                "resultados válidos."
            )

        if hasattr(df, "empty") and df.empty:
            return "ℹ️ La consulta no devolvió registros para resumir."

        try:
            from .formatting import format_dataframe

            preview = format_dataframe(df.head(Config.INSIGHTS_MAX_ROWS))
            message_log = [
                self.system_message(
                    "Eres un asistente de datos para una ferretería colombiana. "
                    "Resume en español colombiano usando formato de moneda COP "
                    "con separador de miles con punto (ej. $25.766.450.551). "
                    "Los valores ya vienen formateados: repítelos tal cual, sin "
                    "convertir a miles/millones ni abreviar (nada de 25.88 ni 9.6K)."
                ),
                self.system_message(
                    f"Pregunta del usuario: '{question}'\n\n"
                    f"Resultados:\n{preview.to_markdown(index=False)}\n"
                ),
                self.user_message(
                    "Resume brevemente los datos según la pregunta. "
                    "No agregues explicación extra." + self._response_language()
                ),
            ]
            summary = self.submit_prompt(message_log, **kwargs)
        except Exception as exc:
            return (
                "⚠️ No se pudo generar el resumen automático para esta consulta "
                f"({exc})."
            )

        return self._normalize_currency_symbols(summary)
