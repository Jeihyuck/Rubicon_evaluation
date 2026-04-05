"""Tests for Sprinklr-specific DOM extraction helpers."""

from __future__ import annotations

from app.dom_extractor import (
    _strip_meta_text,
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

    def test_korean_timestamp_is_rejected(self):
        assert is_static_ui_text("\u200e오전 12:30") is True

    def test_feedback_and_timestamp_meta_is_stripped(self):
        assert _strip_meta_text("좋아요 싫어함 오전 1:43") == ""

    def test_followup_prompt_is_stripped_from_answer(self):
        text = (
            "갤럭시 S24 배터리 교체는 삼성전자서비스 센터에서 진행할 수 있어요. "
            "가까운 센터에 방문 접수로 배터리 점검 후 교체가 가능합니다. "
            "🔍 이어서 물어보세요 가까운 서비스센터에서 바로 가능한가요? "
            "배터리 교체 비용은 얼마나 나와요?"
        )
        assert _strip_meta_text(text) == (
            "갤럭시 S24 배터리 교체는 삼성전자서비스 센터에서 진행할 수 있어요. "
            "가까운 센터에 방문 접수로 배터리 점검 후 교체가 가능합니다."
        )

    def test_accessibility_prefix_is_stripped_from_answer(self):
        text = (
            "자세한 내용을 보려면 Enter를 누르세요. 리치 텍스트 메시지 "
            "갤럭시 S24 배터리 교체는 삼성전자서비스 센터에서 진행할 수 있어요."
        )
        assert _strip_meta_text(text) == "갤럭시 S24 배터리 교체는 삼성전자서비스 센터에서 진행할 수 있어요."


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

    def test_choose_best_answer_segment_ignores_timestamp(self):
        segments = [
            "\u200e오전 12:30",
            "주문 배송 조회는 삼성닷컴 마이페이지의 주문/배송 조회 메뉴에서 확인할 수 있습니다.",
        ]
        best = choose_best_answer_segment(segments)
        assert best == "주문 배송 조회는 삼성닷컴 마이페이지의 주문/배송 조회 메뉴에서 확인할 수 있습니다."

    def test_choose_best_answer_segment_ignores_feedback_meta(self):
        segments = [
            "좋아요 싫어함 오전 1:43",
            "갤럭시 S24 배터리 교체는 가까운 삼성 서비스센터에서 가능합니다.",
        ]
        best = choose_best_answer_segment(segments)
        assert best == "갤럭시 S24 배터리 교체는 가까운 삼성 서비스센터에서 가능합니다."

    def test_choose_best_answer_segment_prefers_body_over_followup_question(self):
        segments = [
            "가까운 서비스센터에서 바로 가능한가요?",
            (
                "갤럭시 S24 배터리 교체는 삼성전자서비스 센터에서 진행할 수 있어요. "
                "가까운 센터에 방문 접수로 배터리 점검 후 교체가 가능합니다."
            ),
        ]
        best = choose_best_answer_segment(segments)
        assert best == (
            "갤럭시 S24 배터리 교체는 삼성전자서비스 센터에서 진행할 수 있어요. "
            "가까운 센터에 방문 접수로 배터리 점검 후 교체가 가능합니다."
        )


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

    def test_extract_clean_text_from_message_node_strips_followup_prompt(self):
        node = {
            "wrapperText": (
                "리치 텍스트 메시지 갤럭시 S24 배터리 교체는 삼성전자서비스 센터에서 진행할 수 있어요. "
                "가까운 센터에 방문 접수로 배터리 점검 후 교체가 가능합니다. "
                "🔍 이어서 물어보세요 가까운 서비스센터에서 바로 가능한가요?"
            ),
            "descendants": [
                {
                    "text": (
                        "갤럭시 S24 배터리 교체는 삼성전자서비스 센터에서 진행할 수 있어요. "
                        "가까운 센터에 방문 접수로 배터리 점검 후 교체가 가능합니다."
                    )
                },
                {"text": "가까운 서비스센터에서 바로 가능한가요?"},
            ],
        }
        assert extract_clean_text_from_message_node(node) == (
            "갤럭시 S24 배터리 교체는 삼성전자서비스 센터에서 진행할 수 있어요. "
            "가까운 센터에 방문 접수로 배터리 점검 후 교체가 가능합니다."
        )

    def test_normalize_text_for_diff(self):
        assert normalize_text_for_diff("  안녕\n하세요  ") == "안녕 하세요"


class TestPostBaselineCandidates:
    def test_answer_prefers_best_new_bot_candidate(self):
        class DummyContext:
            baseline_bot_count = 1
            baseline_bot_messages = ["구매 상담사와 채팅 하세요"]
            baseline_message_nodes_snapshot = ["구매 상담사와 채팅 하세요"]

        from unittest.mock import patch

        with (
            patch(
                "app.dom_extractor.extract_structured_message_history",
                return_value={
                    "history": ["구매 상담사와 채팅 하세요", "최종 답변입니다.", "가까운 서비스센터에서 바로 가능한가요?"],
                    "count": 3,
                    "fallback_diff_used": False,
                },
            ),
            patch(
                "app.dom_extractor.extract_bot_message_texts",
                return_value=["구매 상담사와 채팅 하세요", "최종 답변입니다.", "가까운 서비스센터에서 바로 가능한가요?"],
            ),
            patch("app.dom_extractor.diff_visible_text_against_baseline", return_value=["최종 답변입니다."]),
            patch(
                "app.dom_extractor.extract_visible_chat_text",
                return_value="구매 상담사와 채팅 하세요\n최종 답변입니다.\n가까운 서비스센터에서 바로 가능한가요?",
            ),
            patch(
                "app.dom_extractor.extract_visible_text_blocks",
                return_value=["최종 답변입니다.", "가까운 서비스센터에서 바로 가능한가요?"],
            ),
        ):
            payload = build_post_baseline_answer_candidates(DummyContext())

        assert payload["answer"] == "최종 답변입니다."
        assert payload["strict_candidates"] == ["최종 답변입니다.", "가까운 서비스센터에서 바로 가능한가요?"]

    def test_answer_ignores_korean_timestamp_meta(self):
        class DummyContext:
            baseline_bot_count = 1
            baseline_bot_messages = ["구매 상담사와 채팅 하세요"]
            baseline_message_nodes_snapshot = ["구매 상담사와 채팅 하세요"]
            baseline_visible_blocks = ["구매 상담사와 채팅 하세요"]

        from unittest.mock import patch

        with (
            patch(
                "app.dom_extractor.extract_structured_message_history",
                return_value={
                    "history": [
                        "구매 상담사와 채팅 하세요",
                        "\u200e오전 12:30",
                        "주문 배송 조회는 삼성닷컴 마이페이지에서 확인할 수 있습니다.",
                    ],
                    "count": 3,
                    "fallback_diff_used": False,
                },
            ),
            patch(
                "app.dom_extractor.extract_bot_message_texts",
                return_value=[
                    "구매 상담사와 채팅 하세요",
                    "\u200e오전 12:30",
                    "주문 배송 조회는 삼성닷컴 마이페이지에서 확인할 수 있습니다.",
                ],
            ),
            patch(
                "app.dom_extractor.diff_visible_text_against_baseline",
                return_value=["\u200e오전 12:30", "주문 배송 조회는 삼성닷컴 마이페이지에서 확인할 수 있습니다."],
            ),
            patch(
                "app.dom_extractor.extract_visible_chat_text",
                return_value="구매 상담사와 채팅 하세요\n\u200e오전 12:30\n주문 배송 조회는 삼성닷컴 마이페이지에서 확인할 수 있습니다.",
            ),
            patch(
                "app.dom_extractor.extract_visible_text_blocks",
                return_value=["\u200e오전 12:30", "주문 배송 조회는 삼성닷컴 마이페이지에서 확인할 수 있습니다."],
            ),
        ):
            payload = build_post_baseline_answer_candidates(DummyContext())

        assert payload["answer"] == "주문 배송 조회는 삼성닷컴 마이페이지에서 확인할 수 있습니다."
        assert payload["strict_candidates"] == ["주문 배송 조회는 삼성닷컴 마이페이지에서 확인할 수 있습니다."]

    def test_answer_ignores_feedback_timestamp_meta(self):
        class DummyContext:
            baseline_bot_count = 1
            baseline_bot_messages = ["구매 상담사와 채팅 하세요"]
            baseline_message_nodes_snapshot = ["구매 상담사와 채팅 하세요"]
            baseline_visible_blocks = ["구매 상담사와 채팅 하세요"]

        from unittest.mock import patch

        with (
            patch(
                "app.dom_extractor.extract_structured_message_history",
                return_value={
                    "history": [
                        "구매 상담사와 채팅 하세요",
                        "좋아요 싫어함 오전 1:43",
                        "갤럭시 S24 배터리 교체는 가까운 삼성 서비스센터에서 가능합니다.",
                    ],
                    "count": 3,
                    "fallback_diff_used": False,
                },
            ),
            patch(
                "app.dom_extractor.extract_bot_message_texts",
                return_value=[
                    "구매 상담사와 채팅 하세요",
                    "좋아요 싫어함 오전 1:43",
                    "갤럭시 S24 배터리 교체는 가까운 삼성 서비스센터에서 가능합니다.",
                ],
            ),
            patch(
                "app.dom_extractor.diff_visible_text_against_baseline",
                return_value=["좋아요 싫어함 오전 1:43", "갤럭시 S24 배터리 교체는 가까운 삼성 서비스센터에서 가능합니다."],
            ),
            patch(
                "app.dom_extractor.extract_visible_chat_text",
                return_value="구매 상담사와 채팅 하세요\n좋아요 싫어함 오전 1:43\n갤럭시 S24 배터리 교체는 가까운 삼성 서비스센터에서 가능합니다.",
            ),
            patch(
                "app.dom_extractor.extract_visible_text_blocks",
                return_value=["좋아요 싫어함 오전 1:43", "갤럭시 S24 배터리 교체는 가까운 삼성 서비스센터에서 가능합니다."],
            ),
        ):
            payload = build_post_baseline_answer_candidates(DummyContext())

        assert payload["answer"] == "갤럭시 S24 배터리 교체는 가까운 삼성 서비스센터에서 가능합니다."
        assert payload["strict_candidates"] == ["갤럭시 S24 배터리 교체는 가까운 삼성 서비스센터에서 가능합니다."]

    def test_answer_uses_fallback_body_when_strict_has_only_followup_question(self):
        class DummyContext:
            baseline_bot_count = 1
            baseline_bot_messages = ["구매 상담사와 채팅 하세요"]
            baseline_message_nodes_snapshot = ["구매 상담사와 채팅 하세요"]
            baseline_visible_blocks = ["구매 상담사와 채팅 하세요"]

        from unittest.mock import patch

        answer_body = (
            "갤럭시 S24 배터리 교체는 삼성전자서비스 센터에서 진행할 수 있어요. "
            "가까운 센터에 방문 접수로 배터리 점검 후 교체가 가능합니다."
        )

        with (
            patch(
                "app.dom_extractor.extract_structured_message_history",
                return_value={
                    "history": [
                        "구매 상담사와 채팅 하세요",
                        answer_body,
                        "가까운 서비스센터에서 바로 가능한가요?",
                    ],
                    "count": 3,
                    "fallback_diff_used": False,
                },
            ),
            patch(
                "app.dom_extractor.extract_bot_message_texts",
                return_value=[
                    "구매 상담사와 채팅 하세요",
                    "가까운 서비스센터에서 바로 가능한가요?",
                ],
            ),
            patch("app.dom_extractor.diff_visible_text_against_baseline", return_value=[]),
            patch(
                "app.dom_extractor.extract_visible_chat_text",
                return_value=f"구매 상담사와 채팅 하세요\n{answer_body}\n가까운 서비스센터에서 바로 가능한가요?",
            ),
            patch(
                "app.dom_extractor.extract_visible_text_blocks",
                return_value=[answer_body, "가까운 서비스센터에서 바로 가능한가요?"],
            ),
        ):
            payload = build_post_baseline_answer_candidates(DummyContext())

        assert payload["strict_candidates"] == ["가까운 서비스센터에서 바로 가능한가요?"]
        assert payload["fallback_candidates"] == [answer_body, "가까운 서비스센터에서 바로 가능한가요?"]
        assert payload["all_candidates"] == ["가까운 서비스센터에서 바로 가능한가요?", answer_body]
        assert payload["answer"] == answer_body
