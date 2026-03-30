"""Utility helpers: timestamps, path creation, keyword checks, text normalisation."""

from __future__ import annotations

import re
import unicodedata
from datetime import datetime, timezone
from pathlib import Path
from typing import List


def utc_now_str(fmt: str = "%Y%m%d_%H%M%S") -> str:
    """Return the current UTC time as a formatted string."""
    return datetime.now(tz=timezone.utc).strftime(fmt)


def iso_utc_now() -> str:
    """Return the current UTC time in ISO-8601 format."""
    return datetime.now(tz=timezone.utc).isoformat(timespec="seconds")


def ensure_dir(path: Path) -> Path:
    """Create *path* (and parents) if it does not exist, then return it."""
    path.mkdir(parents=True, exist_ok=True)
    return path


def safe_normalize(text: str) -> str:
    """Normalize Unicode text and collapse whitespace."""
    text = unicodedata.normalize("NFKC", text)
    return re.sub(r"\s+", " ", text).strip()


def contains_any_keyword(text: str, keywords: List[str]) -> bool:
    """Return *True* if *text* contains at least one of *keywords* (case-insensitive)."""
    lower = text.lower()
    return any(kw.lower() in lower for kw in keywords)


def contains_forbidden_keyword(text: str, keywords: List[str]) -> bool:
    """Return *True* if *text* contains any forbidden keyword (case-insensitive)."""
    return contains_any_keyword(text, keywords)


def screenshot_name(case_id: str, suffix: str = "") -> str:
    """Generate a timestamped screenshot filename.

    Args:
        case_id: The test case identifier.
        suffix: Optional suffix (e.g. ``"error"``).

    Returns:
        A string like ``"20240101_120000_case01_error.png"``.
    """
    parts = [utc_now_str(), case_id]
    if suffix:
        parts.append(suffix)
    return "_".join(parts) + ".png"
