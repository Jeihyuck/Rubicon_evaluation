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
from app.report_writer import format_case_console_block, write_reports
from app.samsung_rubicon import configure_runtime, run_single_case
from app.utils import artifact_timestamp, relative_to_root, sanitize_filename


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
            try:
                pair = run_single_case(session.page, test_case)
            finally:
                timestamp = artifact_timestamp()
                safe_case_id = sanitize_filename(test_case.id)
                trace_target = config.trace_dir / f"{timestamp}_{safe_case_id}.zip" if config.enable_trace else None
                video_target = config.video_dir / f"{timestamp}_{safe_case_id}.webm" if config.enable_video else None
                trace_path, video_path = session.close(trace_target=trace_target, video_target=video_target)

            pair = replace(
                pair,
                trace_path=relative_to_root(Path(trace_path) if trace_path else None, config.project_root),
                video_path=relative_to_root(Path(video_path) if video_path else None, config.project_root),
            )

            evaluation = evaluate_pair(config, test_case, pair, logger) if pair.answer else fallback_evaluation()
            result = RunResult(test_case=test_case, pair=pair, evaluation=evaluation)
            results.append(result)
            print(format_case_console_block(result), flush=True)
    finally:
        browser_manager.stop()

    report_paths = write_reports(config, results)
    logger.info("report written")
    print(f"Results JSON: {relative_to_root(Path(report_paths['json']), config.project_root)}", flush=True)
    print(f"Results CSV: {relative_to_root(Path(report_paths['csv']), config.project_root)}", flush=True)
    print(f"Summary: {relative_to_root(Path(report_paths['summary']), config.project_root)}", flush=True)
    print(f"Conversations: {relative_to_root(Path(report_paths['conversations']), config.project_root)}", flush=True)
    return results
