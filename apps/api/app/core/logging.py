"""Centralised logging configuration.

Call ``configure_logging()`` once during application startup.
Use ``get_logger(__name__)`` everywhere else instead of ``print()``.
"""

from __future__ import annotations

import logging
import sys
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    pass


def configure_logging(log_level: str = "INFO", *, json_logs: bool = False) -> None:
    """Configure the root logger for the application.

    Args:
        log_level: Desired log level string (e.g. "INFO", "DEBUG").
        json_logs: When True, emit JSON-structured lines (for staging/production).
                   When False, emit human-readable lines (for development).
    """
    level = getattr(logging, log_level.upper(), logging.INFO)

    if json_logs:
        fmt = (
            '{"time": "%(asctime)s", "level": "%(levelname)s", '
            '"logger": "%(name)s", "message": %(message)r}'
        )
    else:
        fmt = "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(logging.Formatter(fmt, datefmt="%Y-%m-%dT%H:%M:%S"))

    root = logging.getLogger()
    root.setLevel(level)
    root.handlers.clear()
    root.addHandler(handler)

    # Suppress uvicorn's own access log — our middleware handles it.
    logging.getLogger("uvicorn.access").propagate = False
    logging.getLogger("uvicorn.access").handlers.clear()

    # Keep uvicorn error log but respect the configured level.
    logging.getLogger("uvicorn.error").setLevel(level)

    # SQLAlchemy engine log is very verbose; only show at DEBUG.
    logging.getLogger("sqlalchemy.engine").setLevel(
        logging.DEBUG if log_level.upper() == "DEBUG" else logging.WARNING
    )


def get_logger(name: str) -> logging.Logger:
    """Return a named logger.

    Usage::

        from app.core.logging import get_logger
        logger = get_logger(__name__)
        logger.info("Something happened", extra={"key": "value"})
    """
    return logging.getLogger(name)
