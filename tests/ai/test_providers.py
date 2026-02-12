"""
Tests for AI package providers.
"""

import os
import sys

import pytest

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../src"))

from business_analyzer.ai.providers import (
    AnthropicProvider,
    GrokProvider,
    OllamaProvider,
    OpenAIProvider,
)


class TestGrokProvider:
    """Test Grok provider."""

    def test_provider_name(self):
        """Test provider name."""
        assert GrokProvider.NAME == "grok"

    def test_default_model(self):
        """Test default model."""
        assert GrokProvider.DEFAULT_MODEL == "grok-beta"

    def test_base_url(self):
        """Test base URL."""
        assert GrokProvider.BASE_URL == "https://api.x.ai/v1"

    def test_validate_api_key_valid(self):
        """Test valid API key validation."""
        assert GrokProvider.validate_api_key("xai-valid-key") is True

    def test_validate_api_key_invalid(self):
        """Test invalid API key validation."""
        assert GrokProvider.validate_api_key("invalid-key") is False


class TestOpenAIProvider:
    """Test OpenAI provider."""

    def test_provider_name(self):
        """Test provider name."""
        assert OpenAIProvider.NAME == "openai"

    def test_default_model(self):
        """Test default model."""
        assert OpenAIProvider.DEFAULT_MODEL == "gpt-4"

    def test_validate_api_key_valid(self):
        """Test valid API key validation."""
        assert OpenAIProvider.validate_api_key("sk-valid-key") is True

    def test_validate_api_key_invalid(self):
        """Test invalid API key validation."""
        assert OpenAIProvider.validate_api_key("invalid-key") is False


class TestAnthropicProvider:
    """Test Anthropic provider."""

    def test_provider_name(self):
        """Test provider name."""
        assert AnthropicProvider.NAME == "anthropic"

    def test_default_model(self):
        """Test default model."""
        assert AnthropicProvider.DEFAULT_MODEL == "claude-3-sonnet-20240229"

    def test_validate_api_key_valid(self):
        """Test valid API key validation."""
        assert AnthropicProvider.validate_api_key("sk-ant-valid-key") is True

    def test_validate_api_key_invalid(self):
        """Test invalid API key validation."""
        assert AnthropicProvider.validate_api_key("invalid-key") is False


class TestOllamaProvider:
    """Test Ollama provider."""

    def test_provider_name(self):
        """Test provider name."""
        assert OllamaProvider.NAME == "ollama"

    def test_default_model(self):
        """Test default model."""
        assert OllamaProvider.DEFAULT_MODEL == "mistral"

    def test_default_host(self):
        """Test default host."""
        assert OllamaProvider.DEFAULT_HOST == "http://localhost:11434"


class TestProviderExports:
    """Test that all providers are exported."""

    def test_all_providers_exported(self):
        """Test that all providers can be imported."""
        from business_analyzer.ai.providers import (
            AnthropicProvider,
            GrokProvider,
            OllamaProvider,
            OpenAIProvider,
        )

        assert GrokProvider is not None
        assert OpenAIProvider is not None
        assert AnthropicProvider is not None
        assert OllamaProvider is not None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
