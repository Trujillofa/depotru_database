"""
Base module for AI package.

Contains configuration, security utilities, and the AIVanna base class.
"""

import inspect
import math
import os
import re
import sys
import warnings
from functools import wraps
from typing import Callable

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
        print("   DB_SERVER=tu-servidor")
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
    GROK_API_KEY = get_env_or_test_default(
        "GROK_API_KEY",
        test_default="xai-test-key-for-ci-only",
        validation_func=lambda x: x.startswith("xai-"),
        error_msg="La clave de Grok debe comenzar con 'xai-'",
        warn_on_test_default=AI_PROVIDER == "grok",
    )

    OPENAI_API_KEY = get_env_or_test_default(
        "OPENAI_API_KEY",
        test_default="sk-test-key-for-ci-only",
        validation_func=lambda x: x.startswith("sk-"),
        error_msg="La clave de OpenAI debe comenzar con 'sk-'",
        warn_on_test_default=AI_PROVIDER == "openai",
    )

    ANTHROPIC_API_KEY = get_env_or_test_default(
        "ANTHROPIC_API_KEY",
        test_default="sk-ant-test-key-for-ci-only",
        validation_func=lambda x: x.startswith("sk-ant-"),
        error_msg="La clave de Anthropic debe comenzar con 'sk-ant-'",
        warn_on_test_default=AI_PROVIDER == "anthropic",
    )

    # Ollama configuration (local, no API key needed)
    OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://localhost:11434")
    OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "mistral")

    # Database configuration
    DB_SERVER = get_env_or_test_default("DB_SERVER", test_default="test-server")
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

    def connect_to_mssql(self, **kwargs):
        """Connect to MSSQL database using pyodbc or pymssql."""
        try:
            super().connect_to_mssql(**kwargs)
        except AttributeError:
            import pymssql

            self.connection = pymssql.connect(
                server=Config.DB_SERVER,
                user=Config.DB_USER,
                password=Config.DB_PASSWORD,
                database=Config.DB_NAME,
                port=int(os.getenv("DB_PORT", "1433")),
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
                        return self._brand_profit_sql_template()
            return generated
        except CircuitBreakerError as e:
            print(f"🛑 AI Provider {self.provider.upper()} is currently offline: {e}")
            return None
        except Exception as e:
            print(f"⚠️ Error generating SQL with {self.provider.upper()}: {e}")
            raise

    def run_sql(self, sql: str, **kwargs):
        """Execute SQL with improved error handling."""
        import pandas as pd

        if not sql:
            return pd.DataFrame()

        def _execute_to_dataframe(query: str):
            cursor = self.connection.cursor()
            try:
                cursor.execute(query)
                columns = [desc[0] for desc in cursor.description]
                rows = cursor.fetchall()
                return pd.DataFrame(rows, columns=columns)
            finally:
                cursor.close()

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

        try:
            if hasattr(self, "connection") and self.connection:
                df = _execute_to_dataframe(sql)
                if (
                    df.empty
                    and "tercerosnombres" in sql.lower()
                    and " like " in sql.lower()
                ):
                    normalized_sql = _with_customer_space_normalization(sql)
                    if normalized_sql != sql:
                        normalized_df = _execute_to_dataframe(normalized_sql)
                        if not normalized_df.empty:
                            return normalized_df
                return df
            super_df = super().run_sql(sql, **kwargs)
            if super_df is None:
                return pd.DataFrame()
            return super_df
        except Exception as e:
            print(f"❌ Database error executing SQL: {e}")
            return pd.DataFrame()

    def connect_to_mssql_odbc(self):
        """Connect & test via ODBC (Vanna's go-to for MSSQL)"""
        odbc_str = (
            f"DRIVER={{ODBC Driver 17 for SQL Server}};"
            f"SERVER={Config.DB_SERVER};"
            f"DATABASE={Config.DB_NAME};"
            f"UID={Config.DB_USER};"
            f"PWD={Config.DB_PASSWORD};"
            f"TrustServerCertificate=yes;"
            f"Encrypt=yes;"
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
                server=Config.DB_SERVER,
                user=Config.DB_USER,
                password=Config.DB_PASSWORD,
                database=Config.DB_NAME,
                port=int(os.getenv("DB_PORT", "1433")),
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
            summary = super().generate_summary(question, df, **kwargs)
        except Exception as exc:
            return (
                "⚠️ No se pudo generar el resumen automático para esta consulta "
                f"({exc})."
            )

        return self._normalize_currency_symbols(summary)
