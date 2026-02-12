"""
OpenAI provider for AI package.
"""

from typing import Any, Optional, Tuple

try:
    from openai import OpenAI
except ImportError:
    OpenAI = None

from ..base import Config


class OpenAIProvider:
    """OpenAI provider configuration."""

    NAME = "openai"
    DEFAULT_MODEL = "gpt-4"

    @classmethod
    def create_client(cls) -> Tuple[OpenAI, dict, str]:
        """
        Create OpenAI client and configuration.

        Returns:
            Tuple of (client, config_dict, provider_type)
        """
        client = OpenAI(api_key=Config.OPENAI_API_KEY)
        config = {"model": cls.DEFAULT_MODEL, "api_key": Config.OPENAI_API_KEY}
        return client, config, "openai"

    @classmethod
    def validate_api_key(cls, api_key: str) -> bool:
        """Validate OpenAI API key format."""
        return api_key.startswith("sk-")


def create_openai_client() -> Tuple[OpenAI, dict, str]:
    """
    Create OpenAI client.

    Returns:
        Tuple of (client, config_dict, provider_type)
    """
    return OpenAIProvider.create_client()
