"""Runtime configuration for the Samsung Rubicon QA automation."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv


def _to_bool(value: str | None, default: bool) -> bool:
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "y", "on"}


@dataclass(slots=True)
class AppConfig:
    """All environment-driven configuration used by the application."""

    project_root: Path
    openai_api_key: str
    samsung_base_url: str
    headless: bool
    default_locale: str
    max_questions: int
    openai_model: str
    playwright_timeout_ms: int
    answer_stable_checks: int
    answer_stable_interval_sec: float
    enable_video: bool
    enable_trace: bool
    enable_ocr_fallback: bool
    rubicon_chat_debug: bool
    rubicon_force_activation: bool
    rubicon_disable_sdk: bool
    rubicon_max_input_candidates: int
    rubicon_frame_rescan_rounds: int
    rubicon_before_send_screenshot: bool
    rubicon_opened_footer_screenshot: bool
    rubicon_after_answer_screenshot: bool

    @property
    def artifacts_dir(self) -> Path:
        return self.project_root / "artifacts"

    @property
    def fullpage_dir(self) -> Path:
        return self.artifacts_dir / "fullpage"

    @property
    def chatbox_dir(self) -> Path:
        return self.artifacts_dir / "chatbox"

    @property
    def video_dir(self) -> Path:
        return self.artifacts_dir / "video"

    @property
    def trace_dir(self) -> Path:
        return self.artifacts_dir / "trace"

    @property
    def reports_dir(self) -> Path:
        return self.project_root / "reports"

    @property
    def secrets_dir(self) -> Path:
        return self.project_root / ".secrets"

    @property
    def samsung_storage_state_path(self) -> Path:
        return self.secrets_dir / "samsung_storage_state.json"

    @property
    def questions_csv_path(self) -> Path:
        return self.project_root / "testcases" / "questions.csv"

    @property
    def runtime_log_path(self) -> Path:
        return self.reports_dir / "runtime.log"

    def ensure_directories(self) -> None:
        """Create output directories required by the workflow."""

        for path in [
            self.artifacts_dir,
            self.fullpage_dir,
            self.chatbox_dir,
            self.video_dir,
            self.trace_dir,
            self.reports_dir,
            self.secrets_dir,
        ]:
            path.mkdir(parents=True, exist_ok=True)


def load_config(project_root: Path | None = None) -> AppConfig:
    """Load environment variables and create a normalized config object."""

    resolved_root = project_root or Path(__file__).resolve().parent.parent
    env_path = resolved_root / ".env"
    if env_path.exists():
        load_dotenv(env_path)

    return AppConfig(
        project_root=resolved_root,
        openai_api_key=os.getenv("OPENAI_API_KEY", "").strip(),
        samsung_base_url=os.getenv("SAMSUNG_BASE_URL", "https://www.samsung.com/sec/").strip(),
        headless=_to_bool(os.getenv("HEADLESS"), False),
        default_locale=os.getenv("DEFAULT_LOCALE", "ko-KR").strip(),
        max_questions=int(os.getenv("MAX_QUESTIONS", "5")),
        openai_model=os.getenv("OPENAI_MODEL", "gpt-4o").strip(),
        playwright_timeout_ms=int(os.getenv("PLAYWRIGHT_TIMEOUT_MS", "30000")),
        answer_stable_checks=int(os.getenv("ANSWER_STABLE_CHECKS", "3")),
        answer_stable_interval_sec=float(os.getenv("ANSWER_STABLE_INTERVAL_SEC", "1.0")),
        enable_video=_to_bool(os.getenv("ENABLE_VIDEO"), False),
        enable_trace=_to_bool(os.getenv("ENABLE_TRACE"), False),
        enable_ocr_fallback=_to_bool(os.getenv("ENABLE_OCR_FALLBACK"), False),
        rubicon_chat_debug=_to_bool(os.getenv("RUBICON_CHAT_DEBUG"), False),
        rubicon_force_activation=_to_bool(os.getenv("RUBICON_FORCE_ACTIVATION"), True),
        rubicon_disable_sdk=_to_bool(os.getenv("RUBICON_DISABLE_SDK"), False),
        rubicon_max_input_candidates=int(os.getenv("RUBICON_MAX_INPUT_CANDIDATES", "5")),
        rubicon_frame_rescan_rounds=int(os.getenv("RUBICON_FRAME_RESCAN_ROUNDS", "3")),
        rubicon_before_send_screenshot=_to_bool(os.getenv("RUBICON_BEFORE_SEND_SCREENSHOT"), True),
        rubicon_opened_footer_screenshot=_to_bool(os.getenv("RUBICON_OPENED_FOOTER_SCREENSHOT"), True),
        rubicon_after_answer_screenshot=_to_bool(os.getenv("RUBICON_AFTER_ANSWER_SCREENSHOT"), True),
    )
