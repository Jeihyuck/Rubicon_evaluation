"""Tests for the data models."""

from __future__ import annotations

from dataclasses import asdict

import pytest

from app.models import (
    EvalResult,
    ExtractedPair,
    RunResult,
    TestCase,
)
from app.utils import utc_now_timestamp


def _make_test_case(case_id: str = "c01") -> TestCase:
    return TestCase(
        id=case_id,
        category="service",
        locale="ko-KR",
        page_url="https://www.samsung.com/sec/",
        question="배터리 교체는 어디서?",
        expected_keywords=["서비스센터", "배터리"],
        forbidden_keywords=["로그인"],
    )


def _make_pair(case_id: str = "c01") -> ExtractedPair:
    return ExtractedPair(
        run_timestamp=utc_now_timestamp(),
        case_id=case_id,
        category="service",
        page_url="https://www.samsung.com/sec/",
        locale="ko-KR",
        question="배터리 교체는 어디서?",
        answer="서비스센터에서 가능합니다.",
        extraction_source="dom",
        extraction_confidence=1.0,
        response_ms=1000,
        status="passed",
    )


def _make_eval() -> EvalResult:
    return EvalResult(
        overall_score=0.9,
        relevance_score=0.95,
        clarity_score=0.85,
        completeness_score=0.9,
        keyword_alignment_score=0.9,
        hallucination_risk="low",
        needs_human_review=False,
        reason="Good answer",
        fix_suggestion="",
    )


class TestTestCase:
    def test_fields(self):
        case = _make_test_case()
        assert case.id == "c01"
        assert case.expected_keywords == ["서비스센터", "배터리"]
        assert case.forbidden_keywords == ["로그인"]


class TestExtractedPair:
    def test_default_optional_fields(self):
        pair = _make_pair()
        assert pair.error_message == ""
        assert pair.full_screenshot_path == ""
        assert pair.chat_screenshot_path == ""
        assert pair.video_path == ""
        assert pair.trace_path == ""
        assert pair.html_fragment_path == ""
        assert pair.input_verified is False
        assert pair.input_method_used == ""
        assert pair.before_send_screenshot_path == ""
        assert pair.font_fix_applied is False


class TestRunResult:
    def test_to_nested_dict_structure(self):
        result = RunResult(
            test_case=_make_test_case(),
            pair=_make_pair(),
            evaluation=_make_eval(),
        )
        nested = result.to_nested_dict()
        assert "test_case" in nested
        assert "pair" in nested
        assert "evaluation" in nested
        assert nested["test_case"]["id"] == "c01"
        assert nested["pair"]["answer"] == "서비스센터에서 가능합니다."
        assert nested["evaluation"]["overall_score"] == 0.9

    def test_to_flat_dict_structure(self):
        result = RunResult(
            test_case=_make_test_case(),
            pair=_make_pair(),
            evaluation=_make_eval(),
        )
        flat = result.to_flat_dict()
        assert "id" in flat
        assert "pair_answer" in flat
        assert "eval_overall_score" in flat
        assert flat["id"] == "c01"
        assert flat["pair_answer"] == "서비스센터에서 가능합니다."
        assert flat["eval_overall_score"] == 0.9

    def test_to_flat_dict_no_key_conflicts(self):
        result = RunResult(
            test_case=_make_test_case(),
            pair=_make_pair(),
            evaluation=_make_eval(),
        )
        flat = result.to_flat_dict()
        pair_keys = {f"pair_{k}" for k in asdict(_make_pair())}
        eval_keys = {f"eval_{k}" for k in asdict(_make_eval())}
        case_keys = set(asdict(_make_test_case()).keys())
        all_expected = case_keys | pair_keys | eval_keys
        assert all_expected.issubset(flat.keys())
