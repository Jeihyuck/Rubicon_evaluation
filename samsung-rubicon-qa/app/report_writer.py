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

    summary_path.write_text(_build_summary(run_results, config), encoding="utf-8")
    _write_latest_conversation(run_results, conversation_path, config)
    return {
        "json": str(json_path),
        "csv": str(csv_path),
        "summary": str(summary_path),
        "conversation": str(conversation_path),
    }


def _write_latest_conversation(results: list[RunResult], path, config: AppConfig) -> None:
    path.write_text(_build_conversation(results, config), encoding="utf-8")


def _show_detailed_case(item: RunResult) -> bool:
    return item.pair.status != "success" or item.pair.run_mode == "debug"


def _format_flags(flags: list[str]) -> str:
    return " | ".join(flags) if flags else "(none)"


def _reason_text(result: RunResult) -> str:
    return result.evaluation.reason or result.pair.reason or "(none)"


def _fix_suggestion_text(result: RunResult) -> str:
    return result.evaluation.fix_suggestion or result.pair.fix_suggestion or "(none)"


def _score_text(result: RunResult) -> str:
    return f"{result.evaluation.overall_score:.1f} / 10"


def _score_breakdown_text(result: RunResult) -> str:
    evaluation = result.evaluation
    return (
        f"correctness={evaluation.correctness_score:.1f}, "
        f"relevance={evaluation.relevance_score:.1f}, "
        f"completeness={evaluation.completeness_score:.1f}, "
        f"clarity={evaluation.clarity_score:.1f}, "
        f"groundedness={evaluation.groundedness_score:.1f}"
    )


def _error_category_text(result: RunResult) -> str:
    return str(result.to_result_record().get("error_category", "(none)"))


def _language_policy_check_text(result: RunResult) -> str:
    return str(result.to_result_record().get("language_policy_check", "pass"))


def _cleaning_applied_text(result: RunResult) -> str:
    applied: list[str] = []
    if result.pair.cta_stripped:
        applied.append("cta_stripped")
    if result.pair.promo_stripped:
        applied.append("promo_stripped")
    return " | ".join(applied) if applied else "(none)"


def _raw_clean_diff_text(result: RunResult) -> str:
    raw_answer = result.pair.raw_answer or result.pair.answer_raw
    cleaned_answer = result.pair.cleaned_answer or result.pair.actual_answer_clean or result.pair.answer
    if raw_answer and cleaned_answer and raw_answer != cleaned_answer:
        return "cleaned"
    return "same"


def _extraction_rejected_reason(result: RunResult) -> str:
    if result.pair.question_repetition_detected:
        return "question_repetition_detected"
    if result.pair.truncated_answer_detected:
        return "truncated_detected"
    return "(none)"


def format_case_console_block(result: RunResult) -> str:
    pair = result.pair
    evaluation = result.evaluation
    lines = ["=" * 50, f"CASE: {pair.case_id}", f"QUESTION: {pair.question}", f"STATUS: {pair.status}"]

    if pair.status == "success":
        lines.extend(
            [
                f"ANSWER: {pair.answer}",
                f"EXTRACTION SOURCE: {pair.extraction_source}",
                f"EVALUATION LANGUAGE: {evaluation.evaluation_language}",
                f"SCORE: {_score_text(result)}",
                f"SCORE BREAKDOWN: {_score_breakdown_text(result)}",
                f"SCORE BREAKDOWN EXPLANATION: {evaluation.score_breakdown_explanation or '(none)'}",
                f"REASON: {_reason_text(result)}",
                f"FIX SUGGESTION: {_fix_suggestion_text(result)}",
                f"FLAGS: {'|'.join(evaluation.flags) if evaluation.flags else '(none)'}",
                f"NEEDS HUMAN REVIEW: {evaluation.needs_human_review}",
            ]
        )
    else:
        lines.extend(
            [
                f"INPUT DOM VERIFIED: {pair.input_dom_verified}",
                f"SUBMIT EFFECT VERIFIED: {pair.submit_effect_verified}",
                f"INPUT VERIFIED: {pair.input_verified}",
                f"INPUT METHOD: {pair.input_method_used or '(none)'}",
                f"SUBMIT METHOD USED: {pair.submit_method_used}",
                f"EVALUATION LANGUAGE: {evaluation.evaluation_language}",
                f"SCORE: {_score_text(result)}",
                f"SCORE BREAKDOWN: {_score_breakdown_text(result)}",
                f"SCORE BREAKDOWN EXPLANATION: {evaluation.score_breakdown_explanation or '(none)'}",
                f"REASON: {_reason_text(result)}",
                f"FIX SUGGESTION: {_fix_suggestion_text(result)}",
                f"FLAGS: {'|'.join(evaluation.flags) if evaluation.flags else '(none)'}",
            ]
        )
    lines.append("CHECK FIRST: reports/latest_conversation.md")
    lines.append("=" * 50)
    return "\n".join(lines)


