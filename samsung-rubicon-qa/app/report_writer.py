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
    conversation_path = config.reports_dir / "latest_conversation.md"

    records = [result.to_result_record() for result in run_results]
    write_json(json_path, records)

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
    """Build the main per-case evidence report for human review."""

    lines = [
        "# Samsung Rubicon QA Latest Conversation",
        "",
        "가장 먼저 확인해야 할 파일이다.",
        "이 파일에 질문, 입력 검증 여부, 새 응답 여부, 실제 답변, 평가 결과, 스크린샷 경로를 함께 기록한다.",
    ]

    for item in run_results:
        pair = item.pair
        ev = item.evaluation

        lines.extend(
            [
                "",
                f"## {pair.case_id}",
                "",
                f"- Status: {pair.status}",
                f"- Question: {pair.question}",
                f"- Input Verified: {pair.input_verified}",
                f"- Input Method Used: {pair.input_method_used or '(none)'}",
                f"- User Message Echo Verified: {pair.user_message_echo_verified}",
                f"- New Bot Response Detected: {pair.new_bot_response_detected}",
                f"- Baseline Menu Detected: {pair.baseline_menu_detected}",
                f"- Capture Reason: {pair.reason or '(none)'}",
                f"- Actual Answer: {pair.answer or '(none)'}",
                f"- Overall Score: {ev.overall_score}",
                f"- Needs Human Review: {ev.needs_human_review}",
                f"- Evaluation Reason: {ev.reason}",
                f"- Evaluation Fix Suggestion: {ev.fix_suggestion}",
                f"- Opened Chat Screenshot: {pair.opened_chat_screenshot_path or '(none)'}",
                f"- Opened Fullpage Screenshot: {pair.opened_full_screenshot_path or '(none)'}",
                f"- Before Send Chat Screenshot: {pair.before_send_screenshot_path or '(none)'}",
                f"- Before Send Fullpage Screenshot: {pair.before_send_full_screenshot_path or '(none)'}",
                f"- After Send Chat Screenshot: {pair.after_send_screenshot_path or '(none)'}",
                f"- After Send Fullpage Screenshot: {pair.after_send_full_screenshot_path or '(none)'}",
                f"- After Answer Chat Screenshot: {pair.after_answer_screenshot_path or '(none)'}",
                f"- After Answer Fullpage Screenshot: {pair.after_answer_full_screenshot_path or '(none)'}",
                f"- Primary Full Screenshot: {pair.full_screenshot_path or '(none)'}",
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
    invalid_captures = sum(1 for item in run_results if item.pair.status == "invalid_capture")
    failures = sum(1 for item in run_results if item.pair.status == "failed")
    dom_successes = sum(1 for item in run_results if item.pair.extraction_source == "dom")
    ocr_used = sum(1 for item in run_results if item.pair.extraction_source == "ocr")
    human_review = sum(1 for item in run_results if item.evaluation.needs_human_review)
    new_response_detected = sum(1 for item in run_results if item.pair.new_bot_response_detected)
    avg_score = mean(item.evaluation.overall_score for item in run_results) if run_results else 0.0
    lowest = min(run_results, key=lambda item: item.evaluation.overall_score, default=None)
    error_cases = [item for item in run_results if item.pair.error_message]

    lines = [
        "# Samsung Rubicon QA Summary",
        "",
        "결과 확인 우선순위: reports/latest_conversation.md -> reports/latest_results.json -> artifacts/chatbox/STAR_before_send.png 및 STAR_after_answer.png 패턴 -> reports/summary.md",
        "",
        "## 집계",
        "",
        f"- 총 케이스 수: {total}",
        f"- 성공 수: {successes}",
        f"- 실패 수: {failures}",
        f"- invalid_capture 수: {invalid_captures}",
        f"- DOM 추출 성공 수: {dom_successes}",
        f"- OCR fallback 사용 수: {ocr_used}",
        f"- baseline 이후 새 응답 감지 수: {new_response_detected}",
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

    return "\n".join(lines).rstrip() + "\n"
