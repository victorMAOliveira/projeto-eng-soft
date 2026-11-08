"""eh_observability — observability building blocks shared by EstágioHub services.

Public interface:

* :func:`configure_logging` / :class:`JsonFormatter` — structured JSON logs.
* :class:`ObservabilityMiddleware` — correlation-id propagation, ``X-Served-By``
  header and access logs.
* :func:`get_correlation_id` / :func:`set_correlation_id` — context helpers.
* :func:`create_health_router` — ``/health``, ``/ready`` and ``/version``.
* :func:`setup_observability` — one call that wires everything into an app.
"""

from eh_observability.context import (
    CORRELATION_HEADER,
    SERVED_BY_HEADER,
    get_correlation_id,
    set_correlation_id,
)
from eh_observability.health import Check, create_health_router
from eh_observability.logging import JsonFormatter, configure_logging
from eh_observability.middleware import ObservabilityMiddleware
from eh_observability.setup import setup_observability

__version__ = "0.1.0"

__all__ = [
    "CORRELATION_HEADER",
    "SERVED_BY_HEADER",
    "Check",
    "JsonFormatter",
    "ObservabilityMiddleware",
    "configure_logging",
    "create_health_router",
    "get_correlation_id",
    "set_correlation_id",
    "setup_observability",
]
