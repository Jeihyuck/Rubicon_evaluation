"""Tests for the data models."""

from __future__ import annotations

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
        assert pair.question_echo == ""
        assert pair.message_history == []
        assert pair.full_screenshot_path == ""
        assert pair.chat_screenshot_path == ""
        assert pair.submitted_chat_screenshot_path == ""
        assert pair.answered_chat_screenshot_path == ""
        assert pair.video_path == ""
        assert pair.trace_path == ""
        assert pair.html_fragment_path == ""
        assert pair.evidence_markdown_path == ""
        assert pair.evidence_json_path == ""


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
        assert "case_id" in flat
        assert "answer" in flat
        assert "overall_score" in flat
        assert flat["case_id"] == "c01"
        assert flat["answer"] == "서비스센터에서 가능합니다."
        assert flat["overall_score"] == 0.9

    def test_to_flat_dict_no_key_conflicts(self):
        result = RunResult(
            test_case=_make_test_case(),
            pair=_make_pair(),
            evaluation=_make_eval(),
        )
        flat = result.to_flat_dict()
        all_expected = {
            "run_timestamp",
            "case_id",
            "category",
            "page_url",
            "locale",
            "question",
            "expected_keywords",
            "forbidden_keywords",
            "answer",
            "extraction_source",
            "extraction_confidence",
            "response_ms",
            "status",
            "error_message",
            "question_echo",
            "message_history",
            "full_screenshot_path",
            "chat_screenshot_path",
            "submitted_chat_screenshot_path",
            "answered_chat_screenshot_path",
            "video_path",
            "trace_path",
            "html_fragment_path",
            "evidence_markdown_path",
            "evidence_json_path",
            "overall_score",
            "relevance_score",
            "clarity_score",
            "completeness_score",
            "keyword_alignment_score",
            "hallucination_risk",
            "needs_human_review",
            "reason",
            "fix_suggestion",
        }
        assert all_expected.issubset(flat.keys())
