"""OpenAI-based structured evaluation for extracted QA pairs."""

from __future__ import annotations

import json
from dataclasses import asdict
from typing import Any

from openai import OpenAI

from app.config import AppConfig
from app.models import EvalResult, ExtractedPair, TestCase


EVALUATION_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "overall_score": {"type": "number"},
        "relevance_score": {"type": "number"},
        "clarity_score": {"type": "number"},
        "completeness_score": {"type": "number"},
        "keyword_alignment_score": {"type": "number"},
        "hallucination_risk": {
            "type": "string",
            "enum": ["low", "medium", "high"],
        },
        "needs_human_review": {"type": "boolean"},
        "reason": {"type": "string"},
        "fix_suggestion": {"type": "string"},
    },
    "required": [
        "overall_score",
        "relevance_score",
        "clarity_score",
        "completeness_score",
        "keyword_alignment_score",
        "hallucination_risk",
        "needs_human_review",
        "reason",
        "fix_suggestion",
    ],
}


def fallback_evaluation() -> EvalResult:
    """Return the mandated fallback JSON payload as a dataclass."""

    return EvalResult(
        overall_score=0.0,
        relevance_score=0.0,
        clarity_score=0.0,
        completeness_score=0.0,
        keyword_alignment_score=0.0,
        hallucination_risk="high",
        needs_human_review=True,
        reason="OpenAI evaluation failed",
        fix_suggestion="Check before_send/after_send screenshots and submission logs",
    )


def _capture_not_verified_evaluation() -> EvalResult:
    """Return the mandated evaluation payload for invalid or unverified captures."""

    return EvalResult(
        overall_score=0.0,
        relevance_score=0.0,
        clarity_score=0.0,
        completeness_score=0.0,
        keyword_alignment_score=0.0,
        hallucination_risk="high",
        needs_human_review=True,
        reason="Capture invalid: no verified submitted question and bot answer pair",
        fix_suggestion="Check before_send/after_send screenshots, frame selection, and message diff logs",
    )


def _invalid_capture_evaluation(pair: ExtractedPair) -> EvalResult:
    return EvalResult(
        overall_score=0.0,
        relevance_score=0.0,
        clarity_score=0.0,
        completeness_score=0.0,
        keyword_alignment_score=0.0,
        hallucination_risk="high",
        needs_human_review=True,
        reason=f"Invalid capture: {pair.input_failure_category or pair.reason or 'capture_not_verified'}",
        fix_suggestion=pair.fix_suggestion or "Check runtime.log prefixes, activation steps, and screenshots",
    )


def _failed_answer_evaluation(pair: ExtractedPair) -> EvalResult:
    return EvalResult(
        overall_score=0.0,
        relevance_score=0.0,
        clarity_score=0.0,
        completeness_score=0.0,
        keyword_alignment_score=0.0,
        hallucination_risk="high",
        needs_human_review=True,
        reason=pair.reason or "Execution failed before a valid answer was extracted",
        fix_suggestion=pair.fix_suggestion or "Check open, submission, and extraction logs",
    )


def _coerce_eval_payload(payload: dict[str, Any]) -> EvalResult:
    """Normalize model JSON to the required dataclass schema."""

    fallback = asdict(fallback_evaluation())
    fallback.update(payload)
    return EvalResult(
        overall_score=float(fallback["overall_score"]),
        relevance_score=float(fallback["relevance_score"]),
        clarity_score=float(fallback["clarity_score"]),
        completeness_score=float(fallback["completeness_score"]),
        keyword_alignment_score=float(fallback["keyword_alignment_score"]),
        hallucination_risk=str(fallback["hallucination_risk"]),
        needs_human_review=bool(fallback["needs_human_review"]),
        reason=str(fallback["reason"]),
        fix_suggestion=str(fallback["fix_suggestion"]),
    )


