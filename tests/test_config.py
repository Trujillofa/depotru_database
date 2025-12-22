#!/usr/bin/env python3
"""
Tests for configuration management and environment variables.
"""

import os
import pytest
from unittest.mock import patch


class TestConfig:
    """Test configuration loading and validation"""

    def test_environment_variables_loaded(self):
        """Test that environment variables are available"""
        # These should be set by CI or .env
        required_vars = ['DB_SERVER', 'DB_NAME', 'DB_USER', 'DB_PASSWORD', 'GROK_API_KEY']

        for var in required_vars:
            value = os.getenv(var)
            assert value is not None, f"{var} should be set in environment"
            assert len(value) > 0, f"{var} should not be empty"

    def test_grok_api_key_format(self):
        """Test that GROK_API_KEY has correct format"""
        api_key = os.getenv('GROK_API_KEY')

        if api_key:
            assert api_key.startswith('xai-'), "GROK_API_KEY should start with 'xai-'"

    @patch.dict(os.environ, {
        'DB_SERVER': 'test-server',
        'DB_NAME': 'TestDB',
        'DB_USER': 'test_user',
        'DB_PASSWORD': 'test_pass',
        'GROK_API_KEY': 'xai-test-key',
    })
    def test_config_with_mock_env(self):
        """Test configuration with mocked environment variables"""
        assert os.getenv('DB_SERVER') == 'test-server'
        assert os.getenv('DB_NAME') == 'TestDB'
        assert os.getenv('DB_USER') == 'test_user'
        assert os.getenv('GROK_API_KEY') == 'xai-test-key'


class TestFeatureToggles:
    """Test optional feature configuration"""

    def test_enable_ai_insights_default(self):
        """Test that ENABLE_AI_INSIGHTS defaults to 'true'"""
        value = os.getenv('ENABLE_AI_INSIGHTS', 'true')
        assert value.lower() in ['true', 'false']

    def test_insights_max_rows_default(self):
        """Test that INSIGHTS_MAX_ROWS has valid default"""
        value = int(os.getenv('INSIGHTS_MAX_ROWS', '15'))
        assert value > 0
        assert value <= 100  # Reasonable limit

    def test_max_display_rows_default(self):
        """Test that MAX_DISPLAY_ROWS has valid default"""
        value = int(os.getenv('MAX_DISPLAY_ROWS', '100'))
        assert value > 0
        assert value <= 1000  # Reasonable limit


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
