"""Main orchestration for the Samsung Rubicon QA automation workflow."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path

from app.browser import BrowserManager
from app.config import load_config
from app.csv_loader import load_test_cases
from app.evaluator import evaluate_pair, fallback_evaluation
from app.logger import create_logger
from app.models import RunResult
from app.report_writer import write_reports
from app.samsung_rubicon import configure_runtime, run_single_case
from app.utils import artifact_timestamp, sanitize_filename


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
            video_target = config.video_dir / f"{timestamp}_{safe_case_id}.webm" if config.enable_video else None

            trace_path, video_path = session.close(trace_target=trace_target, video_target=video_target)
            pair = replace(pair, trace_path=trace_path, video_path=video_path)

            evaluation = (
                evaluate_pair(config, test_case, pair, logger)
                if pair.answer and pair.input_verified and pair.status != "invalid_capture"
                else fallback_evaluation()
            )
            results.append(RunResult(test_case=test_case, pair=pair, evaluation=evaluation))
    finally:
        browser_manager.stop()

    write_reports(config, results)
    logger.info("report written")
    return results
