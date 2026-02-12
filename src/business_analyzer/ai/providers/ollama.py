"""
Ollama (local) provider for AI package.
"""

from typing import Any, Optional, Tuple

from ..base import Config


class OllamaProvider:
    """Ollama local provider configuration."""

    NAME = "ollama"
    DEFAULT_MODEL = "mistral"
    DEFAULT_HOST = "http://localhost:11434"

    @classmethod
    def create_config(cls) -> Tuple[Optional[Any], dict, str]:
        """
        Create Ollama configuration.
        Note: Ollama is local, no API key needed.

        Returns:
            Tuple of (None, config_dict, provider_type)
        """
        config = {
            "model": Config.OLLAMA_MODEL or cls.DEFAULT_MODEL,
            "ollama_host": Config.OLLAMA_HOST or cls.DEFAULT_HOST,
        }
        return None, config, "ollama"

    @classmethod
    def get_ollama_client(cls):
        """Get Ollama client if available."""
        try:
            import ollama

            return ollama
        except ImportError:
            print("⚠️  Ollama package not installed")
            return None


def create_ollama_config() -> Tuple[Optional[Any], dict, str]:
    """
    Create Ollama configuration.

    Returns:
        Tuple of (None, config_dict, provider_type)
    """
    return OllamaProvider.create_config()
