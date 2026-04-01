"""Report writer – produces JSON, CSV, and Markdown summaries."""
from __future__ import annotations

import csv
import json
import logging
from pathlib import Path
from typing import List

from app.models import RunResult

log = logging.getLogger("samsung_chat_qa.report_writer")

_JSON_FILE = "latest_results.json"
_CSV_FILE = "latest_results.csv"
_MD_FILE = "summary.md"

_CSV_COLUMNS = [
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


def write_reports(results: List[RunResult], reports_dir: Path) -> None:
    """Write all report files for the current run.

    Parameters
    ----------
    results:
        List of :class:`~app.models.RunResult` objects from the current run.
    reports_dir:
        Directory where report files will be written.
    """
    reports_dir.mkdir(parents=True, exist_ok=True)
    _write_json(results, reports_dir / _JSON_FILE)
    _write_csv(results, reports_dir / _CSV_FILE)
    _write_markdown(results, reports_dir / _MD_FILE)
    log.info("Reports written to %s", reports_dir)


# ---------------------------------------------------------------------------
# JSON
# ---------------------------------------------------------------------------

def _write_json(results: List[RunResult], path: Path) -> None:
    data = [r.to_flat_dict() for r in results]
    with path.open("w", encoding="utf-8") as fh:
        json.dump(data, fh, indent=2, ensure_ascii=False)
    log.info("JSON report: %s", path)


# ---------------------------------------------------------------------------
# CSV
# ---------------------------------------------------------------------------

def _write_csv(results: List[RunResult], path: Path) -> None:
    rows = [r.to_flat_dict() for r in results]
    with path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=_CSV_COLUMNS, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)
    log.info("CSV report: %s", path)


# ---------------------------------------------------------------------------
# Markdown summary
# ---------------------------------------------------------------------------

def _write_markdown(results: List[RunResult], path: Path) -> None:
    total = len(results)
    success = sum(1 for r in results if r.status == "success")
    failed = total - success
    needs_review = sum(1 for r in results if r.needs_human_review)
    scores = [r.overall_score for r in results if r.status == "success"]
    avg_score = sum(scores) / len(scores) if scores else 0.0
    lowest = min(results, key=lambda r: r.overall_score) if results else None

    lines: List[str] = [
        "# Samsung Chat QA – Run Summary\n",
        f"| Metric | Value |",
        f"|--------|-------|",
        f"| Total test cases | {total} |",
        f"| Succeeded | {success} |",
        f"| Failed | {failed} |",
        f"| Needs human review | {needs_review} |",
        f"| Average score (successful) | {avg_score:.2f} |",
        "",
    ]

    if lowest:
        lines += [
            "## Lowest-Scoring Case",
            f"- **ID:** {lowest.case_id}",
            f"- **Question:** {lowest.question}",
            f"- **Score:** {lowest.overall_score:.2f}",
            f"- **Reason:** {lowest.reason}",
            "",
        ]

    error_cases = [r for r in results if r.error_message]
    if error_cases:
        lines.append("## Error Cases\n")
        for r in error_cases:
            lines.append(f"### Case `{r.case_id}`")
            lines.append(f"- **Question:** {r.question}")
            lines.append(f"- **Error:** {r.error_message}")
            lines.append("")

    lines.append("## All Results\n")
    lines.append("| ID | Category | Status | Score | Needs Review | Hallucination |")
    lines.append("|----|----------|--------|-------|--------------|---------------|")
    for r in results:
        lines.append(
            f"| {r.case_id} | {r.category} | {r.status} | "
            f"{r.overall_score:.2f} | {r.needs_human_review} | {r.hallucination_risk} |"
        )

    content = "\n".join(lines) + "\n"
    with path.open("w", encoding="utf-8") as fh:
        fh.write(content)
    log.info("Markdown summary: %s", path)
