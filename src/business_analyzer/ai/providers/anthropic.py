"""
Anthropic Claude provider for AI package.
"""

from typing import Any, Optional, Tuple

from ..base import Config


class AnthropicProvider:
    """Anthropic Claude provider configuration."""

    NAME = "anthropic"
    DEFAULT_MODEL = "claude-3-sonnet-20240229"

    @classmethod
    def create_client(cls) -> Tuple[Optional[Any], dict, str]:
        """
        Create Anthropic configuration.
        Note: Anthropic uses its own client, not OpenAI-compatible.

        Returns:
            Tuple of (None, config_dict, provider_type)
        """
        config = {"api_key": Config.ANTHROPIC_API_KEY, "model": cls.DEFAULT_MODEL}
        return None, config, "anthropic"

    @classmethod
    def get_anthropic_client(cls):
        """Get Anthropic client for insights generation."""
        try:
            from anthropic import Anthropic

            return Anthropic(api_key=Config.ANTHROPIC_API_KEY)
        except ImportError:
            print("⚠️  Anthropic package not installed")
            return None

    @classmethod
    def validate_api_key(cls, api_key: str) -> bool:
        """Validate Anthropic API key format."""
        return api_key.startswith("sk-ant-")


def create_anthropic_client() -> Tuple[Optional[Any], dict, str]:
    """
    Create Anthropic configuration.

    Returns:
        Tuple of (None, config_dict, provider_type)
    """
    return AnthropicProvider.create_client()
