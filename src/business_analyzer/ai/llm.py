"""Provider / LLM wiring for the AI package.

Holds retry helpers, the multi-provider client factory, and AIVanna
construction / client access. SQL routing and summaries live elsewhere.
"""

from __future__ import annotations

import os
import sys
from functools import wraps
from typing import Any, Callable, Dict, Optional

from vanna.legacy.chromadb.chromadb_vector import ChromaDB_VectorStore
from vanna.legacy.openai import OpenAI_Chat

from business_analyzer.core.config import Config
from business_analyzer.core.query_cache import create_query_cache

try:
    from openai import OpenAI
except ImportError:
    OpenAI = None


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

    elif provider == "deepseek":
        client = OpenAI(
            api_key=Config.DEEPSEEK_API_KEY,
            base_url=Config.DEEPSEEK_BASE_URL,
        )
        config = {
            "model": Config.DEEPSEEK_MODEL,
            "base_url": Config.DEEPSEEK_BASE_URL,
        }
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


def _iter_loaded_ai_base_modules():
    """Yield loaded ``ai.base`` facade modules, including ``src.*`` aliases."""
    suffix = "business_analyzer.ai.base"
    names = {suffix}
    package = __package__
    if package:
        names.add(f"{package}.base")
        if package.startswith("src."):
            names.add(f"{package[len('src.') :]}.base")
        else:
            names.add(f"src.{package}.base")
    yielded = set()
    for name, mod in sys.modules.items():
        if mod is None:
            continue
        if name == suffix or name.endswith(f".{suffix}"):
            if name not in yielded:
                yielded.add(name)
                yield mod
    for name in names:
        if name in yielded:
            continue
        mod = sys.modules.get(name)
        if mod is not None:
            yielded.add(name)
            yield mod


def _original_create_ai_client_functions():
    """``create_ai_client`` objects from every loaded ``ai.llm`` copy."""
    originals = {create_ai_client}
    suffix = "business_analyzer.ai.llm"
    for name, mod in sys.modules.items():
        if mod is None:
            continue
        if name == suffix or name.endswith(f".{suffix}"):
            factory = getattr(mod, "create_ai_client", None)
            if factory is not None:
                originals.add(factory)
    return originals


def _resolve_create_ai_client():
    """Use any loaded ai.base facade so historical patches still apply.

    Looks up ``create_ai_client`` on every loaded module named
    ``business_analyzer.ai.base`` or ``*.business_analyzer.ai.base`` (covers
    ``src.business_analyzer.ai.base``) and on the sibling ``base`` module
    implied by ``__package__``. A patched factory (not one of the
    implementation-module originals) wins.
    """
    originals = _original_create_ai_client_functions()
    for facade in _iter_loaded_ai_base_modules():
        factory = getattr(facade, "create_ai_client", None)
        if factory is not None and factory not in originals:
            return factory
    return create_ai_client


class LLMMixin:
    """AIVanna construction and provider client access."""

    def __init__(self):
        self.provider = Config.AI_PROVIDER
        self._query_cache = create_query_cache(
            int(os.getenv("CACHE_TTL_SECONDS", "300"))
        )
        self._manager_report_result: Optional[Dict[str, Any]] = None
        self.ai_client, ai_config, provider_type = _resolve_create_ai_client()(
            self.provider
        )

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

    def get_ai_client(self):
        """Get the AI client for insights generation."""
        if self.provider in ["grok", "openai", "deepseek"]:
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
