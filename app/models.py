"""Data models for Samsung Chat QA.

All models are plain Python dataclasses.  Fields intentionally use simple
built-in types so they are easy to serialise to JSON/CSV.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class TestCase:
    """One row from ``testcases/questions.csv``."""

    id: str
    category: str
    locale: str
    page_url: str
    question: str
    expected_keywords: List[str] = field(default_factory=list)
    forbidden_keywords: List[str] = field(default_factory=list)


@dataclass
class EvalResult:
    """Structured output returned by the OpenAI evaluator."""

    overall_score: float = 0.0
    relevance_score: float = 0.0
    clarity_score: float = 0.0
    completeness_score: float = 0.0
    ui_consistency_score: float = 0.0
    hallucination_risk: str = "low"
    needs_human_review: bool = False
    reason: str = ""
    fix_suggestion: str = ""


@dataclass
class RunResult:
    """Combined outcome for a single test-case execution."""

    run_timestamp: str = ""
    case_id: str = ""
    category: str = ""
    question: str = ""
    answer: str = ""
    response_ms: float = 0.0
    status: str = "pending"           # "success" | "failed" | "pending"
    error_message: str = ""
    overall_score: float = 0.0
    needs_human_review: bool = False
    hallucination_risk: str = "low"
    reason: str = ""
    fix_suggestion: str = ""
    full_screenshot_path: str = ""
    chat_screenshot_path: str = ""
    # Evaluation detail (not written to flat CSV)
    eval_result: Optional[EvalResult] = field(default=None, repr=False)

    def to_flat_dict(self) -> dict:
        """Return a dict suitable for CSV / JSON serialisation (no nested objects)."""
        return {
            "run_timestamp": self.run_timestamp,
            "case_id": self.case_id,
            "category": self.category,
            "question": self.question,
            "answer": self.answer,
            "response_ms": self.response_ms,
            "status": self.status,
            "error_message": self.error_message,
            "overall_score": self.overall_score,
            "needs_human_review": self.needs_human_review,
            "hallucination_risk": self.hallucination_risk,
            "reason": self.reason,
            "fix_suggestion": self.fix_suggestion,
            "full_screenshot_path": self.full_screenshot_path,
            "chat_screenshot_path": self.chat_screenshot_path,
        }
