"""DeepSeek provider for the AI package."""

from typing import Tuple

try:
    from openai import OpenAI
except ImportError:
    OpenAI = None

from ..base import Config


class DeepSeekProvider:
    """DeepSeek OpenAI-compatible provider configuration."""

    NAME = "deepseek"
    DEFAULT_MODEL = "deepseek-v4-flash"
    BASE_URL = "https://api.deepseek.com"

    @classmethod
    def create_client(cls) -> Tuple[OpenAI, dict, str]:
        client = OpenAI(
            api_key=Config.DEEPSEEK_API_KEY,
            base_url=Config.DEEPSEEK_BASE_URL,
        )
        config = {
            "model": Config.DEEPSEEK_MODEL,
            "base_url": Config.DEEPSEEK_BASE_URL,
        }
        return client, config, "openai"

    @staticmethod
    def validate_api_key(api_key: str) -> bool:
        return bool(api_key and api_key.strip())


def create_deepseek_client() -> Tuple[OpenAI, dict, str]:
    """Create a DeepSeek client and Vanna configuration."""
    return DeepSeekProvider.create_client()
