"""Tests for BrowserManager session context options."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path
from unittest.mock import Mock

from app.browser import BrowserManager
from app.config import AppConfig


def build_config(tmp_path: Path) -> AppConfig:
    return AppConfig(
        project_root=tmp_path,
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


def test_new_case_session_uses_storage_state_when_present(tmp_path: Path):
    config = build_config(tmp_path)
    config.ensure_directories()
    config.samsung_storage_state_path.write_text('{"cookies": [], "origins": []}', encoding="utf-8")

    logger = Mock()
    browser = Mock()
    context = Mock()
    page = Mock()
    browser.new_context.return_value = context
    context.new_page.return_value = page

    manager = BrowserManager(config=config, logger=logger)
    manager._browser = browser

    session = manager.new_case_session("case-1")

    assert session.page is page
    browser.new_context.assert_called_once_with(
        locale="ko-KR",
        viewport={"width": 1440, "height": 1200},
        storage_state=str(config.samsung_storage_state_path),
    )


def test_new_case_session_skips_storage_state_when_missing(tmp_path: Path):
    config = build_config(tmp_path)
    logger = Mock()
    browser = Mock()
    context = Mock()
    page = Mock()
    browser.new_context.return_value = context
    context.new_page.return_value = page

    manager = BrowserManager(config=config, logger=logger)
    manager._browser = browser

    manager.new_case_session("case-2")

    browser.new_context.assert_called_once_with(
        locale="ko-KR",
        viewport={"width": 1440, "height": 1200},
    )


def test_new_case_session_enables_video_only_in_debug_mode(tmp_path: Path):
    config = build_config(tmp_path)
    config = replace(config, capture_mode="debug", enable_video=True)
    logger = Mock()
    browser = Mock()
    context = Mock()
    page = Mock()
    browser.new_context.return_value = context
    context.new_page.return_value = page

    manager = BrowserManager(config=config, logger=logger)
    manager._browser = browser

    manager.new_case_session("case-video")

    browser.new_context.assert_called_once_with(
        locale="ko-KR",
        viewport={"width": 1440, "height": 1200},
        record_video_dir=str(config.video_dir),
        record_video_size={"width": 1440, "height": 1200},
    )