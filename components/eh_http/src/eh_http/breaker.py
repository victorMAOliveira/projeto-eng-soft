"""A small, dependency-free circuit breaker (closed → open → half-open)."""

import time
from collections.abc import Callable
from enum import StrEnum


class CircuitState(StrEnum):
    """Possible states of a :class:`CircuitBreaker`."""

    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


class CircuitBreaker:
    """Stop calling an upstream after consecutive failures, then probe it again.

    * **closed** — requests flow; consecutive failures are counted.
    * **open** — after ``failure_threshold`` failures requests are refused
      immediately for ``recovery_timeout`` seconds (fail fast).
    * **half-open** — one trial request is allowed; success closes the
      circuit, failure opens it again.
    """

    def __init__(
        self,
        failure_threshold: int = 5,
        recovery_timeout: float = 15.0,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        if failure_threshold < 1:
            raise ValueError("failure_threshold must be >= 1")
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self._clock = clock
        self._failures = 0
        self._opened_at: float | None = None

    @property
    def state(self) -> CircuitState:
        """Current state, moving from open to half-open once the timeout elapsed."""
        if self._opened_at is None:
            return CircuitState.CLOSED
        if self._clock() - self._opened_at >= self.recovery_timeout:
            return CircuitState.HALF_OPEN
        return CircuitState.OPEN

    @property
    def failures(self) -> int:
        """Number of consecutive failures recorded."""
        return self._failures

    def allow_request(self) -> bool:
        """Return ``True`` when a request may be attempted."""
        return self.state is not CircuitState.OPEN

    def record_success(self) -> None:
        """Reset the breaker after a successful call."""
        self._failures = 0
        self._opened_at = None

    def record_failure(self) -> None:
        """Count a failure and open the circuit when the threshold is reached."""
        self._failures += 1
        if self.state is CircuitState.HALF_OPEN or self._failures >= self.failure_threshold:
            self._opened_at = self._clock()
