"""
Circuit Breaker implementation for AI API calls.

Prevents cascading failures by stopping calls to a service that is failing.
"""

import time
from enum import Enum
from functools import wraps
from typing import Callable, Dict, Optional


class CircuitState(Enum):
    CLOSED = "closed"  # Normal operation
    OPEN = "open"  # Failing, stop calls
    HALF_OPEN = "half_open"  # Testing if service recovered


class CircuitBreaker:
    """
    Circuit Breaker pattern implementation.

    States:
    - CLOSED: Calls pass through. Failures increment a counter.
    - OPEN: Calls fail immediately with a CircuitBreakerError.
    - HALF_OPEN: A single trial call is allowed.
    """

    def __init__(
        self,
        name: str,
        failure_threshold: int = 5,
        recovery_timeout: int = 60,
        expected_exception: type = Exception,
    ):
        self.name = name
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.expected_exception = expected_exception

        self.state = CircuitState.CLOSED
        self.failures = 0
        self.last_failure_time: Optional[float] = None

    def _on_failure(self):
        self.failures += 1
        self.last_failure_time = time.time()

        if self.failures >= self.failure_threshold:
            print(
                f"🔴 Circuit Breaker [{self.name}] OPENED after {self.failures} failures."
            )
            self.state = CircuitState.OPEN

    def _on_success(self):
        if self.state != CircuitState.CLOSED:
            print(f"🟢 Circuit Breaker [{self.name}] CLOSED (recovered).")

        self.state = CircuitState.CLOSED
        self.failures = 0
        self.last_failure_time = None

    def __call__(self, func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            # Check state
            if self.state == CircuitState.OPEN:
                if (
                    self.last_failure_time is not None
                    and time.time() - self.last_failure_time > self.recovery_timeout
                ):
                    print(
                        f"🟡 Circuit Breaker [{self.name}] HALF-OPEN (testing recovery)."
                    )
                    self.state = CircuitState.HALF_OPEN
                else:
                    raise CircuitBreakerError(f"Circuit Breaker [{self.name}] is OPEN.")

            try:
                result = func(*args, **kwargs)
                self._on_success()
                return result
            except Exception as e:
                self._on_failure()
                raise e

        return wrapper


class CircuitBreakerError(Exception):
    """Exception raised when the circuit is open."""

    pass


# Shared circuit breakers for different providers
breakers: Dict[str, CircuitBreaker] = {
    "grok": CircuitBreaker("grok", failure_threshold=3, recovery_timeout=30),
    "openai": CircuitBreaker("openai", failure_threshold=3, recovery_timeout=30),
    "anthropic": CircuitBreaker("anthropic", failure_threshold=3, recovery_timeout=30),
    "ollama": CircuitBreaker("ollama", failure_threshold=5, recovery_timeout=15),
}


def with_circuit_breaker(provider_name: str):
    """Decorator to use a named circuit breaker."""

    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            breaker = breakers.get(provider_name)
            if not breaker:
                return func(*args, **kwargs)
            return breaker(func)(*args, **kwargs)

        return wrapper

    return decorator
