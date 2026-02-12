"""
Grok (xAI) provider for AI package.
"""

from typing import Tuple, Optional, Any

try:
    from openai import OpenAI
except ImportError:
    OpenAI = None

from ..base import Config


class GrokProvider:
    """Grok (xAI) provider configuration."""

    NAME = "grok"
    DEFAULT_MODEL = "grok-beta"
    BASE_URL = "https://api.x.ai/v1"
    INSIGHTS_MODEL = "grok-4-1-fast-non-reasoning"

    @classmethod
    def create_client(cls) -> Tuple[OpenAI, dict, str]:
        """
        Create Grok client and configuration.

        Returns:
            Tuple of (client, config_dict, provider_type)
        """
        client = OpenAI(api_key=Config.GROK_API_KEY, base_url=cls.BASE_URL)
        config = {"model": cls.DEFAULT_MODEL, "base_url": cls.BASE_URL}
        return client, config, "openai"

    @classmethod
    def validate_api_key(cls, api_key: str) -> bool:
        """Validate Grok API key format."""
        return api_key.startswith("xai-")


def create_grok_client() -> Tuple[OpenAI, dict, str]:
    """
    Create Grok client.

    Returns:
        Tuple of (client, config_dict, provider_type)
    """
    return GrokProvider.create_client()
