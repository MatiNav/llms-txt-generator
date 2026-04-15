import json
import logging
from datetime import datetime, timezone
from typing import Any


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "message": record.getMessage(),
            "logger": record.name,
        }

        extra_fields = getattr(record, "event_fields", None)
        if isinstance(extra_fields, dict):
            payload.update(extra_fields)

        try:
            return json.dumps(payload)
        except (TypeError, ValueError):
            return json.dumps(payload, default=str)


def configure_json_logging(level: str = "INFO") -> None:
    json_handler = logging.StreamHandler()
    json_handler.setFormatter(JsonFormatter())

    root_logger = logging.getLogger()
    root_logger.handlers = [json_handler]
    root_logger.setLevel(level)


def log_event(
    logger: logging.Logger, level: int, event_name: str, **fields: Any
) -> None:
    logger.log(
        level,
        event_name,
        extra={"event_fields": {"event_name": event_name, **fields}},
    )


def log_decision(
    logger: logging.Logger,
    *,
    decision_name: str,
    reason: str,
    level: int = logging.INFO,
    **fields: Any,
) -> None:
    log_event(
        logger,
        level,
        "decision.made",
        decision_name=decision_name,
        reason=reason,
        **fields,
    )
