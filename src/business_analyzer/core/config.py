"""
Unified application configuration (pydantic-settings).

Canonical home for env-backed settings previously split across
``src/config.py``, a planned ``core/config.py``, and ``ai/base.py``.

Env var names, defaults, and validation semantics are unchanged.
User-facing error strings remain Spanish (Colombian).
"""

from __future__ import annotations

import inspect
import logging
import os
import sys
import warnings
from pathlib import Path
from typing import Any, Callable, Dict, Optional

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from business_analyzer.core.paths import resolve_output_dir

try:
    from dotenv import load_dotenv

    load_dotenv()
    logging.info("Loaded configuration from .env file")
except ImportError:
    logging.warning(
        "python-dotenv not installed. Install with: pip install python-dotenv\n"
        "Using environment variables only."
    )

logger = logging.getLogger(__name__)

MAX_STACK_FRAME_DEPTH = 20
SUPPORTED_PROVIDERS = ["grok", "openai", "deepseek", "anthropic", "ollama"]
DEFAULT_PROVIDER = "grok"
DEFAULT_NCX_FILE_PATH = os.path.expanduser(
    "~/Coding_OMARCHY/python_files/connections.ncx"
)

_SETTINGS_FIELD_NAMES = (
    "NCX_FILE_PATH",
    "DB_HOST",
    "DB_PORT",
    "DB_USER",
    "DB_PASSWORD",
    "DB_NAME",
    "DB_NAME_J3SYSTEM",
    "DB_TABLE",
    "DB_LOGIN_TIMEOUT",
    "DB_TIMEOUT",
    "DB_TDS_VERSION",
    "REPORT_DPI",
    "DEFAULT_LIMIT",
    "LOG_LEVEL",
    "AI_PROVIDER",
    "GROK_API_KEY",
    "OPENAI_API_KEY",
    "DEEPSEEK_API_KEY",
    "ANTHROPIC_API_KEY",
    "OLLAMA_HOST",
    "OLLAMA_MODEL",
    "DEEPSEEK_BASE_URL",
    "DEEPSEEK_MODEL",
    "PORT",
    "HOST",
    "ENABLE_AI_INSIGHTS",
    "INSIGHTS_MAX_ROWS",
    "MAX_DISPLAY_ROWS",
)


def _env_str_or_default(value: Any, default: str) -> str:
    """Match ``src/config.py`` ``_env_str``: strip, then default if blank."""
    if value is None:
        return default
    if isinstance(value, str):
        cleaned = value.strip()
        return cleaned if cleaned else default
    return str(value)


_BOOL_TRUE = frozenset({"true", "1", "yes", "on"})
_BOOL_FALSE = frozenset({"false", "0", "no", "off"})


def _env_bool_default_true(value: Any) -> bool:
    """Parse an optional boolean env flag; default True (used by SMTP TLS).

    Accepts true/1/yes/on and false/0/no/off (case-insensitive). Blank, None,
    and unrecognized values keep the default (TLS on).
    """
    if value is None:
        return True
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return value != 0
    cleaned = str(value).strip().lower()
    if not cleaned:
        return True
    if cleaned in _BOOL_TRUE:
        return True
    if cleaned in _BOOL_FALSE:
        return False
    return True


def _blank_to_none(value: Any) -> Optional[str]:
    if value is None:
        return None
    if isinstance(value, str):
        cleaned = value.strip()
        return cleaned if cleaned else None
    return value


def _coerce_optional_int(value: Any, default: int) -> int:
    """Parse an int for Settings; invalid or blank values use ``default``.

    This keeps a malformed ``PORT`` / row-limit env var from breaking BI
    imports of ``core.config``. The AI hydrate path still uses strict
    ``int(os.getenv(...))`` so invalid values fail there as before.
    """
    if value is None:
        return default
    if isinstance(value, bool):
        return default
    if isinstance(value, int):
        return value
    if isinstance(value, str):
        cleaned = value.strip()
        if not cleaned:
            return default
        try:
            return int(cleaned, 10)
        except ValueError:
            try:
                as_float = float(cleaned)
            except ValueError:
                return default
            if not as_float.is_integer():
                return default
            try:
                return int(as_float)
            except (OverflowError, ValueError):
                return default
    try:
        return int(value)
    except (OverflowError, TypeError, ValueError):
        return default


