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
    status: Literal["passed", "failed", "invalid_capture"]
    reason: str = ""
    error_message: str = ""
    full_screenshot_path: str = ""
    chat_screenshot_path: str = ""
    video_path: str = ""
    trace_path: str = ""
    html_fragment_path: str = ""
    input_dom_verified: bool = False
    submit_effect_verified: bool = False
    input_verified: bool = False
    input_method_used: str = ""
    submit_method_used: str = "unknown"
    opened_chat_screenshot_path: str = ""
    opened_full_screenshot_path: str = ""
    before_send_screenshot_path: str = ""
    before_send_full_screenshot_path: str = ""
    after_send_screenshot_path: str = ""
    after_send_full_screenshot_path: str = ""
    after_answer_screenshot_path: str = ""
    after_answer_full_screenshot_path: str = ""
    font_fix_applied: bool = False
    user_message_echo_verified: bool = False
    new_bot_response_detected: bool = False
    baseline_menu_detected: bool = False
    message_history: list[str] = field(default_factory=list)


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

    def to_flat_dict(self) -> dict[str, Any]:
        """Flatten the result for CSV output."""

        data = asdict(self.test_case)
        data.update({f"pair_{key}": value for key, value in asdict(self.pair).items()})
        data.update({f"eval_{key}": value for key, value in asdict(self.evaluation).items()})
        return data

    def to_result_record(self) -> dict[str, Any]:
        """Build the primary result payload consumed by reports/latest_results.json."""

        return {
            "run_timestamp": self.pair.run_timestamp,
            "case_id": self.pair.case_id,
            "category": self.pair.category,
            "page_url": self.pair.page_url,
            "locale": self.pair.locale,
            "question": self.pair.question,
            "answer": self.pair.answer,
            "input_dom_verified": self.pair.input_dom_verified,
            "submit_effect_verified": self.pair.submit_effect_verified,
            "input_verified": self.pair.input_verified,
            "input_method_used": self.pair.input_method_used,
            "submit_method_used": self.pair.submit_method_used,
            "user_message_echo_verified": self.pair.user_message_echo_verified,
            "new_bot_response_detected": self.pair.new_bot_response_detected,
            "baseline_menu_detected": self.pair.baseline_menu_detected,
            "status": self.pair.status,
            "reason": self.pair.reason,
            "before_send_screenshot_path": self.pair.before_send_screenshot_path,
            "after_answer_screenshot_path": self.pair.after_answer_screenshot_path,
            "full_screenshot_path": self.pair.full_screenshot_path,
            "video_path": self.pair.video_path,
            "trace_path": self.pair.trace_path,
            "overall_score": self.evaluation.overall_score,
            "needs_human_review": self.evaluation.needs_human_review,
            "fix_suggestion": self.evaluation.fix_suggestion,
            "response_ms": self.pair.response_ms,
            "extraction_source": self.pair.extraction_source,
            "extraction_confidence": self.pair.extraction_confidence,
            "opened_chat_screenshot_path": self.pair.opened_chat_screenshot_path,
            "opened_full_screenshot_path": self.pair.opened_full_screenshot_path,
            "before_send_full_screenshot_path": self.pair.before_send_full_screenshot_path,
            "after_send_screenshot_path": self.pair.after_send_screenshot_path,
            "after_send_full_screenshot_path": self.pair.after_send_full_screenshot_path,
            "after_answer_full_screenshot_path": self.pair.after_answer_full_screenshot_path,
            "chat_screenshot_path": self.pair.chat_screenshot_path,
            "html_fragment_path": self.pair.html_fragment_path,
            "error_message": self.pair.error_message,
            "evaluation": asdict(self.evaluation),
        }


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
    baseline_bot_messages: list[str] = field(default_factory=list)
    baseline_history: list[str] = field(default_factory=list)
    baseline_visible_text: str = ""
    baseline_send_button_enabled: bool | None = None


@dataclass(slots=True)
class BrowserArtifacts:
    """File paths captured during or after a case run."""

    fullpage_screenshot: Path | None = None
    chatbox_screenshot: Path | None = None
    video_path: Path | None = None
    trace_path: Path | None = None
    html_fragment_path: Path | None = None
    before_send_screenshot_path: Path | None = None
