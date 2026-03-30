"""Loads test cases from testcases/questions.csv."""

from __future__ import annotations

import csv
from pathlib import Path
from typing import List

from app.models import TestCase
from app.logger import logger


def _parse_keywords(raw: str) -> List[str]:
    """Split a pipe-separated keyword string into a cleaned list."""
    if not raw or not raw.strip():
        return []
    return [kw.strip() for kw in raw.split("|") if kw.strip()]


def load_test_cases(csv_path: Path, max_questions: int = 0) -> List[TestCase]:
    """Read and return test cases from *csv_path*.

    Args:
        csv_path: Path to the CSV file.
        max_questions: Maximum number of cases to load (0 = unlimited).

    Returns:
        A list of :class:`TestCase` objects.
    """
    cases: List[TestCase] = []

    if not csv_path.exists():
        logger.error("CSV file not found: %s", csv_path)
        return cases

    try:
        with csv_path.open(newline="", encoding="utf-8") as fh:
            reader = csv.DictReader(fh)
            for row in reader:
                try:
                    case = TestCase(
                        id=row["id"].strip(),
                        category=row.get("category", "").strip(),
                        locale=row.get("locale", "en-US").strip(),
                        page_url=row.get("page_url", "").strip(),
                        question=row["question"].strip(),
                        expected_keywords=_parse_keywords(row.get("expected_keywords", "")),
                        forbidden_keywords=_parse_keywords(row.get("forbidden_keywords", "")),
                    )
                    cases.append(case)
                except KeyError as exc:
                    logger.warning("Skipping malformed CSV row (missing key %s): %s", exc, row)

                if max_questions > 0 and len(cases) >= max_questions:
                    break
    except Exception as exc:
        logger.exception("Failed to parse CSV %s: %s", csv_path, exc)

    logger.info("Loaded %d test case(s) from %s", len(cases), csv_path)
    return cases
