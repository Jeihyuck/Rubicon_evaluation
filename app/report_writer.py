"""Writes run results to JSON, CSV and Markdown reports."""

from __future__ import annotations

import csv
import dataclasses
import json
from pathlib import Path
from typing import List

from app.logger import logger
from app.models import RunResult
from app.utils import iso_utc_now


# ---------------------------------------------------------------------------
# CSV column order (flattened RunResult fields)
# ---------------------------------------------------------------------------
CSV_COLUMNS: List[str] = [
    "run_timestamp",
    "case_id",
    "category",
    "question",
    "answer",
    "response_ms",
    "status",
    "error_message",
    "overall_score",
    "needs_human_review",
    "hallucination_risk",
    "reason",
    "fix_suggestion",
    "full_screenshot_path",
    "chat_screenshot_path",
]


def _result_to_dict(r: RunResult) -> dict:
    """Convert a RunResult dataclass to a plain dict."""
    return dataclasses.asdict(r)


def write_json(results: List[RunResult], output_path: Path) -> None:
    """Write all results as a JSON array to *output_path*."""
    data = [_result_to_dict(r) for r in results]
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as fh:
        json.dump(data, fh, ensure_ascii=False, indent=2)
    logger.info("JSON report written: %s", output_path)


def write_csv(results: List[RunResult], output_path: Path) -> None:
    """Write results as a CSV table to *output_path*."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=CSV_COLUMNS, extrasaction="ignore")
        writer.writeheader()
        for r in results:
            row = _result_to_dict(r)
            writer.writerow(row)
    logger.info("CSV report written: %s", output_path)


def write_summary(results: List[RunResult], output_path: Path) -> None:
    """Write a human-readable Markdown summary to *output_path*."""
    total = len(results)
    successes = sum(1 for r in results if r.status == "success")
    failures = total - successes
    needs_review = sum(1 for r in results if r.needs_human_review)
    scores = [r.overall_score for r in results if r.status == "success"]
    avg_score = sum(scores) / len(scores) if scores else 0.0
    min_score_case = (
        min(results, key=lambda r: r.overall_score) if results else None
    )
    error_cases = [r for r in results if r.error_message]

    lines = [
        "# Samsung Chat QA – Run Summary",
        "",
        f"**Generated:** {iso_utc_now()}",
        "",
        "## Overview",
        "",
        f"| Metric | Value |",
        f"|--------|-------|",
        f"| Total cases | {total} |",
        f"| Successes | {successes} |",
        f"| Failures | {failures} |",
        f"| Needs human review | {needs_review} |",
        f"| Average score (success) | {avg_score:.2f} |",
        "",
    ]

    if min_score_case:
        lines += [
            "## Lowest Score Case",
            "",
            f"- **ID:** {min_score_case.case_id}",
            f"- **Question:** {min_score_case.question}",
            f"- **Score:** {min_score_case.overall_score:.2f}",
            f"- **Reason:** {min_score_case.reason}",
            "",
        ]

    if error_cases:
        lines += ["## Error Cases", ""]
        for r in error_cases:
            lines.append(f"- **{r.case_id}** – {r.error_message}")
        lines.append("")

    lines += [
        "## Full Results",
        "",
        "| ID | Category | Status | Score | Review | Hallucination |",
        "|----|----------|--------|-------|--------|---------------|",
    ]
    for r in results:
        review = "✅" if not r.needs_human_review else "⚠️"
        lines.append(
            f"| {r.case_id} | {r.category} | {r.status} "
            f"| {r.overall_score:.2f} | {review} | {r.hallucination_risk} |"
        )

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as fh:
        fh.write("\n".join(lines) + "\n")
    logger.info("Markdown summary written: %s", output_path)


def write_all_reports(results: List[RunResult], reports_dir: Path) -> None:
    """Write JSON, CSV, and Markdown reports to *reports_dir*."""
    write_json(results, reports_dir / "latest_results.json")
    write_csv(results, reports_dir / "latest_results.csv")
    write_summary(results, reports_dir / "summary.md")
    logger.info("All reports written to %s", reports_dir)
