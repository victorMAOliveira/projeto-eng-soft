"""Structured JSON logging: one JSON document per line on stdout."""

import json
import logging
import sys
from datetime import UTC, datetime

from eh_observability.context import get_correlation_id

_RESERVED = set(vars(logging.makeLogRecord({}))) | {"message", "asctime", "taskName"}


class JsonFormatter(logging.Formatter):
    """Render log records as single-line JSON including service and correlation id.

    Any ``extra={...}`` passed to the logger is merged into the document, so
    callers can attach structured fields (``event_id``, ``duration_ms``...).
    """

    def __init__(self, service_name: str) -> None:
        super().__init__()
        self.service_name = service_name

    def format(self, record: logging.LogRecord) -> str:
        """Serialise ``record`` to JSON."""
        doc: dict[str, object] = {
            "ts": datetime.fromtimestamp(record.created, UTC).isoformat(),
            "level": record.levelname,
            "service": self.service_name,
            "logger": record.name,
            "message": record.getMessage(),
        }
        correlation_id = get_correlation_id()
        if correlation_id:
            doc["correlation_id"] = correlation_id
        for key, value in record.__dict__.items():
            if key not in _RESERVED and not key.startswith("_"):
                doc[key] = value
        if record.exc_info:
            doc["exc_info"] = self.formatException(record.exc_info)
        return json.dumps(doc, default=str, ensure_ascii=False)


def configure_logging(service_name: str, level: str = "INFO") -> logging.Logger:
    """Route all logging (including uvicorn's) through :class:`JsonFormatter`.

    Returns the logger named after the service, ready to use.
    """
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter(service_name))
    root = logging.getLogger()
    root.handlers[:] = [handler]
    root.setLevel(level.upper())
    for name in ("uvicorn", "uvicorn.error", "uvicorn.access"):
        uvicorn_logger = logging.getLogger(name)
        uvicorn_logger.handlers[:] = []
        uvicorn_logger.propagate = True
    for noisy in ("aiormq", "aio_pika", "httpx", "httpcore", "apscheduler"):
        logging.getLogger(noisy).setLevel(logging.WARNING)
    return logging.getLogger(service_name)
