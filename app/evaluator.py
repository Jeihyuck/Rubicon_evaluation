"""OpenAI-based answer evaluator.

Uses the Responses API with Structured Outputs (``text.format`` / JSON Schema)
to score each QA result against multiple quality dimensions.
"""
from __future__ import annotations

import json
import logging
from typing import Any, Dict, List

from app.config import Config
from app.models import EvalResult

log = logging.getLogger("samsung_chat_qa.evaluator")

# ---------------------------------------------------------------------------
# JSON Schema for Structured Outputs
# ---------------------------------------------------------------------------

_EVAL_SCHEMA: Dict[str, Any] = {
    "type": "object",
    "properties": {
        "overall_score": {
            "type": "number",
            "description": "Overall quality score from 0.0 to 1.0.",
        },
        "relevance_score": {
            "type": "number",
            "description": "How directly the answer addresses the question (0-1).",
        },
        "clarity_score": {
            "type": "number",
            "description": "How clear and understandable the answer is (0-1).",
        },
        "completeness_score": {
            "type": "number",
            "description": "How complete and thorough the answer is (0-1).",
        },
        "ui_consistency_score": {
            "type": "number",
            "description": "Whether the answer is consistent with UI context (0-1).",
        },
        "hallucination_risk": {
            "type": "string",
            "enum": ["low", "medium", "high"],
            "description": "Estimated hallucination risk level.",
        },
        "needs_human_review": {
            "type": "boolean",
            "description": "True if a human should review this response.",
        },
        "reason": {
            "type": "string",
            "description": "Brief explanation for the scores.",
        },
        "fix_suggestion": {
            "type": "string",
            "description": "Actionable suggestion to improve the chatbot response.",
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

# ---------------------------------------------------------------------------
# Fallback result
# ---------------------------------------------------------------------------

def _fallback_result(reason: str = "OpenAI evaluation failed") -> EvalResult:
    return EvalResult(
        overall_score=0.0,
        relevance_score=0.0,
        clarity_score=0.0,
        completeness_score=0.0,
        ui_consistency_score=0.0,
        hallucination_risk="low",
        needs_human_review=True,
        reason=reason,
        fix_suggestion="Check runtime logs and screenshots.",
    )


# ---------------------------------------------------------------------------
# Main evaluator
# ---------------------------------------------------------------------------

def evaluate_answer(
    question: str,
    answer: str,
    page_url: str,
    locale: str,
    expected_keywords: List[str],
    forbidden_keywords: List[str],
    fullpage_screenshot_path: str,
    chat_screenshot_path: str,
    config: Config,
) -> EvalResult:
    """Call OpenAI to evaluate a chatbot answer.

    Parameters
    ----------
    question:          The question that was asked.
    answer:            The chatbot's response.
    page_url:          URL of the page where the question was asked.
    locale:            Locale string (e.g. ``en-US``).
    expected_keywords: Keywords that should appear in the answer.
    forbidden_keywords: Keywords that must *not* appear in the answer.
    fullpage_screenshot_path: Path to the full-page screenshot.
    chat_screenshot_path:     Path to the chat-area screenshot.
    config:            Application config (contains model name & API key).

    Returns
    -------
    EvalResult
        Structured evaluation result.  Never raises – returns a fallback
        :class:`EvalResult` on any error.
    """
    if not config.openai_api_key:
        log.warning("OPENAI_API_KEY not set; returning fallback evaluation.")
        return _fallback_result("OPENAI_API_KEY not set.")

    if not answer or not answer.strip():
        log.warning("Empty answer; returning fallback evaluation.")
        return _fallback_result("No answer text was provided for evaluation.")

    prompt = _build_prompt(
        question=question,
        answer=answer,
        page_url=page_url,
        locale=locale,
        expected_keywords=expected_keywords,
        forbidden_keywords=forbidden_keywords,
        fullpage_screenshot_path=fullpage_screenshot_path,
        chat_screenshot_path=chat_screenshot_path,
    )

    try:
        from openai import OpenAI  # lazy import to keep startup fast

        client = OpenAI(api_key=config.openai_api_key)

        response = client.responses.create(
            model=config.openai_model,
            input=prompt,
            text={
                "format": {
                    "type": "json_schema",
                    "name": "chatbot_evaluation",
                    "schema": _EVAL_SCHEMA,
                    "strict": True,
                }
            },
        )

        raw_json = response.output_text
        data = json.loads(raw_json)
        result = EvalResult(
            overall_score=float(data.get("overall_score", 0.0)),
            relevance_score=float(data.get("relevance_score", 0.0)),
            clarity_score=float(data.get("clarity_score", 0.0)),
            completeness_score=float(data.get("completeness_score", 0.0)),
            ui_consistency_score=float(data.get("ui_consistency_score", 0.0)),
            hallucination_risk=str(data.get("hallucination_risk", "low")),
            needs_human_review=bool(data.get("needs_human_review", False)),
            reason=str(data.get("reason", "")),
            fix_suggestion=str(data.get("fix_suggestion", "")),
        )
        log.info(
            "Evaluation complete: overall=%.2f, hallucination_risk=%s, needs_review=%s",
            result.overall_score,
            result.hallucination_risk,
            result.needs_human_review,
        )
        return result

    except Exception as exc:
        log.error("OpenAI evaluation error: %s", exc, exc_info=True)
        return _fallback_result(f"OpenAI evaluation failed: {exc}")


# ---------------------------------------------------------------------------
# Prompt builder
# ---------------------------------------------------------------------------

def _build_prompt(
    *,
    question: str,
    answer: str,
    page_url: str,
    locale: str,
    expected_keywords: List[str],
    forbidden_keywords: List[str],
    fullpage_screenshot_path: str,
    chat_screenshot_path: str,
) -> str:
    """Build the evaluation prompt string."""
    expected_kw_str = ", ".join(expected_keywords) if expected_keywords else "(none)"
    forbidden_kw_str = ", ".join(forbidden_keywords) if forbidden_keywords else "(none)"

    return (
        "You are an expert QA evaluator for a Samsung.com AI chatbot.\n\n"
        "Evaluate the following chatbot interaction and return a JSON object "
        "that exactly matches the provided schema.\n\n"
        f"**Page URL:** {page_url}\n"
        f"**Locale:** {locale}\n"
        f"**Question asked:** {question}\n"
        f"**Chatbot answer:**\n{answer}\n\n"
        f"**Expected keywords (should appear):** {expected_kw_str}\n"
        f"**Forbidden keywords (must NOT appear):** {forbidden_kw_str}\n\n"
        "Screenshot paths (for your reference; not accessible directly):\n"
        f"  Full page: {fullpage_screenshot_path}\n"
        f"  Chat area: {chat_screenshot_path}\n\n"
        "Evaluate the answer on the following criteria:\n"
        "1. Does the answer directly address the question?\n"
        "2. Is the answer clear and easy to understand?\n"
        "3. Is the answer sufficiently complete?\n"
        "4. Is the answer consistent with what a Samsung website UI should show?\n"
        "5. Are there signs of hallucination or incorrect information?\n"
        "6. Do expected keywords appear in the answer?\n"
        "7. Do any forbidden keywords appear in the answer?\n\n"
        "Assign scores between 0.0 and 1.0.  Set needs_human_review=true if "
        "any score is below 0.5 or if forbidden keywords are detected."
    )
