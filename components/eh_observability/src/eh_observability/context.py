"""Request-scoped context (correlation id) shared by logs, HTTP clients and events."""

from contextvars import ContextVar, Token

CORRELATION_HEADER = "X-Correlation-ID"
SERVED_BY_HEADER = "X-Served-By"

_correlation_id: ContextVar[str | None] = ContextVar("correlation_id", default=None)


def get_correlation_id() -> str | None:
    """Return the correlation id bound to the current task, if any."""
    return _correlation_id.get()


def set_correlation_id(value: str | None) -> Token:
    """Bind ``value`` as the current correlation id and return the reset token."""
    return _correlation_id.set(value)


def reset_correlation_id(token: Token) -> None:
    """Restore the correlation id that was active before :func:`set_correlation_id`."""
    _correlation_id.reset(token)
