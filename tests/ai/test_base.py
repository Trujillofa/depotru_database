"""
Tests for AI package base module.
"""

import os
import sys

import pytest

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../src"))

from business_analyzer.ai.base import (
    DEFAULT_PROVIDER,
    SUPPORTED_PROVIDERS,
    Config,
    create_ai_client,
    get_env_or_test_default,
    require_env,
    retry_on_failure,
)


class TestConfig:
    """Test configuration."""

    def test_supported_providers(self):
        """Test that supported providers are defined."""
        assert "grok" in SUPPORTED_PROVIDERS
        assert "openai" in SUPPORTED_PROVIDERS
        assert "anthropic" in SUPPORTED_PROVIDERS
        assert "ollama" in SUPPORTED_PROVIDERS

    def test_default_provider(self):
        """Test default provider."""
        assert DEFAULT_PROVIDER == "grok"

    def test_config_has_required_attributes(self):
        """Test that Config has required attributes."""
        assert hasattr(Config, "AI_PROVIDER")
        assert hasattr(Config, "GROK_API_KEY")
        assert hasattr(Config, "OPENAI_API_KEY")
        assert hasattr(Config, "ANTHROPIC_API_KEY")
        assert hasattr(Config, "OLLAMA_HOST")
        assert hasattr(Config, "OLLAMA_MODEL")
        assert hasattr(Config, "DB_SERVER")
        assert hasattr(Config, "DB_NAME")
        assert hasattr(Config, "DB_USER")
        assert hasattr(Config, "DB_PASSWORD")


class TestRetryOnFailure:
    """Test retry decorator."""

    def test_retry_success(self):
        """Test that retry works on success."""
        call_count = 0

        @retry_on_failure(max_attempts=3, delay=0.1)
        def success_func():
            nonlocal call_count
            call_count += 1
            return "success"

        result = success_func()
        assert result == "success"
        assert call_count == 1

    def test_retry_eventual_success(self):
        """Test that retry works with eventual success."""
        call_count = 0

        @retry_on_failure(max_attempts=3, delay=0.1)
        def eventual_success():
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise Exception("Temporary failure")
            return "success"

        result = eventual_success()
        assert result == "success"
        assert call_count == 2


class TestCreateAIClient:
    """Test AI client creation."""

    def test_create_grok_client(self):
        """Test creating Grok client."""
        # This will use test defaults in testing mode
        # Skip if OpenAI is not installed
        try:
            from openai import OpenAI
        except ImportError:
            pytest.skip("OpenAI not installed")
        client, config, provider_type = create_ai_client("grok")
        assert provider_type == "openai"
        assert "model" in config
        assert "base_url" in config

    def test_create_openai_client(self):
        """Test creating OpenAI client."""
        # Skip if OpenAI is not installed
        try:
            from openai import OpenAI
        except ImportError:
            pytest.skip("OpenAI not installed")
        client, config, provider_type = create_ai_client("openai")
        assert provider_type == "openai"
        assert "model" in config
        assert "api_key" in config

    def test_create_anthropic_client(self):
        """Test creating Anthropic client."""
        client, config, provider_type = create_ai_client("anthropic")
        assert provider_type == "anthropic"
        assert "model" in config
        assert "api_key" in config
        assert client is None  # Anthropic doesn't use OpenAI client

    def test_create_ollama_client(self):
        """Test creating Ollama client."""
        client, config, provider_type = create_ai_client("ollama")
        assert provider_type == "ollama"
        assert "model" in config
        assert "ollama_host" in config
        assert client is None  # Ollama doesn't use OpenAI client


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
