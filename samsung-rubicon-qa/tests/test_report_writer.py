"""Tests for report writing utilities."""

from __future__ import annotations

import json
import tempfile
from dataclasses import replace
from pathlib import Path

import pytest

from app.config import AppConfig
from app.evaluator import fallback_evaluation
from app.models import EvalResult, ExtractedPair, RunResult, TestCase
from app.report_writer import _build_summary, write_reports
from app.utils import utc_now_timestamp


def _make_config(tmpdir: str) -> AppConfig:
    root = Path(tmpdir)
    return AppConfig(
        project_root=root,
        openai_api_key="",
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


def _make_result(case_id: str = "c01", status: str = "success", score: float = 0.8) -> RunResult:
    test_case = TestCase(
        id=case_id,
        category="service",
        locale="ko-KR",
        page_url="https://www.samsung.com/sec/",
        question="배터리 교체는 어디서?",
        expected_keywords=["서비스센터"],
        forbidden_keywords=["로그인"],
    )
    pair = ExtractedPair(
        run_timestamp=utc_now_timestamp(),
        case_id=case_id,
        category="service",
        page_url="https://www.samsung.com/sec/",
        locale="ko-KR",
        question="배터리 교체는 어디서?",
        answer="서비스센터에서 가능합니다.",
        extraction_source="dom",
        extraction_confidence=1.0,
        response_ms=1200,
        status=status,
        answer_raw="서비스센터에서 가능합니다.",
        answer_normalized="서비스센터에서 가능합니다.",
        actual_answer="서비스센터에서 가능합니다.",
        actual_answer_clean="서비스센터에서 가능합니다.",
        error_message="" if status == "success" else "timeout",
    )
    evaluation = EvalResult(
        overall_score=score,
        relevance_score=score,
        clarity_score=score,
        completeness_score=score,
        keyword_alignment_score=score,
        hallucination_risk="low",
        needs_human_review=False,
        reason="Good answer",
        fix_suggestion="",
    )
    return RunResult(test_case=test_case, pair=pair, evaluation=evaluation)


class TestWriteReports:
    def test_creates_all_report_files(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            config = _make_config(tmpdir)
            config.ensure_directories()
            results = [_make_result("c01"), _make_result("c02")]
            paths = write_reports(config, results)
            assert Path(paths["json"]).exists()
            assert Path(paths["csv"]).exists()
            assert Path(paths["summary"]).exists()

    def test_json_report_is_valid(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            config = _make_config(tmpdir)
            config.ensure_directories()
            results = [_make_result("c01")]
            paths = write_reports(config, results)
            data = json.loads(Path(paths["json"]).read_text(encoding="utf-8"))
            assert isinstance(data, list)
            assert len(data) == 1
            assert data[0]["case_id"] == "c01"
            assert data[0]["question"] == "배터리 교체는 어디서?"
            assert "evaluation" in data[0]

    def test_csv_report_has_expected_columns(self):
        import csv as csv_module

        with tempfile.TemporaryDirectory() as tmpdir:
            config = _make_config(tmpdir)
            config.ensure_directories()
            results = [_make_result("c01")]
            paths = write_reports(config, results)
            with Path(paths["csv"]).open(encoding="utf-8") as fh:
                reader = csv_module.DictReader(fh)
                rows = list(reader)
            assert len(rows) == 1
            assert "id" in rows[0]
            assert "input_scope" in rows[0]
            assert "open_method_used" in rows[0]
            assert "availability_status" in rows[0]
            assert "pair_answer" in rows[0]
            assert "eval_overall_score" in rows[0]

    def test_empty_results_writes_valid_files(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            config = _make_config(tmpdir)
            config.ensure_directories()
            paths = write_reports(config, [])
            data = json.loads(Path(paths["json"]).read_text(encoding="utf-8"))
            assert data == []


class TestBuildSummary:
    def test_summary_counts(self):
        results = [
            _make_result("c01", status="success", score=0.9),
            _make_result("c02", status="failed", score=0.2),
        ]
        summary = _build_summary(results)
        assert "총 케이스 수: 2" in summary
        assert "성공 수: 1" in summary
        assert "실패 수: 1" in summary

    def test_summary_dom_extraction_count(self):
        results = [_make_result("c01"), _make_result("c02")]
        summary = _build_summary(results)
        assert "DOM 추출 성공 수: 2" in summary

    def test_summary_includes_lowest_score_case(self):
        results = [
            _make_result("c01", score=0.9),
            _make_result("c02", score=0.3),
        ]
        summary = _build_summary(results)
        assert "최저 점수 케이스" in summary
        assert "c02" in summary

    def test_summary_error_cases_section(self):
        results = [_make_result("c01", status="failed")]
        summary = _build_summary(results)
        assert "에러 케이스" in summary
        assert "c01" in summary

    def test_empty_results(self):
        summary = _build_summary([])
        assert "총 케이스 수: 0" in summary


class TestBuildConversation:
    """Tests for the per-case evidence conversation report."""

    def test_conversation_report_is_written(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            config = _make_config(tmpdir)
            config.ensure_directories()
            results = [_make_result("c01")]
            paths = write_reports(config, results)
            assert "conversation" in paths
            assert Path(paths["conversation"]).name == "latest_conversation.md"
            content = Path(paths["conversation"]).read_text(encoding="utf-8")
            assert "c01" in content

    def test_conversation_contains_question(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            config = _make_config(tmpdir)
            config.ensure_directories()
            results = [_make_result("c01")]
            paths = write_reports(config, results)
            content = Path(paths["conversation"]).read_text(encoding="utf-8")
            assert "배터리 교체는 어디서?" in content

    def test_conversation_shows_new_response_flag(self):
        """Conversation report includes the strict post-baseline response flag."""

        result = _make_result("c01")
        result = replace(
            result,
            pair=replace(result.pair, new_bot_response_detected=True),
        )
        with tempfile.TemporaryDirectory() as tmpdir:
            config = _make_config(tmpdir)
            config.ensure_directories()
            paths = write_reports(config, [result])
            content = Path(paths["conversation"]).read_text(encoding="utf-8")
        assert "New Bot Response Detected: True" in content

    def test_conversation_contains_required_labels(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            config = _make_config(tmpdir)
            config.ensure_directories()
            paths = write_reports(config, [_make_result("c01")])
            content = Path(paths["conversation"]).read_text(encoding="utf-8")
        assert "Input DOM Verified:" in content
        assert "Submit Effect Verified:" in content
        assert "Input Method:" in content
        assert "Submit Method Used:" in content
        assert "Input Scope:" in content
        assert "Input Selector:" in content
        assert "Input Candidate Score:" in content
        assert "Input Failure Category:" in content
        assert "Input Failure Reason:" in content
        assert "User Message Echo Verified:" in content
        assert "New Bot Response Detected:" in content
        assert "Top Candidate Disabled:" in content
        assert "Activation Attempted:" in content
        assert "Activation Steps Tried:" in content
        assert "Editable Candidates Count:" in content
        assert "Failover Attempts:" in content
        assert "Final Input Target Frame:" in content
        assert "SDK Status:" in content
        assert "Availability Status:" in content
        assert "Open Method Used:" in content
        assert "Actual Answer:" in content
        assert "Actual Answer Clean:" in content
        assert "Answer Raw:" in content
        assert "Extraction Source:" in content
        assert "Message History Clean:" in content
        assert "Before Send Screenshot:" in content
        assert "After Answer Screenshot:" in content
        assert "Fullpage Screenshot:" in content
        assert "Chat Screenshot:" in content
        assert "Opened Footer Screenshot:" in content
        assert "### Input Candidates (c01)" in content
        assert "### Answer Extraction Debug (c01)" in content

    def test_conversation_empty_history(self):
        """Message History shows '(empty)' when no history is captured."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config = _make_config(tmpdir)
            config.ensure_directories()
            results = [_make_result("c01")]
            paths = write_reports(config, results)
            content = Path(paths["conversation"]).read_text(encoding="utf-8")
        assert "### Message History (c01)" in content
        assert "- (empty)" in content

    def test_conversation_populated_history(self):
        """Message History lists each message when history is captured."""

        result = _make_result("c01")
        result = replace(
            result,
            pair=replace(result.pair, message_history=["안녕하세요.", "서비스센터입니다."], message_history_clean="안녕하세요.\n서비스센터입니다."),
        )
        with tempfile.TemporaryDirectory() as tmpdir:
            config = _make_config(tmpdir)
            config.ensure_directories()
            paths = write_reports(config, [result])
            content = Path(paths["conversation"]).read_text(encoding="utf-8")
        assert "- 안녕하세요." in content
        assert "- 서비스센터입니다." in content
        assert "Message History Clean: 안녕하세요.\n서비스센터입니다." in content

    def test_conversation_shows_answer_extraction_debug_fields(self):
        result = _make_result("c01")
        result = replace(
            result,
            pair=replace(
                result.pair,
                extraction_source_detail="dom_main_answer",
                removed_followups=True,
                noise_lines_removed=3,
            ),
        )
        with tempfile.TemporaryDirectory() as tmpdir:
            config = _make_config(tmpdir)
            config.ensure_directories()
            paths = write_reports(config, [result])
            content = Path(paths["conversation"]).read_text(encoding="utf-8")
        assert "selected_source=dom_main_answer" in content
        assert "removed_followups=True" in content
        assert "noise_lines_removed=3" in content

    def test_conversation_populated_input_candidates(self):
        result = _make_result("c01")
        result = replace(
            result,
            pair=replace(
                result.pair,
                input_scope_name="spr-chat__box-frame",
                input_scope="frame[1]",
                input_selector="textarea",
                input_candidate_score=28,
                input_failure_category="input locator found but disabled",
                input_failure_reason="Input candidate exists but is disabled",
                input_candidates_debug="score=28 selector=textarea visible=True editable=False disabled=True reason=disabled",
                input_candidate_logs=["scope=spr-chat__box-frame score=28 selector=textarea index=0"],
            ),
        )
        with tempfile.TemporaryDirectory() as tmpdir:
            config = _make_config(tmpdir)
            config.ensure_directories()
            paths = write_reports(config, [result])
            content = Path(paths["conversation"]).read_text(encoding="utf-8")
        assert "Input Scope: frame[1]" in content
        assert "Input Selector: textarea" in content
        assert "Input Candidate Score: 28" in content
        assert "Input Failure Category: input locator found but disabled" in content
        assert "score=28 selector=textarea visible=True editable=False disabled=True reason=disabled" in content


    def test_summary_mentions_latest_conversation_priority(self):
        summary = _build_summary([_make_result("c01")])
        assert "reports/latest_conversation.md" in summary
        assert "reports/latest_results.csv" in summary

    def test_conversation_md022_md032_compliance(self):
        """Generated markdown must satisfy MD022 (blank lines around headings) and MD032 (blank lines around lists)."""
        results = [_make_result("c01"), _make_result("c02")]
        from app.report_writer import _build_conversation

        content = _build_conversation(results)
        lines = content.split("\n")
        for i, line in enumerate(lines):
            # MD022: every heading must be followed by a blank line
            if line.startswith("#"):
                assert i + 1 < len(lines) and lines[i + 1] == "", (
                    f"MD022 violation: heading at line {i + 1} ({line!r}) "
                    f"not followed by blank line; next line={lines[i + 1]!r}"
                )
            # MD032: a list item must not immediately follow a heading (blank line required between them)
            if line.startswith("- ") and i > 0 and lines[i - 1].startswith("#"):
                raise AssertionError(
                    f"MD032 violation: list item at line {i + 1} ({line!r}) "
                    f"immediately follows heading ({lines[i - 1]!r})"
                )
