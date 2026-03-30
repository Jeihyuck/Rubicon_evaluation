"""CSV loader for test cases.

Reads ``testcases/questions.csv`` and returns a list of :class:`~app.models.TestCase`
objects.  Multi-value keyword columns are delimited by ``|``.
"""
from __future__ import annotations

import csv
import logging
from pathlib import Path
from typing import List

from app.models import TestCase

log = logging.getLogger("samsung_chat_qa.csv_loader")

_KEYWORD_SEP = "|"


def _parse_keywords(raw: str) -> List[str]:
    """Split a pipe-separated keyword string into a cleaned list."""
    if not raw or not raw.strip():
        return []
    return [kw.strip() for kw in raw.split(_KEYWORD_SEP) if kw.strip()]


def load_test_cases(csv_path: Path, max_questions: int = 0) -> List[TestCase]:
    """Load test cases from *csv_path*.

    Parameters
    ----------
    csv_path:
        Absolute path to the questions CSV file.
    max_questions:
        Maximum number of rows to return.  ``0`` means no limit.

    Returns
    -------
    List[TestCase]
        Parsed and optionally truncated list of test cases.

    Raises
    ------
    FileNotFoundError
        When *csv_path* does not exist.
    """
    if not csv_path.exists():
        raise FileNotFoundError(f"Test-case CSV not found: {csv_path}")

    test_cases: List[TestCase] = []

    with csv_path.open(newline="", encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        for row in reader:
            try:
                tc = TestCase(
                    id=row["id"].strip(),
                    category=row.get("category", "").strip(),
                    locale=row.get("locale", "en-US").strip(),
                    page_url=row.get("page_url", "").strip(),
                    question=row["question"].strip(),
                    expected_keywords=_parse_keywords(row.get("expected_keywords", "")),
                    forbidden_keywords=_parse_keywords(row.get("forbidden_keywords", "")),
                )
                test_cases.append(tc)
            except KeyError as exc:
                log.warning("Skipping malformed row (missing column %s): %s", exc, row)

    if max_questions and max_questions > 0:
        test_cases = test_cases[:max_questions]

    log.info("Loaded %d test case(s) from %s", len(test_cases), csv_path)
    return test_cases