def _response_text(response: Any) -> str:
    """Extract textual output from an OpenAI Responses API result."""

    direct_text = getattr(response, "output_text", "")
    if direct_text:
        return direct_text

    try:
        dumped = response.model_dump()
    except Exception:
        return ""

    output_chunks = dumped.get("output", [])
    parts: list[str] = []
    for item in output_chunks:
        for content in item.get("content", []):
            text = content.get("text") or content.get("value")
            if text:
                parts.append(text)
    return "\n".join(parts).strip()


def evaluate_pair(config: AppConfig, test_case: TestCase, pair: ExtractedPair, logger: Any) -> EvalResult:
    """Evaluate a question-answer pair with OpenAI Structured Outputs."""

    if pair.status == "invalid_capture":
        logger.warning(
            "Capture invalid for case %s (%s); using invalid-capture fallback evaluation",
            pair.case_id,
            pair.input_failure_category or pair.reason,
        )
        logger.info("evaluation completed")
        return _invalid_capture_evaluation(pair)

    if pair.status == "failed" and (not pair.answer_raw or pair.input_failure_category == "answer_not_extracted"):
        logger.warning(
            "Execution failed for case %s (%s); using failed-answer fallback evaluation",
            pair.case_id,
            pair.input_failure_category or pair.reason,
        )
        logger.info("evaluation completed")
        return _failed_answer_evaluation(pair)

    if (
        not pair.answer_raw
        or not pair.answer_normalized
        or pair.answer_normalized == "(none)"
        or not pair.input_verified
        or not pair.submit_effect_verified
        or not pair.new_bot_response_detected
        or pair.baseline_menu_detected
    ):
        logger.warning(
            "Capture verification failed for case %s (status=%s); skipping GPT evaluation",
            pair.case_id,
            pair.status,
        )
        logger.info("evaluation completed")
        return _capture_not_verified_evaluation()

    if not config.openai_api_key:
        logger.warning("OpenAI API key missing; using fallback evaluation")
        logger.info("evaluation completed")
        return fallback_evaluation()

    client = OpenAI(api_key=config.openai_api_key)
    system_prompt = (
        "You are evaluating a browser-captured chatbot response from samsung.com/sec/. "
        "Score whether the answer directly addresses the question, remains clear, complete, "
        "and aligned to expected keywords without forbidden content or login-only guidance. "
        "Return JSON only matching the provided schema."
    )
    user_prompt = {
        "page_url": pair.page_url,
        "locale": pair.locale,
        "question": pair.question,
        "answer": pair.answer_normalized,
        "expected_keywords": test_case.expected_keywords,
        "forbidden_keywords": test_case.forbidden_keywords,
        "input_verified": pair.input_verified,
        "submit_effect_verified": pair.submit_effect_verified,
        "new_bot_response_detected": pair.new_bot_response_detected,
        "baseline_menu_detected": pair.baseline_menu_detected,
        "instructions": [
            "Evaluate only the real post-baseline bot response captured from samsung.com/sec/.",
            "Score relevance, clarity, completeness, keyword alignment, and hallucination risk.",
            "Lower the score for vague, evasive, incomplete, or unsupported answers.",
            "Set needs_human_review to true when the answer quality is weak or uncertain.",
        ],
    }

    try:
        response = client.responses.create(
            model=config.openai_model,
            input=[
                {
                    "role": "system",
                    "content": [{"type": "input_text", "text": system_prompt}],
                },
                {
                    "role": "user",
                    "content": [{"type": "input_text", "text": json.dumps(user_prompt, ensure_ascii=False)}],
                },
            ],
            text={
                "format": {
                    "type": "json_schema",
                    "name": "rubicon_ui_qa_evaluation",
                    "schema": EVALUATION_SCHEMA,
                    "strict": True,
                }
            },
        )
        payload = json.loads(_response_text(response))
        result = _coerce_eval_payload(payload)
        logger.info("evaluation completed")
        return result
    except Exception as exc:
        logger.exception("OpenAI evaluation failed: %s", exc)
        logger.info("evaluation completed")
        return fallback_evaluation()
