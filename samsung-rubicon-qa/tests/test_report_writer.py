"""Tests for report writing utilities."""

from __future__ import annotations

import json
import tempfile
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
    )


def _make_result(case_id: str = "c01", status: str = "passed", score: float = 0.8) -> RunResult:
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
        error_message="" if status == "passed" else "timeout",
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
            assert data[0]["test_case"]["id"] == "c01"
            assert "pair" in data[0]
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
            _make_result("c01", status="passed", score=0.9),
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
