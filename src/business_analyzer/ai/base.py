"""
Base module for AI package.

Contains configuration, security utilities, and the AIVanna base class.
"""

import os
import sys
import inspect
import warnings
from functools import wraps
from typing import Any, Callable, Optional

# Optional dotenv import
try:
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:
    pass

# Vanna imports
try:
    from vanna.legacy.chromadb.chromadb_vector import ChromaDB_VectorStore
    from vanna.legacy.openai import OpenAI_Chat
except ImportError:
    # Create dummy base classes for when vanna is not available
    class _ChromaDB_VectorStore:
        def __init__(self, *args, **kwargs):
            pass

    class _OpenAI_Chat:
        def __init__(self, *args, **kwargs):
            pass

    ChromaDB_VectorStore = _ChromaDB_VectorStore
    OpenAI_Chat = _OpenAI_Chat

try:
    from openai import OpenAI
except ImportError:
    OpenAI = None

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
            print(f"   Agrega a tu archivo .env:")
            print(f"   {name}=tu-valor-aqui")
        print(f"\n   Ejemplo .env completo:")
        print(f"   GROK_API_KEY=xai-tu-clave")
        print(f"   DB_SERVER=tu-servidor")
        print(f"   DB_NAME=SmartBusiness")
        print(f"   DB_USER=tu-usuario")
        print(f"   DB_PASSWORD=tu-contraseña")
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
    HOST = os.getenv("HOST", "0.0.0.0")

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
        config = {"model": "grok-beta", "base_url": "https://api.x.ai/v1"}
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
        except ImportError:
            print("❌ pyodbc missing: Run 'pip install pyodbc'")
            sys.exit(1)
        except Exception as e:
            print(f"❌ MSSQL connection failed: {e}")
            print("💡 Quick Fixes:")
            print("   - Linux: sudo apt install unixodbc-dev msodbcsql17")
            print("   - Or reply 'pymssql fallback' for pure Python DB connect")
            sys.exit(1)

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
