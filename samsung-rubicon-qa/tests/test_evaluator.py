"""Tests for the OpenAI evaluator module."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from app.evaluator import (
    EVALUATION_SCHEMA,
    _capture_not_verified_evaluation,
    _coerce_eval_payload,
    _response_text,
    evaluate_pair,
    fallback_evaluation,
)
from app.models import EvalResult, ExtractedPair, TestCase


def _make_test_case() -> TestCase:
    return TestCase(
        id="c01",
        category="service",
        locale="ko-KR",
        page_url="https://www.samsung.com/sec/",
        question="배터리 교체는 어디서?",
        expected_keywords=["서비스센터", "배터리"],
        forbidden_keywords=["로그인"],
    )


def _make_pair(answer: str = "서비스센터에서 가능합니다.") -> ExtractedPair:
    return ExtractedPair(
        run_timestamp="2026-01-01T00:00:00+00:00",
        case_id="c01",
        category="service",
        page_url="https://www.samsung.com/sec/",
        locale="ko-KR",
        question="배터리 교체는 어디서?",
        answer=answer,
        extraction_source="dom",
        extraction_confidence=1.0,
        response_ms=1000,
        status="success",
        answer_raw=answer,
        answer_normalized=answer,
        input_dom_verified=True,
        submit_effect_verified=True,
        input_verified=True,
        input_method_used="fill",
        submit_method_used="button_click",
        new_bot_response_detected=True,
    )


def _make_config(api_key: str = "test-key"):
    from app.config import AppConfig
    from pathlib import Path

    return AppConfig(
        project_root=Path("/tmp/test"),
        openai_api_key=api_key,
        samsung_base_url="https://www.samsung.com/sec/",
        headless=True,
        default_locale="ko-KR",
        max_questions=5,
        openai_model="gpt-4o",
        playwright_timeout_ms=30000,
        answer_stable_checks=3,
        answer_stable_interval_sec=1.0,
        enable_video=False,
        enable_trace=False,
        enable_ocr_fallback=False,
        rubicon_chat_debug=False,
        rubicon_force_activation=True,
        rubicon_disable_sdk=False,
        rubicon_max_input_candidates=5,
        rubicon_frame_rescan_rounds=3,
        rubicon_before_send_screenshot=True,
        rubicon_opened_footer_screenshot=True,
        rubicon_after_answer_screenshot=True,
    )


class TestFallbackEvaluation:
    def test_returns_eval_result(self):
        result = fallback_evaluation()
        assert isinstance(result, EvalResult)

    def test_scores_are_zero(self):
        result = fallback_evaluation()
        assert result.overall_score == 0.0
        assert result.relevance_score == 0.0
        assert result.clarity_score == 0.0
        assert result.completeness_score == 0.0
        assert result.keyword_alignment_score == 0.0

    def test_hallucination_risk_is_high(self):
        result = fallback_evaluation()
        assert result.hallucination_risk == "high"

    def test_needs_human_review(self):
        result = fallback_evaluation()
        assert result.needs_human_review is True


class TestCaptureNotVerifiedEvaluation:
    def test_matches_mandated_reason(self):
        result = _capture_not_verified_evaluation()
        assert result.overall_score == 0.0
        assert result.needs_human_review is True
        assert result.reason == "Capture invalid: no verified submitted question and bot answer pair"


class TestCoerceEvalPayload:
    def test_valid_payload(self):
        payload = {
            "overall_score": 0.85,
            "relevance_score": 0.9,
            "clarity_score": 0.8,
            "completeness_score": 0.85,
            "keyword_alignment_score": 0.9,
            "hallucination_risk": "low",
            "needs_human_review": False,
            "reason": "Good answer",
            "fix_suggestion": "None needed",
        }
        result = _coerce_eval_payload(payload)
        assert result.overall_score == 0.85
        assert result.hallucination_risk == "low"
        assert result.needs_human_review is False
        assert result.reason == "Good answer"

    def test_partial_payload_uses_fallback_defaults(self):
        payload = {"overall_score": 0.5}
        result = _coerce_eval_payload(payload)
        assert result.overall_score == 0.5
        assert result.hallucination_risk == "high"

    def test_numeric_coercion(self):
        payload = {
            "overall_score": "0.75",
            "relevance_score": "0.8",
            "clarity_score": "0.7",
            "completeness_score": "0.8",
            "keyword_alignment_score": "0.9",
            "hallucination_risk": "medium",
            "needs_human_review": False,
            "reason": "ok",
            "fix_suggestion": "",
        }
        result = _coerce_eval_payload(payload)
        assert result.overall_score == 0.75
        assert result.clarity_score == 0.7


class TestResponseText:
    def test_output_text_attribute(self):
        mock_response = MagicMock()
        mock_response.output_text = "hello"
        assert _response_text(mock_response) == "hello"

    def test_model_dump_fallback(self):
        mock_response = MagicMock()
        mock_response.output_text = ""
        mock_response.model_dump.return_value = {
            "output": [
                {
                    "content": [
                        {"text": '{"overall_score": 0.9}'},
                    ]
                }
            ]
        }
        text = _response_text(mock_response)
        assert "overall_score" in text

    def test_empty_when_no_output(self):
        mock_response = MagicMock()
        mock_response.output_text = ""
        mock_response.model_dump.return_value = {"output": []}
        text = _response_text(mock_response)
        assert text == ""


class TestEvaluatePair:
    def test_fallback_when_no_api_key(self):
        config = _make_config(api_key="")
        logger = MagicMock()
        result = evaluate_pair(config, _make_test_case(), _make_pair(), logger)
        assert result.overall_score == 0.0
        assert result.needs_human_review is True

    def test_fallback_when_input_not_verified(self):
        config = _make_config(api_key="sk-test")
        logger = MagicMock()
        unverified_pair = _make_pair()
        # Override to unverified
        from dataclasses import replace
        unverified_pair = replace(unverified_pair, input_verified=False)
        result = evaluate_pair(config, _make_test_case(), unverified_pair, logger)
        assert result.overall_score == 0.0
        assert result.needs_human_review is True
        assert result.reason == "Capture invalid: no verified submitted question and bot answer pair"

    def test_fallback_when_invalid_capture(self):
        config = _make_config(api_key="sk-test")
        logger = MagicMock()
        from dataclasses import replace
        invalid_pair = replace(_make_pair(), status="invalid_capture", input_verified=False)
        result = evaluate_pair(config, _make_test_case(), invalid_pair, logger)
        assert result.overall_score == 0.0
        assert result.needs_human_review is True
        assert result.reason == "Invalid capture: capture_not_verified"

    def test_fallback_when_new_response_not_detected(self):
        config = _make_config(api_key="sk-test")
        logger = MagicMock()
        from dataclasses import replace

        pair = replace(_make_pair(), new_bot_response_detected=False)
        result = evaluate_pair(config, _make_test_case(), pair, logger)
        assert result.overall_score == 0.0
        assert result.reason == "Capture invalid: no verified submitted question and bot answer pair"

    def test_fallback_when_baseline_menu_detected(self):
        config = _make_config(api_key="sk-test")
        logger = MagicMock()
        from dataclasses import replace

        pair = replace(_make_pair(), baseline_menu_detected=True)
        result = evaluate_pair(config, _make_test_case(), pair, logger)
        assert result.overall_score == 0.0
        assert result.reason == "Capture invalid: no verified submitted question and bot answer pair"

    def test_fallback_when_submit_effect_not_verified(self):
        config = _make_config(api_key="sk-test")
        logger = MagicMock()
        from dataclasses import replace

        pair = replace(_make_pair(), submit_effect_verified=False, input_verified=False)
        result = evaluate_pair(config, _make_test_case(), pair, logger)
        assert result.overall_score == 0.0
        assert result.reason == "Capture invalid: no verified submitted question and bot answer pair"

    def test_fallback_when_answer_empty(self):
        config = _make_config(api_key="sk-test")
        logger = MagicMock()
        pair = _make_pair(answer="")
        result = evaluate_pair(config, _make_test_case(), pair, logger)
        assert result.overall_score == 0.0
        assert result.reason == "Capture invalid: no verified submitted question and bot answer pair"

    def test_evaluation_proceeds_when_echo_unverified_but_input_verified(self):
        """Echo check failure alone must not block evaluation."""
        import json
        config = _make_config(api_key="sk-test")
        logger = MagicMock()
        from dataclasses import replace
        # input verified, echo NOT verified — evaluation should still run
        pair_no_echo = replace(_make_pair(), user_message_echo_verified=False)
        payload = {
            "overall_score": 0.8,
            "relevance_score": 0.8,
            "clarity_score": 0.8,
            "completeness_score": 0.8,
            "keyword_alignment_score": 0.8,
            "hallucination_risk": "low",
            "needs_human_review": False,
            "reason": "ok",
            "fix_suggestion": "",
        }
        mock_response = MagicMock()
        mock_response.output_text = json.dumps(payload)
        with patch("app.evaluator.OpenAI") as mock_openai_cls:
            mock_client = MagicMock()
            mock_openai_cls.return_value = mock_client
            mock_client.responses.create.return_value = mock_response
            result = evaluate_pair(config, _make_test_case(), pair_no_echo, logger)
        assert result.overall_score == 0.8

    def test_openai_success(self):
        import json

        config = _make_config(api_key="sk-test")
        logger = MagicMock()
        payload = {
            "overall_score": 0.9,
            "relevance_score": 0.95,
            "clarity_score": 0.85,
            "completeness_score": 0.9,
            "keyword_alignment_score": 0.85,
            "hallucination_risk": "low",
            "needs_human_review": False,
            "reason": "Answer directly addresses the question.",
            "fix_suggestion": "",
        }

        mock_response = MagicMock()
        mock_response.output_text = json.dumps(payload)

        with patch("app.evaluator.OpenAI") as mock_openai_cls:
            mock_client = MagicMock()
            mock_openai_cls.return_value = mock_client
            mock_client.responses.create.return_value = mock_response

            result = evaluate_pair(config, _make_test_case(), _make_pair(), logger)

        assert result.overall_score == 0.9
        assert result.hallucination_risk == "low"
        assert result.needs_human_review is False

    def test_openai_exception_returns_fallback(self):
        config = _make_config(api_key="sk-test")
        logger = MagicMock()

        with patch("app.evaluator.OpenAI") as mock_openai_cls:
            mock_client = MagicMock()
            mock_openai_cls.return_value = mock_client
            mock_client.responses.create.side_effect = RuntimeError("API error")

            result = evaluate_pair(config, _make_test_case(), _make_pair(), logger)

        assert result.overall_score == 0.0
        assert result.needs_human_review is True


class TestEvaluationSchema:
    def test_schema_has_required_fields(self):
        required = EVALUATION_SCHEMA["required"]
        assert "overall_score" in required
        assert "hallucination_risk" in required
        assert "needs_human_review" in required
        assert "reason" in required

    def test_schema_disallows_additional_properties(self):
        assert EVALUATION_SCHEMA.get("additionalProperties") is False
