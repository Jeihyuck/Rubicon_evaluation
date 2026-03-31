"""Report generation for JSON, CSV, and Markdown summaries."""

from __future__ import annotations

import csv
from statistics import mean
from typing import Any

from app.config import AppConfig
from app.models import RunResult
from app.utils import write_json


def write_reports(config: AppConfig, run_results: list[RunResult]) -> dict[str, str]:
    """Write the latest JSON, CSV, and Markdown report files."""

    json_path = config.reports_dir / "latest_results.json"
    csv_path = config.reports_dir / "latest_results.csv"
    summary_path = config.reports_dir / "summary.md"

    rows = [result.to_report_dict() for result in run_results]
    write_json(json_path, rows)

    fieldnames = list(rows[0].keys()) if rows else [
        "run_timestamp",
        "case_id",
        "category",
        "page_url",
        "locale",
        "question",
        "expected_keywords",
        "forbidden_keywords",
        "answer",
        "extraction_source",
        "extraction_confidence",
        "response_ms",
        "status",
        "error_message",
        "full_screenshot_path",
        "chat_screenshot_path",
        "video_path",
        "trace_path",
        "html_fragment_path",
        "overall_score",
        "relevance_score",
        "clarity_score",
        "completeness_score",
        "keyword_alignment_score",
        "hallucination_risk",
        "needs_human_review",
        "reason",
        "fix_suggestion",
    ]
    with csv_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    summary_path.write_text(_build_summary(run_results), encoding="utf-8")
    return {
        "json": str(json_path),
        "csv": str(csv_path),
        "summary": str(summary_path),
    }


def _build_summary(run_results: list[RunResult]) -> str:
    total = len(run_results)
    successes = sum(1 for item in run_results if item.pair.status == "passed")
    failures = total - successes
    dom_successes = sum(1 for item in run_results if item.pair.extraction_source == "dom")
    ocr_used = sum(1 for item in run_results if item.pair.extraction_source == "ocr")
    human_review = sum(1 for item in run_results if item.evaluation.needs_human_review)
    avg_score = mean(item.evaluation.overall_score for item in run_results) if run_results else 0.0
    lowest = min(run_results, key=lambda item: item.evaluation.overall_score, default=None)
    error_cases = [item for item in run_results if item.pair.error_message]

    lines = [
        "# Samsung Rubicon QA Summary",
        "",
        "## Result Files",
        "- JSON: reports/latest_results.json",
        "- CSV: reports/latest_results.csv",
        "- Summary: reports/summary.md",
        "- Runtime Log: reports/runtime.log",
        "",
        "## Aggregate",
        f"- 총 케이스 수: {total}",
        f"- 성공 수: {successes}",
        f"- 실패 수: {failures}",
        f"- DOM 추출 성공 수: {dom_successes}",
        f"- OCR fallback 사용 수: {ocr_used}",
        f"- 평균 overall score: {avg_score:.2f}",
        f"- human review 필요 건수: {human_review}",
    ]

    if lowest is not None:
        lines.extend(
            [
                "",
                "## 최저 점수 케이스",
                f"- case_id: {lowest.pair.case_id}",
                f"- score: {lowest.evaluation.overall_score:.2f}",
                f"- reason: {lowest.evaluation.reason}",
            ]
        )

    lines.extend(["", "## 에러 케이스"])
    if not error_cases:
        lines.append("- 없음")
    else:
        for item in error_cases:
            lines.append(f"- {item.pair.case_id}: {item.pair.error_message}")

    lines.extend(["", "## 케이스별 결과"])
    if not run_results:
        lines.append("- 없음")
    else:
        for item in run_results:
            lines.extend(
                [
                    f"### {item.pair.case_id}",
                    f"- Question: {item.pair.question}",
                    f"- Answer: {item.pair.answer or '(empty)'}",
                    f"- Extraction Source: {item.pair.extraction_source}",
                    f"- Overall Score: {item.evaluation.overall_score:.2f}",
                    f"- Needs Human Review: {item.evaluation.needs_human_review}",
                    f"- Reason: {item.evaluation.reason}",
                    f"- Chat Screenshot: {item.pair.chat_screenshot_path}",
                    f"- Fullpage Screenshot: {item.pair.full_screenshot_path}",
                    "",
                ]
            )

    return "\n".join(lines) + "\n"


def format_case_console_block(result: RunResult) -> str:
    """Render the required terminal summary format for a single case."""

    return "\n".join(
        [
            "=" * 50,
            f"CASE: {result.pair.case_id}",
            f"QUESTION: {result.pair.question}",
            f"ANSWER: {result.pair.answer or '(empty)'}",
            f"EXTRACTION SOURCE: {result.pair.extraction_source}",
            f"OVERALL SCORE: {result.evaluation.overall_score:.2f}",
            f"NEEDS HUMAN REVIEW: {result.evaluation.needs_human_review}",
            f"REASON: {result.evaluation.reason}",
            f"CHAT SCREENSHOT: {result.pair.chat_screenshot_path}",
            f"FULLPAGE SCREENSHOT: {result.pair.full_screenshot_path}",
            "=" * 50,
        ]
    )
