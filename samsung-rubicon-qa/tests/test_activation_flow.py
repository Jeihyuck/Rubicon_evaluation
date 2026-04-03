"""Tests for the activation state machine."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from app.config import AppConfig
from app.logger import create_logger
from app.samsung_rubicon import configure_runtime, ensure_composer_ready


class _DummyPage:
    def wait_for_timeout(self, _: int) -> None:
        return None


class _DummyLocator:
    def click(self, timeout: int = 0) -> None:
        return None


def _make_config() -> AppConfig:
    return AppConfig(
        project_root=Path("/tmp/rubicon-activation-tests"),
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
        rubicon_chat_debug=False,
        rubicon_force_activation=True,
        rubicon_disable_sdk=False,
        rubicon_max_input_candidates=5,
        rubicon_frame_rescan_rounds=3,
        rubicon_before_send_screenshot=True,
        rubicon_opened_footer_screenshot=True,
        rubicon_after_answer_screenshot=True,
    )


def test_activation_sequence_succeeds_when_editable_candidate_appears(tmp_path):
    configure_runtime(_make_config(), create_logger(tmp_path / "runtime.log"))
    context = SimpleNamespace(container_locator=None, input_locator=None, scope=SimpleNamespace())
    rounds = [
        [{"grade": "C", "selector": "textarea", "disabled": True}],
        [{"grade": "A", "selector": ".ql-editor", "disabled": False}],
    ]
    with (
        patch("app.samsung_rubicon.collect_ranked_input_candidates", side_effect=rounds),
        patch("app.samsung_rubicon._activation_targets", return_value=[("chat_container", _DummyLocator())]),
    ):
        result = ensure_composer_ready(_DummyPage(), context)
    assert result["activation_success"] is True
    assert result["editable_candidates_after_activation"] == 1


def test_activation_rescan_moves_past_disabled_only_state(tmp_path):
    configure_runtime(_make_config(), create_logger(tmp_path / "runtime-2.log"))
    context = SimpleNamespace(container_locator=None, input_locator=None, scope=SimpleNamespace())
    rounds = [
        [{"grade": "C", "selector": "textarea", "disabled": True}],
        [{"grade": "B", "selector": "[role='textbox']", "disabled": False}],
    ]
    with (
        patch("app.samsung_rubicon.collect_ranked_input_candidates", side_effect=rounds),
        patch("app.samsung_rubicon._activation_targets", return_value=[("placeholder_area", _DummyLocator())]),
    ):
        result = ensure_composer_ready(_DummyPage(), context)
    assert result["activation_attempted"] is True
    assert result["activation_success"] is True
    assert any(step.endswith("placeholder_area") for step in result["activation_steps"])


def test_activation_uses_rescan_rounds_before_exhausting(tmp_path):
    configure_runtime(_make_config(), create_logger(tmp_path / "runtime-3.log"))
    context = SimpleNamespace(container_locator=None, input_locator=None, scope=SimpleNamespace())
    rounds = [
        [{"grade": "C", "selector": "textarea", "disabled": True}],
        [{"grade": "C", "selector": "textarea", "disabled": True}],
        [{"grade": "C", "selector": "textarea", "disabled": True}],
        [{"grade": "B", "selector": "[role='textbox']", "disabled": False}],
    ]
    with (
        patch("app.samsung_rubicon.collect_ranked_input_candidates", side_effect=rounds),
        patch("app.samsung_rubicon._activation_targets", return_value=[("footer", _DummyLocator())]),
    ):
        result = ensure_composer_ready(_DummyPage(), context)
    assert result["activation_success"] is True
    assert result["editable_candidates_after_activation"] == 1
    assert any(step.startswith("round2:") for step in result["activation_steps"])
