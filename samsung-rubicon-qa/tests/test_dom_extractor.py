"""Tests for Sprinklr-specific DOM extraction helpers."""

from __future__ import annotations

from app.dom_extractor import (
    build_post_baseline_answer_candidates,
    choose_best_answer_segment,
    compute_new_text_segments,
    extract_clean_text_from_message_node,
    filter_out_static_ui_text,
    is_static_ui_text,
    normalize_text_for_diff,
)


class TestStaticUiFiltering:
    def test_static_header_is_rejected(self):
        assert is_static_ui_text("삼성닷컴 구매 상담사와 채팅하세요") is True
        assert is_static_ui_text("Samsung AI Assistant") is True

    def test_real_answer_is_not_rejected(self):
        assert is_static_ui_text("갤럭시 S24 배터리 교체는 가까운 삼성 서비스센터에서 가능합니다.") is False

    def test_filter_out_static_ui_segments(self):
        segments = [
            "Samsung AI Assistant",
            "아래에서 원하는 항목을 선택해 주세요",
            "갤럭시 S24 배터리 교체는 가까운 삼성 서비스센터에서 가능합니다.",
        ]
        filtered = filter_out_static_ui_text(segments)
        assert filtered == ["갤럭시 S24 배터리 교체는 가까운 삼성 서비스센터에서 가능합니다."]

    def test_close_button_text_is_rejected(self):
        assert is_static_ui_text("닫기") is True


class TestDiffHelpers:
    def test_compute_new_text_segments(self):
        before = ["Samsung AI Assistant", "구매 상담사 연결"]
        after = before + ["갤럭시 S24 배터리 교체는 가까운 삼성 서비스센터에서 가능합니다."]
        segments = compute_new_text_segments(before, after)
        assert segments == ["갤럭시 S24 배터리 교체는 가까운 삼성 서비스센터에서 가능합니다."]

    def test_choose_best_answer_segment_prefers_real_answer(self):
        segments = [
            "서비스 센터",
            "갤럭시 S24 배터리 교체는 가까운 삼성 서비스센터에서 가능합니다.",
            "FAQ",
        ]
        best = choose_best_answer_segment(segments)
        assert best == "갤럭시 S24 배터리 교체는 가까운 삼성 서비스센터에서 가능합니다."


class TestMessageNodeExtraction:
    def test_extract_clean_text_from_wrapper_prefers_text_child(self):
        node = {
            "wrapperText": "삼성닷컴 구매 상담사와 채팅하세요 갤럭시 S24 배터리 교체는 가까운 삼성 서비스센터에서 가능합니다.",
            "descendants": [
                {"text": "삼성닷컴 구매 상담사와 채팅하세요"},
                {"text": "갤럭시 S24 배터리 교체는 가까운 삼성 서비스센터에서 가능합니다."},
            ],
        }
        assert extract_clean_text_from_message_node(node) == "갤럭시 S24 배터리 교체는 가까운 삼성 서비스센터에서 가능합니다."

    def test_normalize_text_for_diff(self):
        assert normalize_text_for_diff("  안녕\n하세요  ") == "안녕 하세요"


class TestPostBaselineCandidates:
    def test_answer_prefers_last_new_bot_candidate(self):
        class DummyContext:
            baseline_bot_count = 1
            baseline_bot_messages = ["구매 상담사와 채팅 하세요"]
            baseline_message_nodes_snapshot = ["구매 상담사와 채팅 하세요"]

        from unittest.mock import patch

        with (
            patch("app.dom_extractor.extract_structured_message_history", return_value={"history": ["구매 상담사와 채팅 하세요", "첫 답변", "최종 답변입니다."], "count": 3, "fallback_diff_used": False}),
            patch("app.dom_extractor.extract_bot_message_texts", return_value=["구매 상담사와 채팅 하세요", "첫 답변", "최종 답변입니다."]),
            patch("app.dom_extractor.diff_visible_text_against_baseline", return_value=["최종 답변입니다."]),
            patch("app.dom_extractor.extract_visible_chat_text", return_value="구매 상담사와 채팅 하세요\n첫 답변\n최종 답변입니다."),
            patch("app.dom_extractor.extract_visible_text_blocks", return_value=["첫 답변", "최종 답변입니다."]),
        ):
            payload = build_post_baseline_answer_candidates(DummyContext())

        assert payload["answer"] == "최종 답변입니다."
        assert payload["strict_candidates"][-1] == "최종 답변입니다."
