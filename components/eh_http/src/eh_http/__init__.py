"""eh_http — resilient synchronous (REST) communication between EstágioHub services.

Public interface:

* :class:`ResilientClient` — ``httpx.AsyncClient`` wrapper with timeout,
  retry with exponential backoff and a per-upstream circuit breaker.
* :class:`CircuitBreaker` / :class:`CircuitState` — the breaker itself.
* :class:`CircuitOpenError` / :class:`UpstreamUnavailableError` — failures
  raised when an upstream cannot be used, so callers can degrade gracefully.
"""

from eh_http.breaker import CircuitBreaker, CircuitState
from eh_http.client import CircuitOpenError, ResilientClient, UpstreamUnavailableError

__version__ = "0.1.0"

__all__ = [
    "CircuitBreaker",
    "CircuitOpenError",
    "CircuitState",
    "ResilientClient",
    "UpstreamUnavailableError",
]
