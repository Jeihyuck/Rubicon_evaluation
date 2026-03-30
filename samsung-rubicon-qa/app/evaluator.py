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
        fix_suggestion="Check logs and screenshots",
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
        "answer": pair.answer,
        "expected_keywords": test_case.expected_keywords,
        "forbidden_keywords": test_case.forbidden_keywords,
        "extraction_source": pair.extraction_source,
        "extraction_confidence": pair.extraction_confidence,
        "artifacts": {
            "full_screenshot_path": pair.full_screenshot_path,
            "chat_screenshot_path": pair.chat_screenshot_path,
            "video_path": pair.video_path,
            "trace_path": pair.trace_path,
            "html_fragment_path": pair.html_fragment_path,
        },
        "instructions": [
            "Consider whether the answer stays within a public, non-login flow.",
            "Lower clarity/completeness for vague, evasive, or incomplete answers.",
            "Set needs_human_review to true when the answer quality is weak or extraction confidence is low.",
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
