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
    status: Literal["success", "failed", "invalid_capture"]
    answer_raw: str = ""
    answer_normalized: str = ""
    actual_answer: str = ""
    actual_answer_clean: str = ""
    extraction_source_detail: str = ""
    message_history_clean: str = ""
    removed_followups: bool = False
    noise_lines_removed: int = 0
    reason: str = ""
    error_message: str = ""
    run_mode: str = "speed"
    fast_path_used: bool = False
    full_screenshot_path: str = ""
    chat_screenshot_path: str = ""
    submitted_chat_screenshot_path: str = ""
    answered_chat_screenshot_path: str = ""
    video_path: str = ""
    trace_path: str = ""
    html_fragment_path: str = ""
    evidence_markdown_path: str = ""
    evidence_json_path: str = ""
    fix_suggestion: str = ""
    input_dom_verified: bool = False
    submit_effect_verified: bool = False
    input_verified: bool = False
    input_method_used: str = ""
    submit_method_used: str = "unknown"
    opened_chat_screenshot_path: str = ""
    opened_full_screenshot_path: str = ""
    opened_footer_screenshot_path: str = ""
    open_method_used: str = ""
    sdk_status: str = ""
    availability_status: str = ""
    input_scope: str = ""
    input_scope_name: str = ""
    input_selector: str = ""
    input_failure_category: str = ""
    input_failure_reason: str = ""
    input_candidate_score: float = 0.0
    top_candidate_disabled: bool = False
    top_candidate_placeholder: str = ""
    top_candidate_aria: str = ""
    input_ready_wait_result: str = ""
    transition_wait_attempted: bool = False
    transition_ready: bool = False
    transition_timeout: bool = False
    transition_reason: str = ""
    transition_history: str = ""
    activation_attempted: bool = False
    activation_steps_tried: str = ""
    editable_candidates_count: int = 0
    failover_attempts: int = 0
    final_input_target_frame: str = ""
    input_candidates_debug: str = ""
    input_candidate_logs: list[str] = field(default_factory=list)
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
    answer_screenshot_paths: list[str] = field(default_factory=list)
    after_answer_multi_page: bool = False
    ocr_text: str = ""
    ocr_confidence: float = 0.0
    structured_message_history_count: int = 0
    fallback_diff_used: bool = False
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
        record = self.to_result_record()
        data.update({key: value for key, value in record.items() if key != "evaluation"})
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
            "answer_raw": self.pair.answer_raw,
            "answer_normalized": self.pair.answer_normalized,
            "actual_answer": self.pair.actual_answer or self.pair.answer,
            "actual_answer_clean": self.pair.actual_answer_clean or self.pair.actual_answer or self.pair.answer,
            "input_dom_verified": self.pair.input_dom_verified,
            "submit_effect_verified": self.pair.submit_effect_verified,
            "input_verified": self.pair.input_verified,
            "input_method_used": self.pair.input_method_used,
            "submit_method_used": self.pair.submit_method_used,
            "user_message_echo_verified": self.pair.user_message_echo_verified,
            "new_bot_response_detected": self.pair.new_bot_response_detected,
            "baseline_menu_detected": self.pair.baseline_menu_detected,
            "status": self.pair.status,
            "error_message": self.pair.error_message,
            "reason": self.pair.reason,
            "run_mode": self.pair.run_mode,
            "fast_path_used": self.pair.fast_path_used,
            "fix_suggestion": self.pair.fix_suggestion or self.evaluation.fix_suggestion,
            "message_history": self.pair.message_history,
            "message_history_clean": self.pair.message_history_clean,
            "html_fragment_path": self.pair.html_fragment_path,
            "evidence_markdown_path": self.pair.evidence_markdown_path,
            "evidence_json_path": self.pair.evidence_json_path,
            "extraction_source": self.pair.extraction_source,
            "extraction_source_detail": self.pair.extraction_source_detail,
            "removed_followups": self.pair.removed_followups,
            "noise_lines_removed": self.pair.noise_lines_removed,
            "ocr_text": self.pair.ocr_text,
            "ocr_confidence": self.pair.ocr_confidence,
            "structured_message_history_count": self.pair.structured_message_history_count,
            "fallback_diff_used": self.pair.fallback_diff_used,
            "input_scope": self.pair.input_scope or self.pair.input_scope_name,
            "input_selector": self.pair.input_selector,
            "input_candidate_score": self.pair.input_candidate_score,
            "input_failure_category": self.pair.input_failure_category,
            "input_failure_reason": self.pair.input_failure_reason,
            "top_candidate_disabled": self.pair.top_candidate_disabled,
            "top_candidate_placeholder": self.pair.top_candidate_placeholder,
            "top_candidate_aria": self.pair.top_candidate_aria,
            "input_ready_wait_result": self.pair.input_ready_wait_result,
            "transition_wait_attempted": self.pair.transition_wait_attempted,
            "transition_ready": self.pair.transition_ready,
            "transition_timeout": self.pair.transition_timeout,
            "transition_reason": self.pair.transition_reason,
            "transition_history": self.pair.transition_history,
            "activation_attempted": self.pair.activation_attempted,
            "activation_steps_tried": self.pair.activation_steps_tried,
            "editable_candidates_count": self.pair.editable_candidates_count,
            "failover_attempts": self.pair.failover_attempts,
            "final_input_target_frame": self.pair.final_input_target_frame,
            "open_method_used": self.pair.open_method_used,
            "sdk_status": self.pair.sdk_status,
            "availability_status": self.pair.availability_status,
            "input_candidates_debug": self.pair.input_candidates_debug,
            "before_send_screenshot_path": self.pair.before_send_screenshot_path,
            "submitted_chat_screenshot_path": self.pair.submitted_chat_screenshot_path,
            "after_send_screenshot_path": self.pair.after_send_screenshot_path,
            "answered_chat_screenshot_path": self.pair.answered_chat_screenshot_path,
            "after_answer_screenshot_path": self.pair.after_answer_screenshot_path,
            "answer_screenshot_paths": self.pair.answer_screenshot_paths,
            "after_answer_multi_page": self.pair.after_answer_multi_page,
            "full_screenshot_path": self.pair.full_screenshot_path,
            "overall_score": self.evaluation.overall_score,
            "needs_human_review": self.evaluation.needs_human_review,
            "response_ms": self.pair.response_ms,
            "extraction_confidence": self.pair.extraction_confidence,
            "opened_chat_screenshot_path": self.pair.opened_chat_screenshot_path,
            "opened_full_screenshot_path": self.pair.opened_full_screenshot_path,
            "opened_footer_screenshot_path": self.pair.opened_footer_screenshot_path,
            "input_scope_name": self.pair.input_scope_name,
            "input_candidate_logs": self.pair.input_candidate_logs,
            "before_send_full_screenshot_path": self.pair.before_send_full_screenshot_path,
            "after_send_full_screenshot_path": self.pair.after_send_full_screenshot_path,
            "after_answer_full_screenshot_path": self.pair.after_answer_full_screenshot_path,
            "chat_screenshot_path": self.pair.chat_screenshot_path,
            "video_path": self.pair.video_path,
            "trace_path": self.pair.trace_path,
            "evaluation": asdict(self.evaluation),
        }


