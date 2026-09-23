"""Structured logging configuration for the OSINT Intelligence Component."""

import logging
import sys
from typing import Any


class SensitiveDataFilter(logging.Filter):
    """Filter out sensitive credentials and tokens from logs."""

    SENSITIVE_KEYS = ("api_key", "apikey", "authorization", "secret", "password", "token")

    def filter(self, record: logging.LogRecord) -> bool:
        msg = str(record.msg).lower()
        for key in self.SENSITIVE_KEYS:
            if key in msg:
                # If a log contains sensitive markers, sanitize it
                record.msg = "[SANITIZED LOG ENTRY CONTAINING SENSITIVE DATA]"
                break
        return True


def setup_logging(log_level: str = "INFO") -> logging.Logger:
    """Configure structured logging for the application."""
    logger = logging.getLogger("osint_component")
    level = getattr(logging, log_level.upper(), logging.INFO)
    logger.setLevel(level)

    # Avoid duplicate handlers if already configured
    if not logger.handlers:
        handler = logging.StreamHandler(sys.stdout)
        handler.setLevel(level)
        formatter = logging.Formatter(
            fmt="%(asctime)s [%(levelname)s] [%(name)s] %(message)s",
            datefmt="%Y-%m-%dT%H:%M:%SZ",
        )
        handler.setFormatter(formatter)
        handler.addFilter(SensitiveDataFilter())
        logger.addHandler(handler)

    logger.propagate = False
    return logger


logger = setup_logging()
