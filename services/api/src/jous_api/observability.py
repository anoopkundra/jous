"""Structured application logs with deliberately bounded, non-sensitive fields."""

import json
import logging
from contextvars import ContextVar
from datetime import datetime, timezone

from .config import Settings

request_id: ContextVar[str | None] = ContextVar("jous_request_id", default=None)


class JsonFormatter(logging.Formatter):
    def __init__(self, settings: Settings):
        super().__init__()
        self.settings = settings

    def format(self, record):
        # Never serialize arbitrary messages, arguments, exception text or extras.
        event = getattr(record, "event", "application_event")
        if event not in {"startup", "shutdown", "request_complete", "request_failed",
                         "database_unavailable"}:
            event = "application_event"
        result = {
            "timestamp": datetime.fromtimestamp(record.created, timezone.utc).isoformat(),
            "severity": record.levelname,
            "service": self.settings.service_name,
            "environment": self.settings.environment,
            "event": event,
            "request_id": request_id.get(),
        }
        status = getattr(record, "status_code", None)
        if isinstance(status, int) and 100 <= status <= 599:
            result["status_code"] = status
        return json.dumps(result)


def application_logger(settings: Settings) -> logging.Logger:
    # An app-owned logger avoids changing host/Uvicorn/global logging configuration.
    logger = logging.Logger(settings.service_name, level=settings.log_level)
    handler = logging.StreamHandler()
    handler.setFormatter(JsonFormatter(settings))
    logger.addHandler(handler)
    logger.propagate = False
    return logger
