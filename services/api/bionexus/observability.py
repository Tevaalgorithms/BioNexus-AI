"""Structured JSON logs with opaque ids only (OPS-01). Content and credentials are never logged."""

import json
import logging
import re
import sys
from datetime import UTC, datetime

SENSITIVE = re.compile(r"(authorization|token|secret|password|api[_-]?key|passage|prompt)", re.I)
ALLOWED_FIELDS = frozenset(
    {"run_id", "tenant", "agent", "stage", "status", "latency_ms", "cost_usd", "error_category"}
)


def redact(fields: dict) -> dict:
    """Keep only known-safe field names; drop anything that looks sensitive."""
    return {k: v for k, v in fields.items() if k in ALLOWED_FIELDS and not SENSITIVE.search(k)}


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        entry = {
            "ts": datetime.now(UTC).isoformat(),
            "level": record.levelname,
            "event": record.getMessage(),
            **redact(getattr(record, "fields", {})),
        }
        return json.dumps(entry)


def configure_logging(level: str = "INFO") -> logging.Logger:
    logger = logging.getLogger("bionexus")
    if not logger.handlers:
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(JsonFormatter())
        logger.addHandler(handler)
    logger.setLevel(level)
    logger.propagate = False
    return logger


def log_event(event: str, **fields) -> None:
    logging.getLogger("bionexus").info(event, extra={"fields": fields})
