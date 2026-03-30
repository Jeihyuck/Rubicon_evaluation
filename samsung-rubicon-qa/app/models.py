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
    full_screenshot_path: str = ""
    chat_screenshot_path: str = ""
    video_path: str = ""
    trace_path: str = ""
    html_fragment_path: str = ""


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


@dataclass(slots=True)
class BrowserArtifacts:
    """File paths captured during or after a case run."""

    fullpage_screenshot: Path | None = None
    chatbox_screenshot: Path | None = None
    video_path: Path | None = None
    trace_path: Path | None = None
    html_fragment_path: Path | None = None
