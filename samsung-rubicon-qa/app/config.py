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
        ]:
            path.mkdir(parents=True, exist_ok=True)


def load_config(project_root: Path | None = None) -> AppConfig:
    """Load environment variables and create a normalized config object."""

    resolved_root = project_root or Path(__file__).resolve().parent.parent
    env_path = resolved_root / ".env"
    load_dotenv(env_path if env_path.exists() else None)

    return AppConfig(
        project_root=resolved_root,
        openai_api_key=os.getenv("OPENAI_API_KEY", "").strip(),
        samsung_base_url=os.getenv("SAMSUNG_BASE_URL", "https://www.samsung.com/sec/").strip(),
        headless=_to_bool(os.getenv("HEADLESS"), True),
        default_locale=os.getenv("DEFAULT_LOCALE", "ko-KR").strip(),
        max_questions=int(os.getenv("MAX_QUESTIONS", "5")),
        openai_model=os.getenv("OPENAI_MODEL", "gpt-4o").strip(),
        playwright_timeout_ms=int(os.getenv("PLAYWRIGHT_TIMEOUT_MS", "30000")),
        answer_stable_checks=int(os.getenv("ANSWER_STABLE_CHECKS", "3")),
        answer_stable_interval_sec=float(os.getenv("ANSWER_STABLE_INTERVAL_SEC", "1.0")),
        enable_video=_to_bool(os.getenv("ENABLE_VIDEO"), True),
        enable_trace=_to_bool(os.getenv("ENABLE_TRACE"), True),
        enable_ocr_fallback=_to_bool(os.getenv("ENABLE_OCR_FALLBACK"), False),
    )
