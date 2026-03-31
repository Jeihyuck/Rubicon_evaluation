"""Dataclasses used by the Samsung Rubicon QA workflow."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Literal


@dataclass(slots=True)
class TestCase:
    """Single chatbot QA scenario loaded from CSV."""

    id: str
    category: str
    locale: str
    page_url: str
    question: str
    expected_keywords: list[str] = field(default_factory=list)
    forbidden_keywords: list[str] = field(default_factory=list)


@dataclass(slots=True)
class ExtractedPair:
    """Structured question-answer pair extracted from the browser UI."""

    run_timestamp: str
    case_id: str
    category: str
    page_url: str
    locale: str
    question: str
    answer: str
    extraction_source: Literal["dom", "ocr", "unknown"]
    extraction_confidence: float
    response_ms: int
    status: Literal["passed", "failed"]
    error_message: str = ""
    question_echo: str = ""
    message_history: list[str] = field(default_factory=list)
    full_screenshot_path: str = ""
    chat_screenshot_path: str = ""
    submitted_chat_screenshot_path: str = ""
    answered_chat_screenshot_path: str = ""
    video_path: str = ""
    trace_path: str = ""
    html_fragment_path: str = ""
    evidence_markdown_path: str = ""
    evidence_json_path: str = ""


@dataclass(slots=True)
class EvalResult:
    """LLM evaluation outcome for an extracted pair."""

    overall_score: float
    relevance_score: float
    clarity_score: float
    completeness_score: float
    keyword_alignment_score: float
    hallucination_risk: Literal["low", "medium", "high"]
    needs_human_review: bool
    reason: str
    fix_suggestion: str


@dataclass(slots=True)
class RunResult:
    """Combined execution and evaluation result for a test case."""

    test_case: TestCase
    pair: ExtractedPair
    evaluation: EvalResult

    def to_nested_dict(self) -> dict[str, Any]:
        """Convert the result to a JSON-serializable dictionary."""

        return {
            "test_case": asdict(self.test_case),
            "pair": asdict(self.pair),
            "evaluation": asdict(self.evaluation),
        }

    def to_report_dict(self) -> dict[str, Any]:
        """Flatten the result using the report field names required by the project."""

        return {
            "run_timestamp": self.pair.run_timestamp,
            "case_id": self.pair.case_id,
            "category": self.pair.category,
            "page_url": self.pair.page_url,
            "locale": self.pair.locale,
            "question": self.pair.question,
            "expected_keywords": "|".join(self.test_case.expected_keywords),
            "forbidden_keywords": "|".join(self.test_case.forbidden_keywords),
            "answer": self.pair.answer,
            "extraction_source": self.pair.extraction_source,
            "extraction_confidence": self.pair.extraction_confidence,
            "response_ms": self.pair.response_ms,
            "status": self.pair.status,
            "error_message": self.pair.error_message,
            "question_echo": self.pair.question_echo,
            "message_history": " || ".join(self.pair.message_history),
            "full_screenshot_path": self.pair.full_screenshot_path,
            "chat_screenshot_path": self.pair.chat_screenshot_path,
            "submitted_chat_screenshot_path": self.pair.submitted_chat_screenshot_path,
            "answered_chat_screenshot_path": self.pair.answered_chat_screenshot_path,
            "video_path": self.pair.video_path,
            "trace_path": self.pair.trace_path,
            "html_fragment_path": self.pair.html_fragment_path,
            "evidence_markdown_path": self.pair.evidence_markdown_path,
            "evidence_json_path": self.pair.evidence_json_path,
            "overall_score": self.evaluation.overall_score,
            "relevance_score": self.evaluation.relevance_score,
            "clarity_score": self.evaluation.clarity_score,
            "completeness_score": self.evaluation.completeness_score,
            "keyword_alignment_score": self.evaluation.keyword_alignment_score,
            "hallucination_risk": self.evaluation.hallucination_risk,
            "needs_human_review": self.evaluation.needs_human_review,
            "reason": self.evaluation.reason,
            "fix_suggestion": self.evaluation.fix_suggestion,
        }

    def to_flat_dict(self) -> dict[str, Any]:
        """Backward-compatible alias used by tests and report generation."""

        return self.to_report_dict()


@dataclass(slots=True)
class ResolvedChatContext:
    """Resolved chat widget references for the current case."""

    scope: Any
    scope_name: str
    input_locator: Any
    send_locator: Any | None
    container_locator: Any | None
    bot_message_candidates: list[dict[str, Any]]
    history_candidates: list[dict[str, Any]]
    loading_candidates: list[dict[str, Any]]
    baseline_bot_count: int = 0
    baseline_last_answer: str = ""


@dataclass(slots=True)
class BrowserArtifacts:
    """File paths captured during or after a case run."""

    fullpage_screenshot: Path | None = None
    chatbox_screenshot: Path | None = None
    video_path: Path | None = None
    trace_path: Path | None = None
    html_fragment_path: Path | None = None
