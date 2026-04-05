"""Tests for AppConfig and load_config."""

from __future__ import annotations

import os
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

from app.config import AppConfig, load_config


class TestAppConfigPaths:
    def test_artifacts_subdirectories(self, tmp_path: Path):
        config = AppConfig(
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
        assert config.artifacts_dir == tmp_path / "artifacts"
        assert config.fullpage_dir == tmp_path / "artifacts" / "fullpage"
        assert config.chatbox_dir == tmp_path / "artifacts" / "chatbox"
        assert config.video_dir == tmp_path / "artifacts" / "video"
        assert config.trace_dir == tmp_path / "artifacts" / "trace"
        assert config.reports_dir == tmp_path / "reports"
        assert config.secrets_dir == tmp_path / ".secrets"
        assert config.samsung_storage_state_path == tmp_path / ".secrets" / "samsung_storage_state.json"
        assert config.questions_csv_path == tmp_path / "testcases" / "questions.csv"
        assert config.runtime_log_path == tmp_path / "reports" / "runtime.log"

    def test_ensure_directories_creates_all(self, tmp_path: Path):
        config = AppConfig(
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
        config.ensure_directories()
        assert config.fullpage_dir.is_dir()
        assert config.chatbox_dir.is_dir()
        assert config.video_dir.is_dir()
        assert config.trace_dir.is_dir()
        assert config.reports_dir.is_dir()
        assert config.secrets_dir.is_dir()


class TestLoadConfig:
    def test_defaults(self, tmp_path: Path):
        env = {
            "OPENAI_API_KEY": "sk-abc",
        }
        with patch.dict(os.environ, env, clear=True):
            config = load_config(tmp_path)
        assert config.openai_api_key == "sk-abc"
        assert config.samsung_base_url == "https://www.samsung.com/sec/"
        assert config.headless is False
        assert config.max_questions == 5
        assert config.enable_video is False
        assert config.enable_trace is False
        assert config.enable_ocr_fallback is False
        assert config.rubicon_force_activation is True
        assert config.rubicon_disable_sdk is False
        assert config.rubicon_max_input_candidates == 5
        assert config.rubicon_frame_rescan_rounds == 3

    def test_env_overrides(self, tmp_path: Path):
        env = {
            "OPENAI_API_KEY": "sk-xyz",
            "HEADLESS": "false",
            "MAX_QUESTIONS": "10",
            "OPENAI_MODEL": "gpt-4o",
            "ENABLE_VIDEO": "false",
            "ENABLE_TRACE": "false",
            "ENABLE_OCR_FALLBACK": "true",
            "RUBICON_CHAT_DEBUG": "true",
            "RUBICON_FORCE_ACTIVATION": "false",
            "RUBICON_DISABLE_SDK": "true",
            "RUBICON_MAX_INPUT_CANDIDATES": "4",
            "RUBICON_FRAME_RESCAN_ROUNDS": "2",
        }
        with patch.dict(os.environ, env, clear=True):
            config = load_config(tmp_path)
        assert config.headless is False
        assert config.max_questions == 10
        assert config.openai_model == "gpt-4o"
        assert config.enable_video is False
        assert config.enable_trace is False
        assert config.enable_ocr_fallback is True
        assert config.rubicon_chat_debug is True
        assert config.rubicon_force_activation is False
        assert config.rubicon_disable_sdk is True
        assert config.rubicon_max_input_candidates == 4
        assert config.rubicon_frame_rescan_rounds == 2

    def test_project_root_defaults_to_package_parent(self):
        config = load_config()
        assert config.project_root.is_dir()
