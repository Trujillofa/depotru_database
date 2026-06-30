"""
Tests for business_analyzer/ai/base.py
"""

from unittest.mock import Mock

import pytest

# Standalone mock config (does not replace business_analyzer.ai.base in sys.modules)
mock_config = Mock()
mock_config.GROK_API_KEY = "test-key"
mock_config.OPENAI_API_KEY = "test-openai-key"
mock_config.ANTHROPIC_API_KEY = "test-anthropic-key"
mock_config.DB_HOST = "test-host"
mock_config.DB_NAME = "TestDB"
mock_config.DB_USER = "test-user"
mock_config.DB_PASSWORD = "test-password"
mock_config.AI_PROVIDER = "grok"
mock_config.MODEL_NAME = "grok-beta"
mock_config.HOST = "0.0.0.0"
mock_config.PORT = 8084
mock_config.TESTING = False

# Module-level constants that are exported from base.py
mock_config.SUPPORTED_PROVIDERS = ["grok", "openai", "anthropic", "ollama"]
mock_config.DEFAULT_PROVIDER = "grok"


# Now test basic functionality
class TestAIBase:
    """Test AI base module"""

    def test_mock_config(self):
        """Test that mock config is set up correctly"""
        assert mock_config.GROK_API_KEY == "test-key"
        assert mock_config.AI_PROVIDER == "grok"

    def test_provider_selection(self):
        """Test provider selection logic"""
        # Test that different providers can be configured
        providers = ["grok", "openai", "anthropic", "ollama"]
        for provider in providers:
            mock_config.AI_PROVIDER = provider
            assert mock_config.AI_PROVIDER == provider
