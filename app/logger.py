"""Logging setup: console + rotating file handler, duplicate handler prevention."""

from __future__ import annotations

import logging
import sys
from pathlib import Path


def setup_logger(name: str = "samsung_qa", log_dir: Path | None = None) -> logging.Logger:
    """Configure and return the application logger.

    Writes to both stdout and ``reports/runtime.log``.
    Safe to call multiple times – duplicate handlers are prevented.
    """
    logger = logging.getLogger(name)
    if logger.handlers:
        # Already configured; return as-is
        return logger

    logger.setLevel(logging.DEBUG)

    fmt = logging.Formatter(
        fmt="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%dT%H:%M:%S",
    )

    # Console handler (INFO and above)
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(fmt)
    logger.addHandler(console_handler)

    # File handler (DEBUG and above)
    if log_dir is None:
        log_dir = Path(__file__).parent.parent / "reports"
    log_dir.mkdir(parents=True, exist_ok=True)
    log_file = log_dir / "runtime.log"

    file_handler = logging.FileHandler(log_file, encoding="utf-8")
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(fmt)
    logger.addHandler(file_handler)

    # Prevent messages from propagating to the root logger
    logger.propagate = False

    return logger


# Module-level convenience instance
logger = setup_logger()
