"""
Tests for AI stability features: Circuit Breakers and Retries.
"""

import sys

# Ensure src is in path
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

src_path = str(Path(__file__).parent.parent.parent / "src")
if src_path not in sys.path:
    sys.path.insert(0, src_path)

from business_analyzer.ai.circuit_breaker import (
    CircuitBreaker,
    CircuitBreakerError,
    CircuitState,
)


class TestStability:
    """Test suite for circuit breaker and retry logic."""

    def test_circuit_breaker_opening(self):
        """Test that circuit breaker opens after threshold failures."""
        breaker = CircuitBreaker("test", failure_threshold=2, recovery_timeout=60)

        @breaker
        def failing_func():
            raise ValueError("Failure")

        # First failure
        with pytest.raises(ValueError):
            failing_func()
        assert breaker.state == CircuitState.CLOSED
        assert breaker.failures == 1

        # Second failure (threshold reached)
        with pytest.raises(ValueError):
            failing_func()
        assert breaker.state == CircuitState.OPEN
        assert breaker.failures == 2

        # Subsequent call should raise CircuitBreakerError immediately
        with pytest.raises(CircuitBreakerError):
            failing_func()

    def test_circuit_breaker_recovery(self):
        """Test that circuit breaker recovers after timeout."""
        # Short timeout for testing
        breaker = CircuitBreaker("test", failure_threshold=1, recovery_timeout=0.1)

        @breaker
        def failing_func():
            raise ValueError("Failure")

        # Open the circuit
        with pytest.raises(ValueError):
            failing_func()
        assert breaker.state == CircuitState.OPEN

        # Wait for timeout
        import time

        time.sleep(0.2)

        # Should be HALF_OPEN and allow a trial
        @breaker
        def success_func():
            return "Success"

        assert success_func() == "Success"
        assert breaker.state == CircuitState.CLOSED
        assert breaker.failures == 0

    def test_retry_logic(self):
        """Test the retry_on_failure decorator."""
        from business_analyzer.ai.base import retry_on_failure

        call_count = 0

        @retry_on_failure(max_attempts=3, delay=0.01)
        def test_retry():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise ValueError(f"Fail {call_count}")
            return "Success"

        result = test_retry()
        assert result == "Success"
        assert call_count == 3


if __name__ == "__main__":
    # If pytest is available, use it
    try:
        import pytest

        sys.exit(pytest.main([__file__, "-v"]))
    except ImportError:
        # Simple manual execution if pytest is not available
        print("Running tests manually...")
        test_class = TestStability()

        print("Testing circuit breaker opening...")
        test_class.test_circuit_breaker_opening()
        print("✅ Passed")

        print("Testing circuit breaker recovery...")
        test_class.test_circuit_breaker_recovery()
        print("✅ Passed")

        print("Testing retry logic...")
        test_class.test_retry_logic()
        print("✅ Passed")

        print("\n✨ ALL TESTS PASSED!")