@dataclass(slots=True)
class ResolvedChatContext:
    """Resolved chat widget references for the current case."""

    scope: Any
    scope_name: str
    input_locator: Any | None
    send_locator: Any | None
    container_locator: Any | None
    bot_message_candidates: list[dict[str, Any]]
    history_candidates: list[dict[str, Any]]
    loading_candidates: list[dict[str, Any]]
    page: Any | None = None
    input_scope: Any | None = None
    input_scope_name: str = ""
    input_selector: str = ""
    input_failure_category: str = ""
    input_failure_reason: str = ""
    frame_inventory: list[dict[str, Any]] = field(default_factory=list)
    ranked_input_candidates: list[dict[str, Any]] = field(default_factory=list)
    input_candidates_debug: str = ""
    baseline_bot_count: int = 0
    baseline_bot_messages: list[str] = field(default_factory=list)
    baseline_history: list[str] = field(default_factory=list)
    baseline_visible_text: str = ""
    baseline_message_nodes_snapshot: list[str] = field(default_factory=list)
    baseline_visible_blocks: list[str] = field(default_factory=list)
    baseline_send_button_enabled: bool | None = None
    chat_frame_score: int = 0
    input_candidate_score: float = 0.0
    input_candidate_logs: list[str] = field(default_factory=list)


@dataclass(slots=True)
class BrowserArtifacts:
    """File paths captured during or after a case run."""

    fullpage_screenshot: Path | None = None
    chatbox_screenshot: Path | None = None
    video_path: Path | None = None
    trace_path: Path | None = None
    html_fragment_path: Path | None = None
    before_send_screenshot_path: Path | None = None
