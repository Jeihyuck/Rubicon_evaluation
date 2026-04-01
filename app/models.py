"""Data models used throughout the application."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class TestCase:
    """A single QA test case loaded from questions.csv."""

    id: str
    category: str
    locale: str
    page_url: str
    question: str
    expected_keywords: List[str] = field(default_factory=list)
    forbidden_keywords: List[str] = field(default_factory=list)


@dataclass
class EvalResult:
    """Structured evaluation result returned by the OpenAI evaluator."""

    overall_score: float = 0.0
    relevance_score: float = 0.0
    clarity_score: float = 0.0
    completeness_score: float = 0.0
    ui_consistency_score: float = 0.0
    hallucination_risk: str = "unknown"
    needs_human_review: bool = True
    reason: str = ""
    fix_suggestion: str = ""


@dataclass
class RunResult:
    """The combined result of running a single test case end-to-end."""

    run_timestamp: str = ""
    case_id: str = ""
    category: str = ""
    question: str = ""
    answer: str = ""
    response_ms: float = 0.0
    status: str = "pending"          # "success" | "failed"
    error_message: str = ""
    full_screenshot_path: str = ""
    chat_screenshot_path: str = ""

    # Evaluation fields (flattened from EvalResult)
    overall_score: float = 0.0
    relevance_score: float = 0.0
    clarity_score: float = 0.0
    completeness_score: float = 0.0
    ui_consistency_score: float = 0.0
    hallucination_risk: str = "unknown"
    needs_human_review: bool = True
    reason: str = ""
    fix_suggestion: str = ""

    def apply_eval(self, eval_result: EvalResult) -> None:
        """Copy evaluation fields from an EvalResult into this RunResult."""
        self.overall_score = eval_result.overall_score
        self.relevance_score = eval_result.relevance_score
        self.clarity_score = eval_result.clarity_score
        self.completeness_score = eval_result.completeness_score
        self.ui_consistency_score = eval_result.ui_consistency_score
        self.hallucination_risk = eval_result.hallucination_risk
        self.needs_human_review = eval_result.needs_human_review
        self.reason = eval_result.reason
        self.fix_suggestion = eval_result.fix_suggestion
