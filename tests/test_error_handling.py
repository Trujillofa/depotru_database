#!/usr/bin/env python3
"""
Tests for error handling and retry logic.
"""

import pytest
import time
from unittest.mock import Mock, patch


class TestRetryDecorator:
    """Test retry_on_failure decorator"""

    def test_retry_decorator_success_first_try(self):
        """Test that successful function executes once"""
        try:
            from src.vanna_grok import retry_on_failure
        except ImportError:
            pytest.skip("vanna_grok not available")
            return

        call_count = 0

        @retry_on_failure(max_attempts=3, delay=0.1)
        def successful_function():
            nonlocal call_count
            call_count += 1
            return "success"

        result = successful_function()
        assert result == "success"
        assert call_count == 1

    def test_retry_decorator_fails_then_succeeds(self):
        """Test that function retries on failure then succeeds"""
        try:
            from src.vanna_grok import retry_on_failure
        except ImportError:
            pytest.skip("vanna_grok not available")
            return

        call_count = 0

        @retry_on_failure(max_attempts=3, delay=0.1, backoff=1)
        def flaky_function():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise Exception("Temporary failure")
            return "success"

        result = flaky_function()
        assert result == "success"
        assert call_count == 3

    def test_retry_decorator_max_attempts_exceeded(self):
        """Test that function raises after max attempts"""
        try:
            from src.vanna_grok import retry_on_failure
        except ImportError:
            pytest.skip("vanna_grok not available")
            return

        call_count = 0

        @retry_on_failure(max_attempts=3, delay=0.1, backoff=1)
        def always_fails():
            nonlocal call_count
            call_count += 1
            raise Exception("Permanent failure")

        with pytest.raises(Exception, match="Permanent failure"):
            always_fails()

        assert call_count == 3

    def test_retry_exponential_backoff(self):
        """Test that retry delay increases exponentially"""
        try:
            from src.vanna_grok import retry_on_failure
        except ImportError:
            pytest.skip("vanna_grok not available")
            return

        call_times = []

        @retry_on_failure(max_attempts=3, delay=0.1, backoff=2)
        def timing_function():
            call_times.append(time.time())
            if len(call_times) < 3:
                raise Exception("Retry me")
            return "done"

        timing_function()

        # Check delays between calls
        if len(call_times) >= 3:
            delay1 = call_times[1] - call_times[0]
            delay2 = call_times[2] - call_times[1]

            # Second delay should be roughly 2x first delay (exponential backoff)
            # Allow some tolerance for execution time
            assert delay2 >= delay1 * 1.5


class TestSecurityValidation:
    """Test security and validation functions"""

    def test_require_env_missing_variable(self):
        """Test that require_env exits on missing variable"""
        try:
            from src.vanna_grok import require_env
        except ImportError:
            pytest.skip("vanna_grok not available")
            return

        # Test with non-existent variable
        with patch.dict('os.environ', {}, clear=True):
            with pytest.raises(SystemExit):
                require_env("NONEXISTENT_VAR")

    def test_require_env_validation_function(self):
        """Test that require_env validates correctly"""
        try:
            from src.vanna_grok import require_env
        except ImportError:
            pytest.skip("vanna_grok not available")
            return

        # Test with validation function
        with patch.dict('os.environ', {'TEST_VAR': 'valid_value'}):
            result = require_env('TEST_VAR', validation_func=lambda x: x.startswith('valid'))
            assert result == 'valid_value'

        # Test with failing validation
        with patch.dict('os.environ', {'TEST_VAR': 'invalid_value'}):
            with pytest.raises(SystemExit):
                require_env('TEST_VAR', validation_func=lambda x: x.startswith('valid'))


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
