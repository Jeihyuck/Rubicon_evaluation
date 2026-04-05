"""Regression tests for Samsung answer cleaning and history dedupe."""

from __future__ import annotations

from app.samsung_rubicon import (
    _clean_bot_answer_candidate,
    _dedupe_preserve_order,
    _is_noise_line,
    _looks_like_main_answer,
)


def test_clean_bot_answer_candidate_removes_followup_suggestions():
    raw = """갤럭시 S24 배터리 교체는 삼성전자서비스 센터에서 진행할 수 있어요.
가까운 센터에 방문 접수로 점검 후 교체가 가능합니다.
🔍 이어서 물어보세요
가까운 서비스센터에서 바로 가능한가요?
배터리 교체 비용은 얼마나 나와요?
삼성케어플러스 가입이면 혜택이 있나요?"""

    cleaned = _clean_bot_answer_candidate(raw)

    assert "이어서 물어보세요" not in cleaned
    assert "가까운 서비스센터에서 바로 가능한가요?" not in cleaned
    assert cleaned.startswith("갤럭시 S24 배터리 교체는 삼성전자서비스 센터에서 진행할 수 있어요.")


def test_looks_like_main_answer_rejects_followup_question_chip():
    assert _looks_like_main_answer("가까운 서비스센터에서 바로 가능한가요?") is False


def test_is_noise_line_rejects_date_delivery_and_accessibility_meta():
    assert _is_noise_line("2026년 4월 5일 수신됨") is True
    assert _is_noise_line("전송됨") is True
    assert _is_noise_line("첨부") is True
    assert _is_noise_line("자세한 내용을 보려면 Enter를 누르세요") is True


def test_dedupe_preserve_order_keeps_first_unique_message_only():
    items = [
        "질문입니다.",
        "답변입니다.",
        "질문입니다.",
        "  답변입니다.  ",
        "추가 답변입니다.",
    ]

    assert _dedupe_preserve_order(items) == [
        "질문입니다.",
        "답변입니다.",
        "추가 답변입니다.",
    ]