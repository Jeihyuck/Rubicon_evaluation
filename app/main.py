"""Main orchestrator: loads test cases, runs automation, evaluates, saves reports."""

from __future__ import annotations

import asyncio
from typing import List

from app.browser import browser_session
from app.config import AppConfig, config as default_config
from app.csv_loader import load_test_cases
from app.evaluator import evaluate_answer
from app.logger import logger, setup_logger
from app.models import RunResult
from app.report_writer import write_all_reports
from app.samsung_chat import run_single_question


async def _run_all(cfg: AppConfig) -> List[RunResult]:
    """Core async runner: executes all test cases and returns results."""
    logger.info("=== Samsung Chat QA – App Start ===")
    logger.info("Config loaded: base_url=%s, headless=%s, max_questions=%d",
                cfg.samsung_base_url, cfg.headless, cfg.max_questions)

    # Ensure output directories exist
    cfg.ensure_dirs()

    # Load test cases
    csv_path = cfg.testcases_dir / "questions.csv"
    test_cases = load_test_cases(csv_path, max_questions=cfg.max_questions)
    logger.info("CSV loaded: %d case(s)", len(test_cases))

    if not test_cases:
        logger.error("No test cases loaded – aborting run")
        return []

    results: List[RunResult] = []

    async with browser_session(cfg) as (ctx, page):
        for test_case in test_cases:
            logger.info("--- Running case: %s ---", test_case.id)
            result: RunResult = await run_single_question(page, test_case, cfg)

            # Evaluate answer via OpenAI (synchronous – runs in calling thread)
            eval_result = evaluate_answer(test_case, result, cfg)
            result.apply_eval(eval_result)
            logger.info(
                "Evaluation done for %s: overall=%.2f needs_review=%s",
                test_case.id, result.overall_score, result.needs_human_review,
            )

            results.append(result)

    logger.info("=== All cases complete. Total: %d ===", len(results))
    return results


def run(cfg: AppConfig | None = None) -> List[RunResult]:
    """Synchronous entry point for the orchestrator.

    Args:
        cfg: Optional :class:`AppConfig`; uses the global singleton if not provided.

    Returns:
        List of :class:`RunResult` objects.
    """
    if cfg is None:
        cfg = default_config

    # Re-initialise logger with correct reports dir (in case dirs weren't created yet)
    cfg.ensure_dirs()
    setup_logger(log_dir=cfg.reports_dir)

    results = asyncio.run(_run_all(cfg))

    # Write reports
    write_all_reports(results, cfg.reports_dir)
    logger.info("Reports written. Workflow finished.")

    return results