def _build_conversation(run_results: list[RunResult], config: AppConfig | None = None) -> str:
    """Build the main per-case evidence report for human review."""

    lines = [
        "# Samsung Rubicon QA Latest Conversation",
        "",
        "가장 먼저 확인해야 할 파일이다.",
        "이 파일에 질문, 입력 검증 여부, 새 응답 여부, 실제 답변, 평가 결과, 스크린샷 경로를 함께 기록한다.",
    ]

    for index, item in enumerate(run_results):
        pair = item.pair
        ev = item.evaluation
        heading_suffix = f" ({pair.case_id})"

        if not _show_detailed_case(item):
            if index != 0:
                lines.append("")
            lines.extend(
                [
                    f"## {pair.case_id}",
                    "",
                    f"- Question: {pair.question}",
                    f"- Final Answer: {pair.answer or '(none)'}",
                    f"- Raw Answer: {pair.raw_answer or pair.answer_raw or '(none)'}",
                    f"- Cleaned Answer: {pair.cleaned_answer or pair.actual_answer_clean or pair.answer or '(none)'}",
                    f"- Raw/Clean Diff: {_raw_clean_diff_text(item)}",
                    f"- Cleaning Applied: {_cleaning_applied_text(item)}",
                    f"- Extraction Source: {pair.extraction_source}",
                    f"- Evaluation Language: {ev.evaluation_language}",
                    f"- Score: {_score_text(item)}",
                    f"- Score Breakdown: {_score_breakdown_text(item)}",
                    f"- Score Breakdown Explanation: {ev.score_breakdown_explanation or '(none)'}",
                    f"- Reason: {_reason_text(item)}",
                    f"- Fix Suggestion: {_fix_suggestion_text(item)}",
                    f"- Error Category: {_error_category_text(item)}",
                    f"- Language Policy Check: {_language_policy_check_text(item)}",
                    f"- Flags: {_format_flags(ev.flags)}",
                ]
            )
            if index != len(run_results) - 1:
                lines.append("")
            continue

        if index != 0:
            lines.append("")
        lines.extend(
            [
                f"## {pair.case_id}",
                "",
                f"- Question: {pair.question}",
                f"- Input DOM Verified: {pair.input_dom_verified}",
                f"- Submit Effect Verified: {pair.submit_effect_verified}",
                f"- Input Scope: {pair.input_scope or pair.input_scope_name or '(none)'}",
                f"- Input Selector: {pair.input_selector or '(none)'}",
                f"- Input Candidate Score: {pair.input_candidate_score}",
                f"- Input Failure Category: {pair.input_failure_category or '(none)'}",
                f"- Input Failure Reason: {pair.input_failure_reason or '(none)'}",
                f"- Top Candidate Placeholder: {pair.top_candidate_placeholder or '(none)'}",
                f"- Top Candidate Aria: {pair.top_candidate_aria or '(none)'}",
                f"- Input Ready Wait Attempted: {pair.transition_wait_attempted}",
                f"- Input Ready Wait Result: {pair.input_ready_wait_result or '(none)'}",
                f"- Input Verified: {pair.input_verified}",
                f"- Input Method: {pair.input_method_used or '(none)'}",
                f"- Submit Method Used: {pair.submit_method_used or 'unknown'}",
                f"- User Message Echo Verified: {pair.user_message_echo_verified}",
                f"- New Bot Response Detected: {pair.new_bot_response_detected}",
                f"- Failure Reason: {pair.reason or pair.input_failure_reason or pair.error_message or '(none)'}",
                f"- Top Candidate Disabled: {pair.top_candidate_disabled}",
                f"- Transition Ready: {pair.transition_ready}",
                f"- Transition Timeout: {pair.transition_timeout}",
                f"- Transition Reason: {pair.transition_reason or '(none)'}",
                f"- Transition History: {pair.transition_history or '(none)'}",
                f"- Activation Attempted: {pair.activation_attempted}",
                f"- Activation Steps Tried: {pair.activation_steps_tried or '(none)'}",
                f"- Editable Candidates Count: {pair.editable_candidates_count}",
                f"- Failover Attempts: {pair.failover_attempts}",
                f"- Final Input Target Frame: {pair.final_input_target_frame or '(none)'}",
                f"- SDK Status: {pair.sdk_status or '(none)'}",
                f"- Availability Status: {pair.availability_status or 'unknown'}",
                f"- Open Method Used: {pair.open_method_used or '(none)'}",
                f"- Status: {pair.status}",
                f"- Extraction Rejected Reason: {_extraction_rejected_reason(item)}",
                f"- Actual Answer: {pair.actual_answer or pair.answer or '(none)'}",
                f"- Actual Answer Clean: {pair.actual_answer_clean or pair.actual_answer or pair.answer or '(none)'}",
                f"- Raw Answer: {pair.raw_answer or pair.answer_raw or '(none)'}",
                f"- Cleaned Answer: {pair.cleaned_answer or pair.actual_answer_clean or pair.actual_answer or pair.answer or '(none)'}",
                f"- Raw/Clean Diff: {_raw_clean_diff_text(item)}",
                f"- Cleaning Applied: {_cleaning_applied_text(item)}",
                f"- Answer Raw: {pair.answer_raw or '(none)'}",
                f"- Extraction Source: {pair.extraction_source}",
                f"- Message History Clean: {pair.message_history_clean or '(none)'}",
                f"- Evaluation Language: {ev.evaluation_language}",
                f"- Score: {_score_text(item)}",
                f"- Score Breakdown: {_score_breakdown_text(item)}",
                f"- Score Breakdown Explanation: {ev.score_breakdown_explanation or '(none)'}",
                f"- Reason: {_reason_text(item)}",
                f"- Fix Suggestion: {_fix_suggestion_text(item)}",
                f"- Error Category: {_error_category_text(item)}",
                f"- Language Policy Check: {_language_policy_check_text(item)}",
                f"- Flags: {_format_flags(ev.flags)}",
                f"- Needs Human Review: {ev.needs_human_review}",
                f"- Screenshot Path: {pair.after_answer_screenshot_path or pair.before_send_screenshot_path or pair.opened_footer_screenshot_path or pair.chat_screenshot_path or '(none)'}",
                f"- Opened Footer Screenshot: {pair.opened_footer_screenshot_path or '(none)'}",
                f"- Before Send Screenshot: {pair.before_send_screenshot_path or '(none)'}",
                f"- After Answer Screenshot: {pair.after_answer_screenshot_path or '(none)'}",
                f"- Fullpage Screenshot: {pair.full_screenshot_path or pair.after_answer_full_screenshot_path or '(none)'}",
                f"- Chat Screenshot: {pair.chat_screenshot_path or '(none)'}",
                f"- Video Path: {pair.video_path or '(none)'}",
                "",
                f"### Input Candidates{heading_suffix}",
                "",
            ]
        )

        candidate_lines = [line for line in (pair.input_candidates_debug or "").splitlines() if line.strip()]
        if not candidate_lines and pair.input_candidate_logs:
            candidate_lines = pair.input_candidate_logs
        if candidate_lines:
            for candidate_log in candidate_lines[:10]:
                lines.append(f"- {candidate_log}")
        else:
            lines.append("- (empty)")

        lines.extend(
            [
                "",
                f"### Answer Extraction Debug{heading_suffix}",
                "",
                f"- selected_source={pair.extraction_source_detail or pair.extraction_source or 'unknown'}",
                f"- raw_len={len(pair.answer_raw or '')}",
                f"- clean_len={len(pair.actual_answer_clean or pair.actual_answer or pair.answer or '')}",
                f"- removed_followups={pair.removed_followups}",
                f"- noise_lines_removed={pair.noise_lines_removed}",
                "",
                f"### Message History{heading_suffix}",
                "",
            ]
        )

        if pair.message_history:
            for msg in pair.message_history:
                lines.append(f"- {msg}")
        else:
            lines.append("- (empty)")

        if index != len(run_results) - 1:
            lines.append("")

    return "\n".join(lines).rstrip() + "\n"


