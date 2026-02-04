from hexagon_core.circuit_breaker.core import CircuitBreaker, CircuitBreakerConfig


def test_before_call_closed_always_allowed():
    cb = CircuitBreaker("test", CircuitBreakerConfig())
    assert cb.before_call() is True
    assert cb.before_call() is True
