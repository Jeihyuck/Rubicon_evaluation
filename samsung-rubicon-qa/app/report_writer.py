"""Report generation for JSON, CSV, and Markdown summaries."""

from __future__ import annotations

import csv
from statistics import mean

from app.config import AppConfig
from app.models import RunResult
from app.utils import write_json


def write_reports(config: AppConfig, run_results: list[RunResult]) -> dict[str, str]:
    """Write the latest JSON, CSV, Markdown summary, and conversation report files."""

    json_path = config.reports_dir / "latest_results.json"
    csv_path = config.reports_dir / "latest_results.csv"
    summary_path = config.reports_dir / "summary.md"
    conversation_path = config.reports_dir / "latest_conversations.md"

    nested = [result.to_nested_dict() for result in run_results]
    write_json(json_path, nested)

    flat_rows = [result.to_flat_dict() for result in run_results]
    fieldnames = sorted({key for row in flat_rows for key in row.keys()})
    with csv_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(flat_rows)

    summary_path.write_text(_build_summary(run_results), encoding="utf-8")
    conversation_path.write_text(_build_conversation(run_results), encoding="utf-8")
    return {
        "json": str(json_path),
        "csv": str(csv_path),
        "summary": str(summary_path),
        "conversation": str(conversation_path),
    }


def _build_conversation(run_results: list[RunResult]) -> str:
    """Build a per-case evidence report with question, echo, history, answer, and scores."""

    lines = [
        "# Samsung Rubicon QA Conversations",
        "",
        "질문, 채팅 UI에서 확인된 질문 echo, DOM history, 추출 답변, 평가 결과를 함께 저장한 증거 리포트다.",
    ]

    for item in run_results:
        pair = item.pair
        ev = item.evaluation

        echo_text = pair.question if pair.user_message_echo_verified else "(not verified)"

        lines.extend(
            [
                "",
                f"## {pair.case_id}",
                "",
                f"- Question: {pair.question}",
                f"- Question Echo In Chat: {echo_text}",
                f"- Extracted Answer: {pair.answer or '(none)'}",
                f"- Extraction Source: {pair.extraction_source}",
                f"- Overall Score: {ev.overall_score}",
                f"- Needs Human Review: {ev.needs_human_review}",
                f"- Reason: {ev.reason}",
                f"- Fix Suggestion: {ev.fix_suggestion}",
                f"- Submitted Chat Screenshot: {pair.before_send_screenshot_path or '(none)'}",
                f"- Answered Chat Screenshot: {pair.after_answer_screenshot_path or '(none)'}",
                f"- Chat Screenshot: {pair.chat_screenshot_path or '(none)'}",
                f"- Fullpage Screenshot: {pair.full_screenshot_path or '(none)'}",
                f"- HTML Fragment: {pair.html_fragment_path or '(none)'}",
                f"- Trace: {pair.trace_path or '(none)'}",
                f"- Video: {pair.video_path or '(none)'}",
                "",
                "### Message History",
                "",
            ]
        )

        if pair.message_history:
            for msg in pair.message_history:
                lines.append(f"- {msg}")
        else:
            lines.append("- (empty)")

        lines.append("")

    return "\n".join(lines)


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
                "",
                f"- case_id: {lowest.pair.case_id}",
                f"- score: {lowest.evaluation.overall_score:.2f}",
                f"- reason: {lowest.evaluation.reason}",
            ]
        )

    lines.extend(["", "## 에러 케이스", ""])
    if not error_cases:
        lines.append("- 없음")
    else:
        for item in error_cases:
            lines.append(f"- {item.pair.case_id}: {item.pair.error_message}")

    return "\n".join(lines) + "\n"
