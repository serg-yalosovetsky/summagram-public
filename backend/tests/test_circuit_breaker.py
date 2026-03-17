"""Unit tests for LLMCircuitBreaker — threshold-based tripping."""

import time
from unittest.mock import MagicMock

import pytest

# Ensure imports resolve when running from backend/tests/
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from backend.models import ModelNotReadyError

pytestmark = pytest.mark.unit


# --- Isolated LLMCircuitBreaker tests (re-import to avoid module side effects) ---


def _make_breaker(cooldown: float = 15.0, threshold: int = 3):
    """Create a fresh LLMCircuitBreaker instance."""
    from backend.service import LLMCircuitBreaker

    return LLMCircuitBreaker(cooldown=cooldown, threshold=threshold)


class TestCircuitBreakerThreshold:
    """Circuit breaker should NOT trip on fewer than `threshold` failures."""

    def test_single_failure_does_not_trip(self) -> None:
        cb = _make_breaker(threshold=3)
        cb.record_failure()
        # Should NOT raise
        cb.check()

    def test_two_failures_do_not_trip(self) -> None:
        cb = _make_breaker(threshold=3)
        cb.record_failure()
        cb.record_failure()
        cb.check()

    def test_trips_after_threshold(self) -> None:
        cb = _make_breaker(threshold=3, cooldown=60.0)
        for _ in range(3):
            cb.record_failure()
        with pytest.raises(ModelNotReadyError, match="3 consecutive failures"):
            cb.check()

    def test_resets_on_success(self) -> None:
        cb = _make_breaker(threshold=3)
        cb.record_failure()
        cb.record_failure()
        cb.record_success()
        # Counter should be 0 now
        cb.record_failure()
        cb.check()  # Only 1 failure — should NOT trip

    def test_cooldown_expiry_resets(self) -> None:
        cb = _make_breaker(threshold=1, cooldown=0.01)
        cb.record_failure()
        time.sleep(0.02)
        # Cooldown expired — check() should auto-reset and pass
        cb.check()


class TestIsTransient:
    """LLMCircuitBreaker.is_transient should detect transient 503 errors."""

    def test_transient_503(self) -> None:
        from backend.service import LLMCircuitBreaker

        exc = MagicMock()
        exc.status_code = 503
        # Patch isinstance check
        import openai

        real_exc = openai.APIStatusError.__new__(openai.APIStatusError)
        real_exc.status_code = 503
        assert LLMCircuitBreaker.is_transient(real_exc) is True

    def test_non_transient_500(self) -> None:
        from backend.service import LLMCircuitBreaker
        import openai

        real_exc = openai.APIStatusError.__new__(openai.APIStatusError)
        real_exc.status_code = 500
        assert LLMCircuitBreaker.is_transient(real_exc) is False

    def test_generic_exception_not_transient(self) -> None:
        from backend.service import LLMCircuitBreaker

        assert LLMCircuitBreaker.is_transient(RuntimeError("boom")) is False