class Settings(BaseSettings):
    """Environment-backed settings. Missing secrets do not fail construction."""

    model_config = SettingsConfigDict(
        extra="ignore",
        case_sensitive=True,
        populate_by_name=True,
    )

    NCX_FILE_PATH: str = Field(default=DEFAULT_NCX_FILE_PATH)
    DB_HOST: Optional[str] = None
    DB_PORT: int = 1433
    DB_USER: Optional[str] = None
    DB_PASSWORD: Optional[str] = None
    DB_NAME: str = "SmartBusiness"
    DB_NAME_J3SYSTEM: str = "J3System"
    DB_TABLE: str = "banco_datos"
    DB_LOGIN_TIMEOUT: int = 30
    DB_TIMEOUT: int = 180
    DB_TDS_VERSION: str = "7.4"
    REPORT_DPI: int = 300
    DEFAULT_LIMIT: int = 1000
    LOG_LEVEL: str = "INFO"

    AI_PROVIDER: str = DEFAULT_PROVIDER
    GROK_API_KEY: Optional[str] = None
    OPENAI_API_KEY: Optional[str] = None
    DEEPSEEK_API_KEY: Optional[str] = None
    ANTHROPIC_API_KEY: Optional[str] = None
    OLLAMA_HOST: str = "http://localhost:11434"
    OLLAMA_MODEL: str = "mistral"
    DEEPSEEK_BASE_URL: str = "https://api.deepseek.com"
    DEEPSEEK_MODEL: str = "deepseek-v4-flash"
    PORT: int = 8084
    # nosec B104: Binding to 0.0.0.0 is intentional for the web server
    HOST: str = "0.0.0.0"  # nosec B104
    ENABLE_AI_INSIGHTS: bool = True
    INSIGHTS_MAX_ROWS: int = 15
    MAX_DISPLAY_ROWS: int = 100

    SMTP_HOST: Optional[str] = None
    SMTP_PORT: int = 587
    SMTP_USER: Optional[str] = None
    SMTP_PASSWORD: Optional[str] = None
    SMTP_USE_TLS: bool = True
    MAIL_FROM: Optional[str] = None
    MAIL_TO: Optional[str] = None
    AKZONOBEL_CORE_LINES_CONFIG: Optional[str] = None
    ASSISTANT_CHAT_LOG: Optional[str] = None

    @field_validator(
        "DB_HOST",
        "DB_USER",
        "DB_PASSWORD",
        "SMTP_HOST",
        "SMTP_USER",
        "SMTP_PASSWORD",
        "MAIL_FROM",
        "MAIL_TO",
        "AKZONOBEL_CORE_LINES_CONFIG",
        "ASSISTANT_CHAT_LOG",
        mode="before",
    )
    @classmethod
    def _optional_db_str(cls, value: Any) -> Optional[str]:
        return _blank_to_none(value)

    @field_validator("DB_NAME", mode="before")
    @classmethod
    def _db_name(cls, value: Any) -> str:
        return _env_str_or_default(value, "SmartBusiness")

    @field_validator("DB_NAME_J3SYSTEM", mode="before")
    @classmethod
    def _j3_name(cls, value: Any) -> str:
        return _env_str_or_default(value, "J3System")

    @field_validator("DB_TABLE", mode="before")
    @classmethod
    def _db_table(cls, value: Any) -> str:
        return _env_str_or_default(value, "banco_datos")

    @field_validator("DB_PORT", mode="before")
    @classmethod
    def _db_port(cls, value: Any) -> Any:
        if value is None:
            return 1433
        if isinstance(value, str) and not value.strip():
            return 1433
        return value

    @field_validator("AI_PROVIDER", mode="before")
    @classmethod
    def _ai_provider(cls, value: Any) -> str:
        if value is None:
            return DEFAULT_PROVIDER
        return str(value).lower()

    @field_validator("ENABLE_AI_INSIGHTS", mode="before")
    @classmethod
    def _ai_insights_flag(cls, value: Any) -> bool:
        if value is None:
            return True
        if isinstance(value, bool):
            return value
        return str(value).lower() == "true"

    @field_validator("PORT", mode="before")
    @classmethod
    def _port(cls, value: Any) -> int:
        return _coerce_optional_int(value, 8084)

    @field_validator("SMTP_PORT", mode="before")
    @classmethod
    def _smtp_port(cls, value: Any) -> int:
        return _coerce_optional_int(value, 587)

    @field_validator("SMTP_USE_TLS", mode="before")
    @classmethod
    def _smtp_use_tls(cls, value: Any) -> bool:
        return _env_bool_default_true(value)

    @field_validator("INSIGHTS_MAX_ROWS", mode="before")
    @classmethod
    def _insights_max_rows(cls, value: Any) -> int:
        return _coerce_optional_int(value, 15)

    @field_validator("MAX_DISPLAY_ROWS", mode="before")
    @classmethod
    def _max_display_rows(cls, value: Any) -> int:
        return _coerce_optional_int(value, 100)


def get_settings() -> Settings:
    """Build a fresh Settings snapshot from the current process environment."""
    return Settings()


