"""Main orchestration for the Samsung Rubicon QA automation workflow."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path

from app.browser import BrowserManager
from app.config import load_config
from app.csv_loader import load_test_cases
from app.evaluator import evaluate_pair
from app.logger import create_logger
from app.models import RunResult
from app.report_writer import write_reports
from app.samsung_rubicon import configure_runtime, run_single_case
from app.utils import artifact_timestamp, sanitize_filename


def _display_path(project_root: Path, value: str) -> str:
    if not value:
        return ""
    target = Path(value)
    try:
        return str(target.relative_to(project_root))
    except Exception:
        return value


def _print_case_summary(project_root: Path, result: RunResult) -> None:
    pair = result.pair
    evaluation = result.evaluation

    print("=" * 50)


def _delete_artifact(path_value: str) -> None:
    if not path_value:
        return
    try:
        Path(path_value).unlink(missing_ok=True)
    except Exception:
        return


def _cleanup_success_artifacts(pair):
    removable_paths = [
        pair.full_screenshot_path,
        pair.chat_screenshot_path,
        pair.video_path,
        pair.trace_path,
        pair.html_fragment_path,
        pair.opened_chat_screenshot_path,
        pair.opened_full_screenshot_path,
        pair.opened_footer_screenshot_path,
        pair.before_send_screenshot_path,
        pair.before_send_full_screenshot_path,
        pair.after_send_screenshot_path,
        pair.after_send_full_screenshot_path,
        pair.after_answer_screenshot_path,
        pair.after_answer_full_screenshot_path,
        *pair.answer_screenshot_paths,
    ]
    for artifact_path in removable_paths:
        _delete_artifact(artifact_path)

    return replace(
        pair,
        full_screenshot_path="",
        chat_screenshot_path="",
        video_path="",
        trace_path="",
        html_fragment_path="",
        opened_chat_screenshot_path="",
        opened_full_screenshot_path="",
        opened_footer_screenshot_path="",
        before_send_screenshot_path="",
        before_send_full_screenshot_path="",
        after_send_screenshot_path="",
        after_send_full_screenshot_path="",
        after_answer_screenshot_path="",
        after_answer_full_screenshot_path="",
        answer_screenshot_paths=[],
        after_answer_multi_page=False,
    )
    print(f"CASE: {pair.case_id}")
    print(f"QUESTION: {pair.question}")
    print(f"INPUT DOM VERIFIED: {pair.input_dom_verified}")
    print(f"SUBMIT EFFECT VERIFIED: {pair.submit_effect_verified}")
    print(f"INPUT VERIFIED: {pair.input_verified}")
    if pair.input_method_used:
        print(f"INPUT METHOD: {pair.input_method_used}")
    print(f"SUBMIT METHOD USED: {pair.submit_method_used}")
    print(f"USER MESSAGE ECHO VERIFIED: {pair.user_message_echo_verified}")
    print(f"NEW BOT RESPONSE DETECTED: {pair.new_bot_response_detected}")
    if pair.status in {"invalid_capture", "failed"}:
        print(f"STATUS: {pair.status}")
        if pair.input_failure_category:
            print(f"INPUT FAILURE CATEGORY: {pair.input_failure_category}")
        print(f"REASON: {pair.reason or evaluation.reason}")
    else:
        print(f"BASELINE MENU DETECTED: {pair.baseline_menu_detected}")
        print(f"ANSWER: {pair.answer}")
        print(f"OVERALL SCORE: {evaluation.overall_score:.2f}")
        print(f"NEEDS HUMAN REVIEW: {evaluation.needs_human_review}")
    print("CHECK FIRST: reports/latest_conversation.md")
    if pair.opened_footer_screenshot_path:
        print(f"OPENED FOOTER SCREENSHOT: {_display_path(project_root, pair.opened_footer_screenshot_path)}")
    if pair.before_send_screenshot_path:
        print(f"BEFORE SEND SCREENSHOT: {_display_path(project_root, pair.before_send_screenshot_path)}")
    if pair.answer_screenshot_paths:
        display_paths = ", ".join(_display_path(project_root, path) for path in pair.answer_screenshot_paths)
        print(f"AFTER ANSWER SCREENSHOTS: {display_paths}")
    elif pair.after_answer_screenshot_path:
        print(f"AFTER ANSWER SCREENSHOTS: {_display_path(project_root, pair.after_answer_screenshot_path)}")
    print("=" * 50)


def run(project_root: Path | None = None) -> list[RunResult]:
    """Execute the configured batch and return all case results."""

    config = load_config(project_root)
    config.ensure_directories()
    logger = create_logger(config.runtime_log_path)
    logger.info("app start")
    logger.info("config loaded")

    test_cases = load_test_cases(config.questions_csv_path, max_questions=config.max_questions)
    browser_manager = BrowserManager(config=config, logger=logger)
    browser_manager.start()
    configure_runtime(config, logger)

    results: list[RunResult] = []
    try:
        for test_case in test_cases:
            session = browser_manager.new_case_session(test_case.id)
            pair = run_single_case(session.page, test_case)

            timestamp = artifact_timestamp()
            safe_case_id = sanitize_filename(test_case.id)
            trace_target = config.trace_dir / f"{timestamp}_{safe_case_id}.zip" if config.enable_trace else None
            video_target = config.video_dir / f"{timestamp}_{safe_case_id}.webm" if config.video_recording_enabled else None

            trace_path, video_path = session.close(trace_target=trace_target, video_target=video_target)
            pair = replace(pair, trace_path=trace_path, video_path=video_path)
            if pair.status == "success" and config.keep_only_failure_artifacts:
                pair = _cleanup_success_artifacts(pair)

            evaluation = evaluate_pair(config, test_case, pair, logger)
            run_result = RunResult(test_case=test_case, pair=pair, evaluation=evaluation)
            results.append(run_result)
            _print_case_summary(config.project_root, run_result)
    finally:
        browser_manager.stop()

    report_paths = write_reports(config, results)
    logger.info("report written")
    logger.info("check results in this order:")
    logger.info("1. %s", report_paths["conversation"])
    logger.info("2. %s", report_paths["json"])
    logger.info("3. %s", report_paths["csv"])
    logger.info("4. %s", report_paths["summary"])
    logger.info("5. %s", config.chatbox_dir)
    return results
