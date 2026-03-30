"""Utility helpers for Samsung Chat QA."""
from __future__ import annotations

import re
import unicodedata
from datetime import datetime, timezone
from pathlib import Path
from typing import List


def now_utc_str(fmt: str = "%Y%m%d_%H%M%S") -> str:
    """Return the current UTC time as a formatted string.

    Parameters
    ----------
    fmt:
        ``strftime``-compatible format string.
    """
    return datetime.now(tz=timezone.utc).strftime(fmt)


def build_screenshot_name(case_id: str) -> str:
    """Build a screenshot base name: ``YYYYMMDD_HHMMSS_<case_id>``.

    Special characters in *case_id* are replaced with underscores to keep
    the filename safe on all platforms.
    """
    safe_id = re.sub(r"[^\w-]", "_", case_id)
    return f"{now_utc_str()}_{safe_id}"


def safe_text(text: str) -> str:
    """Normalise *text* to NFC Unicode and strip leading/trailing whitespace."""
    return unicodedata.normalize("NFC", text).strip()


def contains_any(text: str, keywords: List[str]) -> bool:
    """Return ``True`` if *text* contains at least one keyword (case-insensitive)."""
    lower = text.lower()
    return any(kw.lower() in lower for kw in keywords if kw)


def contains_none(text: str, keywords: List[str]) -> bool:
    """Return ``True`` if *text* contains *none* of the forbidden keywords."""
    return not contains_any(text, keywords)


def get_project_root() -> Path:
    """Return the absolute path of the project root directory."""
    return Path(__file__).resolve().parent.parent


def ensure_dir(path: Path) -> Path:
    """Create *path* (and any missing parents) and return it."""
    path.mkdir(parents=True, exist_ok=True)
    return path