def _build_summary(run_results: list[RunResult], config: AppConfig | None = None) -> str:
    total = len(run_results)
    successes = sum(1 for item in run_results if item.pair.status == "success")
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
        "결과 확인 우선순위: `reports/latest_conversation.md` -> `reports/latest_results.json` -> `reports/latest_results.csv` -> `reports/summary.md`",
        "성공 케이스는 스크린샷이나 비디오 경로가 비어 있어도 정상이며, 실패 케이스에서만 최소 증거 캡처가 남을 수 있다.",
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

    lines.extend(["", "## 케이스 요약", ""])
    if not run_results:
        lines.append("- 없음")
    else:
        for item in run_results:
            pair = item.pair
            evaluation = item.evaluation
            lines.extend(
                [
                    f"### {pair.case_id}",
                    "",
                    f"- Question: {pair.question}",
                    f"- Final Answer: {pair.answer or '(none)'}",
                    f"- Raw/Clean Diff: {_raw_clean_diff_text(item)}",
                    f"- Cleaning Applied: {_cleaning_applied_text(item)}",
                    f"- Extraction Source: {pair.extraction_source}",
                    f"- Evaluation Language: {evaluation.evaluation_language}",
                    f"- Score: {_score_text(item)}",
                    f"- Score Breakdown: {_score_breakdown_text(item)}",
                    f"- Score Breakdown Explanation: {evaluation.score_breakdown_explanation or '(none)'}",
                    f"- Reason: {_reason_text(item)}",
                    f"- Fix Suggestion: {_fix_suggestion_text(item)}",
                    f"- Flags: {_format_flags(evaluation.flags)}",
                    f"- Needs Human Review: {evaluation.needs_human_review}",
                    "",
                ]
            )

    if lowest is not None:
        lines.extend(
            [
                "",
                "## 최저 점수 케이스",
                "",
                f"- case_id: {lowest.pair.case_id}",
                f"- evaluation_language: {lowest.evaluation.evaluation_language}",
                f"- score: {_score_text(lowest)}",
                f"- score_breakdown: {_score_breakdown_text(lowest)}",
                f"- score_breakdown_explanation: {lowest.evaluation.score_breakdown_explanation or '(none)'}",
                f"- reason: {lowest.evaluation.reason}",
                f"- fix_suggestion: {_fix_suggestion_text(lowest)}",
                f"- flags: {_format_flags(lowest.evaluation.flags)}",
            ]
        )

    lines.extend(["", "## 에러 케이스", ""])
    if not error_cases:
        lines.append("- 없음")
    else:
        for item in error_cases:
            lines.append(f"- {item.pair.case_id}: {item.pair.error_message}")

    return "\n".join(lines).rstrip() + "\n"
