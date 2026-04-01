"""Logging configuration for Samsung Chat QA.

Sets up a root logger that writes to *both* the console and a rotating file
at ``reports/runtime.log``.  Duplicate handlers are prevented so that the
function is safe to call multiple times (e.g. in tests).
"""
from __future__ import annotations

import logging
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path

_LOG_FORMAT = "%(asctime)s [%(levelname)-8s] %(name)s - %(message)s"
_DATE_FORMAT = "%Y-%m-%dT%H:%M:%S"
_LOGGER_NAME = "samsung_chat_qa"


def setup_logger(log_file: Path | None = None) -> logging.Logger:
    """Configure and return the application logger.

    Parameters
    ----------
    log_file:
        Absolute path to the log file.  When *None* the default
        ``reports/runtime.log`` (relative to this file's project root) is used.
    """
    logger = logging.getLogger(_LOGGER_NAME)

    # Return early if handlers are already attached (prevents duplication).
    if logger.handlers:
        return logger

    logger.setLevel(logging.DEBUG)
    formatter = logging.Formatter(_LOG_FORMAT, datefmt=_DATE_FORMAT)

    # --- Console handler ---
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    # --- File handler ---
    if log_file is None:
        log_file = Path(__file__).resolve().parent.parent / "reports" / "runtime.log"

    log_file.parent.mkdir(parents=True, exist_ok=True)
    file_handler = RotatingFileHandler(
        log_file,
        maxBytes=10 * 1024 * 1024,  # 10 MB
        backupCount=5,
        encoding="utf-8",
    )
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    # Prevent propagation to the root logger to avoid duplicate console output.
    logger.propagate = False

    return logger


def get_logger(name: str = _LOGGER_NAME) -> logging.Logger:
    """Return a child logger.  Call :func:`setup_logger` once before this."""
    return logging.getLogger(name)