def require_env(
    name: str, validation_func: Callable = None, error_msg: str = None
) -> str:
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
        print(f"❌ ERROR: {name} tiene un valor inválido")
        if error_msg:
            print(f"   {error_msg}")
        sys.exit(1)

    return value


def _is_testing_env() -> bool:
    """
    Detect if we're running in a testing environment.
    Checks multiple indicators to be robust across different test runners.
    """
    if "pytest" in sys.modules:
        return True

    if os.getenv("TESTING", "false").lower() == "true":
        return True

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
        # Stack frames can disappear while walking; treat as not-testing.
        pass
    finally:
        if current_frame is not None:
            del current_frame

    return False


def get_env_or_test_default(
    name: str,
    test_default: str,
    validation_func: Callable = None,
    error_msg: str = None,
    warn_on_test_default: bool = True,
) -> str:
    """
    Get environment variable with testing support.

    In production: uses require_env() with validation and exits on failure.
    In testing: returns environment variable or test default with optional warning.
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
    return require_env(name, validation_func, error_msg)


def resolve_database_settings() -> Dict[str, Any]:
    """Resolve direct database variables or a local Navicat NCX export."""
    if _is_testing_env():
        return {
            "host": get_env_or_test_default("DB_HOST", test_default="test-host"),
            "port": int(get_env_or_test_default("DB_PORT", "1433")),
            "name": get_env_or_test_default("DB_NAME", test_default="TestDB"),
            "user": get_env_or_test_default("DB_USER", test_default="test_user"),
            "password": get_env_or_test_default(
                "DB_PASSWORD", test_default="test_password"
            ),
        }

    direct_requested = any(
        os.getenv(name) for name in ("DB_HOST", "DB_USER", "DB_PASSWORD")
    )
    if direct_requested:
        return {
            "host": require_env("DB_HOST"),
            "port": int(os.getenv("DB_PORT", "1433")),
            "name": require_env("DB_NAME"),
            "user": require_env("DB_USER"),
            "password": require_env("DB_PASSWORD"),
        }

    ncx_file_path = os.getenv("NCX_FILE_PATH")
    if ncx_file_path:
        from business_analyzer.core.database import load_connections

        expanded_path = os.path.expanduser(ncx_file_path)
        connections = load_connections(expanded_path)
        if not connections:
            print(f"❌ ERROR: No se encontró una conexión válida en {expanded_path}")
            sys.exit(1)

        details = connections[0]
        return {
            "host": details["Host"],
            "port": int(details.get("Port", 1433)),
            "name": os.getenv("DB_NAME") or details.get("Database", "master"),
            "user": details["UserName"],
            "password": details["Password"],
        }

    return {
        "host": require_env("DB_HOST"),
        "port": int(os.getenv("DB_PORT", "1433")),
        "name": require_env("DB_NAME"),
        "user": require_env("DB_USER"),
        "password": require_env("DB_PASSWORD"),
    }


def hydrate_ai_config() -> None:
    """Apply ``ai/base.py`` import-time AI provider validation and key loading.

    Calls :func:`resolve_database_settings` so a missing production DB config
    still fail-fast with the Spanish ``require_env`` message (same timing as
    the historical ``ai/base.py`` class body). The resolved mapping is stored
    on ``Config._DB_SETTINGS`` and is not copied onto BI ``Config.DB_*``.
    """
    provider = os.getenv("AI_PROVIDER", DEFAULT_PROVIDER).lower()
    if provider not in SUPPORTED_PROVIDERS:
        print(f"❌ ERROR: AI_PROVIDER '{provider}' no es válido.")
        print(f"   Proveedores soportados: {', '.join(SUPPORTED_PROVIDERS)}")
        print("   Ejemplo: AI_PROVIDER=grok")
        sys.exit(1)

    Config.AI_PROVIDER = provider
    Config.GROK_API_KEY = None
    Config.OPENAI_API_KEY = None
    Config.DEEPSEEK_API_KEY = None
    Config.ANTHROPIC_API_KEY = None

    if provider == "grok":
        Config.GROK_API_KEY = get_env_or_test_default(
            "GROK_API_KEY",
            test_default="xai-test-key-for-ci-only",
            validation_func=lambda x: x.startswith("xai-"),
            error_msg="La clave de Grok debe comenzar con 'xai-'",
            warn_on_test_default=True,
        )
    elif provider == "openai":
        Config.OPENAI_API_KEY = get_env_or_test_default(
            "OPENAI_API_KEY",
            test_default="sk-test-key-for-ci-only",
            validation_func=lambda x: x.startswith("sk-"),
            error_msg="La clave de OpenAI debe comenzar con 'sk-'",
            warn_on_test_default=True,
        )
    elif provider == "deepseek":
        Config.DEEPSEEK_API_KEY = get_env_or_test_default(
            "DEEPSEEK_API_KEY",
            test_default="sk-test-key-for-ci-only",
            warn_on_test_default=True,
        )
    elif provider == "anthropic":
        Config.ANTHROPIC_API_KEY = get_env_or_test_default(
            "ANTHROPIC_API_KEY",
            test_default="sk-ant-test-key-for-ci-only",
            validation_func=lambda x: x.startswith("sk-ant-"),
            error_msg="La clave de Anthropic debe comenzar con 'sk-ant-'",
            warn_on_test_default=True,
        )

    Config.OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://localhost:11434")
    Config.OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "mistral")
    Config.DEEPSEEK_BASE_URL = os.getenv(
        "DEEPSEEK_BASE_URL", "https://api.deepseek.com"
    )
    Config.DEEPSEEK_MODEL = os.getenv("DEEPSEEK_MODEL", "deepseek-v4-flash")
    # Fail-fast on missing production DB, same as historical ai/base.py Config.
    Config._DB_SETTINGS = resolve_database_settings()
    Config.PORT = int(os.getenv("PORT", "8084"))
    Config.HOST = os.getenv("HOST", "0.0.0.0")  # nosec B104
    Config.ENABLE_AI_INSIGHTS = (
        os.getenv("ENABLE_AI_INSIGHTS", "true").lower() == "true"
    )
    Config.INSIGHTS_MAX_ROWS = int(os.getenv("INSIGHTS_MAX_ROWS", "15"))
    Config.MAX_DISPLAY_ROWS = int(os.getenv("MAX_DISPLAY_ROWS", "100"))
    Config.OUTPUT_DIR = resolve_output_dir()


class Config:
    """Class-attribute facade used throughout the codebase (``Config.DB_HOST``)."""

    EXCLUDED_DOCUMENT_CODES = ["XY", "AS", "TS", "YX", "ISC"]
    REPORT_FIGURE_SIZE = (20, 24)
    # Resolved AI/NCX credentials. Not copied onto optional BI ``DB_*``.
    _DB_SETTINGS: Optional[Dict[str, Any]] = None

    @classmethod
    def reload(cls) -> Settings:
        """Re-read environment into class attributes (BI defaults, optional secrets)."""
        settings = get_settings()
        for name in _SETTINGS_FIELD_NAMES:
            setattr(cls, name, getattr(settings, name))
        cls.OUTPUT_DIR = resolve_output_dir()
        return settings

    @classmethod
    def ensure_output_dir(cls) -> Path:
        """Create output directory if it doesn't exist"""
        path = resolve_output_dir()
        cls.OUTPUT_DIR = path
        path.mkdir(parents=True, exist_ok=True)
        return path

    @classmethod
    def has_direct_db_config(cls) -> bool:
        """Check if direct database configuration is provided"""
        return all([cls.DB_HOST, cls.DB_USER, cls.DB_PASSWORD])

    @classmethod
    def validate(cls) -> bool:
        """Validate configuration and check for security issues"""
        if not cls.has_direct_db_config() and not os.path.exists(cls.NCX_FILE_PATH):
            raise ValueError(
                "No valid database configuration found. "
                "Provide either NCX_FILE_PATH or DB_HOST/DB_USER/DB_PASSWORD "
                "environment variables."
            )

        if cls.has_direct_db_config():
            logger.warning(
                "⚠️  Using direct database credentials from environment variables. "
                "Ensure these are not exposed in logs or version control."
            )

        if (
            cls.NCX_FILE_PATH
            and "/home/" in cls.NCX_FILE_PATH
            and "NCX_FILE_PATH" not in os.environ
        ):
            logger.warning(
                f"⚠️  NCX_FILE_PATH appears to be hardcoded: {cls.NCX_FILE_PATH}\n"
                f"   Consider setting NCX_FILE_PATH environment variable instead."
            )

        return True


class CustomerSegmentation:
    """Customer segmentation configuration"""

    VIP_REVENUE_THRESHOLD = 500000
    VIP_ORDERS_THRESHOLD = 5
    HIGH_VALUE_THRESHOLD = 200000
    FREQUENT_ORDERS_THRESHOLD = 10
    REGULAR_REVENUE_THRESHOLD = 50000


class InventoryConfig:
    """Inventory analysis configuration"""

    FAST_MOVER_THRESHOLD = 5
    SLOW_MOVER_THRESHOLD = 2


class ProfitabilityConfig:
    """Profitability analysis configuration"""

    LOW_MARGIN_THRESHOLD = 10
    STAR_PRODUCT_MARGIN = 30
    CRITICAL_MARGIN = 0


Config.reload()
