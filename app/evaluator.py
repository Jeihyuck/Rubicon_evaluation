"""OpenAI-based answer evaluator using Responses API + Structured Outputs."""

from __future__ import annotations

import json
from typing import Any, Dict

from app.config import AppConfig
from app.logger import logger
from app.models import EvalResult, RunResult, TestCase

# ---------------------------------------------------------------------------
# JSON Schema for structured output
# ---------------------------------------------------------------------------

EVAL_SCHEMA: Dict[str, Any] = {
    "type": "object",
    "properties": {
        "overall_score": {
            "type": "number",
            "description": "Overall quality score from 0.0 to 1.0",
        },
        "relevance_score": {
            "type": "number",
            "description": "How directly the answer addresses the question (0.0–1.0)",
        },
        "clarity_score": {
            "type": "number",
            "description": "How clearly and concisely the answer is written (0.0–1.0)",
        },
        "completeness_score": {
            "type": "number",
            "description": "How thoroughly the answer covers the question (0.0–1.0)",
        },
        "ui_consistency_score": {
            "type": "number",
            "description": "Whether the answer is consistent with the UI context (0.0–1.0)",
        },
        "hallucination_risk": {
            "type": "string",
            "enum": ["low", "medium", "high"],
            "description": "Estimated risk of factual hallucination",
        },
        "needs_human_review": {
            "type": "boolean",
            "description": "True if a human should review this answer",
        },
        "reason": {
            "type": "string",
            "description": "Concise explanation of the evaluation scores",
        },
        "fix_suggestion": {
            "type": "string",
            "description": "Actionable suggestion for improving the answer or UI flow",
        },
    },
    "required": [
        "overall_score",
        "relevance_score",
        "clarity_score",
        "completeness_score",
        "ui_consistency_score",
        "hallucination_risk",
        "needs_human_review",
        "reason",
        "fix_suggestion",
    ],
    "additionalProperties": False,
}


def _fallback_result(reason: str = "OpenAI evaluation failed") -> EvalResult:
    """Return a safe fallback EvalResult when evaluation cannot complete."""
    return EvalResult(
        overall_score=0.0,
        relevance_score=0.0,
        clarity_score=0.0,
        completeness_score=0.0,
        ui_consistency_score=0.0,
        hallucination_risk="unknown",
        needs_human_review=True,
        reason=reason,
        fix_suggestion="Check runtime logs and screenshots",
    )


def _build_prompt(
    question: str,
    answer: str,
    page_url: str,
    locale: str,
    expected_keywords: list[str],
    forbidden_keywords: list[str],
) -> str:
    """Build the evaluation prompt sent to the OpenAI model."""
    expected = ", ".join(expected_keywords) if expected_keywords else "(none)"
    forbidden = ", ".join(forbidden_keywords) if forbidden_keywords else "(none)"

    return f"""You are a QA evaluator for a Samsung AI chatbot.

Evaluate the following chatbot interaction:

Question: {question}
Answer: {answer}
Page URL: {page_url}
Locale: {locale}
Expected keywords (should appear): {expected}
Forbidden keywords (must NOT appear): {forbidden}

Score each dimension from 0.0 to 1.0:
- overall_score: weighted average of all dimensions
- relevance_score: does the answer directly address the question?
- clarity_score: is the answer clear and concise?
- completeness_score: is the answer sufficiently complete?
- ui_consistency_score: is the answer appropriate for the UI/brand context?
- hallucination_risk: low / medium / high

Set needs_human_review=true if overall_score < 0.6 OR hallucination_risk == "high" OR any forbidden keyword appears.

Provide a concise reason and a fix_suggestion.
"""


def evaluate_answer(
    test_case: TestCase,
    run_result: RunResult,
    cfg: AppConfig,
) -> EvalResult:
    """Evaluate the chatbot answer using the OpenAI Responses API.

    Uses Structured Outputs (``text.format`` with JSON Schema) to guarantee
    a parseable response. Falls back gracefully on any error.
    """
    if not cfg.openai_api_key:
        logger.warning("OPENAI_API_KEY not set; skipping evaluation for case %s", test_case.id)
        return _fallback_result("OPENAI_API_KEY not configured")

    if not run_result.answer:
        logger.warning("No answer text for case %s; skipping evaluation", test_case.id)
        return _fallback_result("No answer text available for evaluation")

    try:
        from openai import OpenAI  # lazy import – not required for browser automation

        client = OpenAI(api_key=cfg.openai_api_key)

        prompt = _build_prompt(
            question=test_case.question,
            answer=run_result.answer,
            page_url=test_case.page_url or cfg.samsung_base_url,
            locale=test_case.locale,
            expected_keywords=test_case.expected_keywords,
            forbidden_keywords=test_case.forbidden_keywords,
        )

        logger.debug("Calling OpenAI model %s for case %s", cfg.openai_model, test_case.id)

        response = client.responses.create(
            model=cfg.openai_model,
            input=prompt,
            text={
                "format": {
                    "type": "json_schema",
                    "name": "evaluation_result",
                    "schema": EVAL_SCHEMA,
                    "strict": True,
                }
            },
        )

        raw = response.output_text
        data: Dict[str, Any] = json.loads(raw)

        eval_result = EvalResult(
            overall_score=float(data.get("overall_score", 0.0)),
            relevance_score=float(data.get("relevance_score", 0.0)),
            clarity_score=float(data.get("clarity_score", 0.0)),
            completeness_score=float(data.get("completeness_score", 0.0)),
            ui_consistency_score=float(data.get("ui_consistency_score", 0.0)),
            hallucination_risk=str(data.get("hallucination_risk", "unknown")),
            needs_human_review=bool(data.get("needs_human_review", True)),
            reason=str(data.get("reason", "")),
            fix_suggestion=str(data.get("fix_suggestion", "")),
        )

        logger.info(
            "Evaluation complete for case %s: overall=%.2f, review=%s",
            test_case.id,
            eval_result.overall_score,
            eval_result.needs_human_review,
        )
        return eval_result

    except Exception as exc:
        logger.exception("OpenAI evaluation failed for case %s: %s", test_case.id, exc)
        return _fallback_result(f"OpenAI evaluation failed: {exc}")
