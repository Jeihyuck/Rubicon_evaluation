"""Configuration loader for Samsung Chat QA.

Reads settings from environment variables (or a .env file loaded by the
caller) and exposes them through the :class:`Config` dataclass.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv

# Load .env if it exists (no-op when variables are already set by CI)
_env_path = Path(__file__).resolve().parent.parent / ".env"
if _env_path.exists():
    load_dotenv(_env_path, override=False)


@dataclass
class Config:
    """Application-wide configuration values."""

    # Samsung website
    base_url: str = field(
        default_factory=lambda: os.getenv("SAMSUNG_BASE_URL", "https://www.samsung.com/")
    )

    # Playwright
    headless: bool = field(
        default_factory=lambda: os.getenv("HEADLESS", "true").lower() in ("1", "true", "yes")
    )
    playwright_timeout_ms: int = field(
        default_factory=lambda: int(os.getenv("PLAYWRIGHT_TIMEOUT_MS", "30000"))
    )
    viewport_width: int = 1280
    viewport_height: int = 900

    # Locale / language
    default_locale: str = field(
        default_factory=lambda: os.getenv("DEFAULT_LOCALE", "en-US")
    )

    # Test run limits
    max_questions: int = field(
        default_factory=lambda: int(os.getenv("MAX_QUESTIONS", "3"))
    )

    # Answer stability detection
    answer_stable_checks: int = field(
        default_factory=lambda: int(os.getenv("ANSWER_STABLE_CHECKS", "3"))
    )
    answer_stable_interval_sec: float = field(
        default_factory=lambda: float(os.getenv("ANSWER_STABLE_INTERVAL_SEC", "1.0"))
    )

    # OpenAI
    openai_api_key: str = field(
        default_factory=lambda: os.getenv("OPENAI_API_KEY", "")
    )
    openai_model: str = field(
        default_factory=lambda: os.getenv("OPENAI_MODEL", "gpt-4o")
    )

    # Paths (relative to project root)
    project_root: Path = field(
        default_factory=lambda: Path(__file__).resolve().parent.parent
    )

    @property
    def testcases_dir(self) -> Path:
        return self.project_root / "testcases"

    @property
    def artifacts_fullpage_dir(self) -> Path:
        return self.project_root / "artifacts" / "fullpage"

    @property
    def artifacts_chatbox_dir(self) -> Path:
        return self.project_root / "artifacts" / "chatbox"

    @property
    def reports_dir(self) -> Path:
        return self.project_root / "reports"

    def ensure_dirs(self) -> None:
        """Create output directories if they do not exist."""
        for d in (
            self.artifacts_fullpage_dir,
            self.artifacts_chatbox_dir,
            self.reports_dir,
        ):
            d.mkdir(parents=True, exist_ok=True)


def load_config() -> Config:
    """Return a fully initialised :class:`Config` instance."""
    cfg = Config()
    cfg.ensure_dirs()
    return cfg
