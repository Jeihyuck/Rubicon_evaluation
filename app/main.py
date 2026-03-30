"""Main orchestrator for Samsung Chat QA.

Loads test cases, runs each through the Samsung chat widget, evaluates with
OpenAI, and writes reports.  Exceptions in individual test cases do not abort
the overall run.
"""
from __future__ import annotations

import logging
import sys

from app.browser import BrowserManager
from app.config import Config, load_config
from app.csv_loader import load_test_cases
from app.evaluator import evaluate_answer
from app.logger import setup_logger
from app.models import RunResult
from app.report_writer import write_reports
from app.samsung_chat import run_single_question
from app.utils import now_utc_str

log: logging.Logger  # assigned after setup


def run(config: Config | None = None) -> int:
    """Execute the full QA pipeline.

    Parameters
    ----------
    config:
        Pre-built :class:`Config` instance.  When *None* a fresh one is
        loaded via :func:`~app.config.load_config`.

    Returns
    -------
    int
        Exit code: ``0`` for success (≥1 case passed), ``1`` otherwise.
    """
    global log

    if config is None:
        config = load_config()

    setup_logger(config.reports_dir / "runtime.log")
    log = logging.getLogger("samsung_chat_qa.main")

    log.info("=== Samsung Chat QA – run started ===")
    log.info("Config loaded: base_url=%s, headless=%s, model=%s", config.base_url, config.headless, config.openai_model)

    # --- Load test cases ---
    csv_path = config.testcases_dir / "questions.csv"
    try:
        test_cases = load_test_cases(csv_path, max_questions=config.max_questions)
    except FileNotFoundError as exc:
        log.error("Cannot load test cases: %s", exc)
        return 1

    if not test_cases:
        log.warning("No test cases found. Exiting.")
        return 0

    log.info("CSV loaded: %d test case(s).", len(test_cases))

    run_ts = now_utc_str("%Y-%m-%dT%H:%M:%SZ")
    results: list[RunResult] = []

    # --- Browser session ---
    with BrowserManager(config) as mgr:
        page = mgr.page
        log.info("Browser started.")

        for tc in test_cases:
            log.info("--- Running case: %s (%s) ---", tc.id, tc.category)

            result = RunResult(
                run_timestamp=run_ts,
                case_id=tc.id,
                category=tc.category,
                question=tc.question,
            )

            try:
                (
                    answer,
                    full_screenshot,
                    chat_screenshot,
                    response_ms,
                    status,
                    error_message,
                ) = run_single_question(page, tc, config)

                result.answer = answer
                result.full_screenshot_path = full_screenshot
                result.chat_screenshot_path = chat_screenshot
                result.response_ms = response_ms
                result.status = status
                result.error_message = error_message

            except Exception as exc:
                log.error("Unexpected error for case %s: %s", tc.id, exc, exc_info=True)
                result.status = "failed"
                result.error_message = str(exc)

            # --- Evaluate ---
            try:
                eval_res = evaluate_answer(
                    question=tc.question,
                    answer=result.answer,
                    page_url=tc.page_url or config.base_url,
                    locale=tc.locale or config.default_locale,
                    expected_keywords=tc.expected_keywords,
                    forbidden_keywords=tc.forbidden_keywords,
                    fullpage_screenshot_path=result.full_screenshot_path,
                    chat_screenshot_path=result.chat_screenshot_path,
                    config=config,
                )
            except Exception as exc:
                log.error("Evaluation error for case %s: %s", tc.id, exc, exc_info=True)
                from app.evaluator import _fallback_result
                eval_res = _fallback_result(str(exc))

            result.eval_result = eval_res
            result.overall_score = eval_res.overall_score
            result.needs_human_review = eval_res.needs_human_review
            result.hallucination_risk = eval_res.hallucination_risk
            result.reason = eval_res.reason
            result.fix_suggestion = eval_res.fix_suggestion

            log.info(
                "Evaluation complete for %s: score=%.2f, review=%s",
                tc.id,
                eval_res.overall_score,
                eval_res.needs_human_review,
            )
            results.append(result)

    # --- Write reports ---
    try:
        write_reports(results, config.reports_dir)
    except Exception as exc:
        log.error("Failed to write reports: %s", exc, exc_info=True)

    # --- Summary ---
    success_count = sum(1 for r in results if r.status == "success")
    log.info(
        "=== Run finished: %d/%d succeeded ===",
        success_count,
        len(results),
    )

    return 0 if success_count > 0 else 1


if __name__ == "__main__":
    sys.exit(run())
