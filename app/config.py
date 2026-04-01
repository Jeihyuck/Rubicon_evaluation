"""Configuration management: loads from .env or environment variables."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv

# Load .env if present (local development)
load_dotenv(dotenv_path=Path(__file__).parent.parent / ".env", override=False)


def _env_str(key: str, default: str = "") -> str:
    return os.environ.get(key, default)


def _env_bool(key: str, default: bool = False) -> bool:
    val = os.environ.get(key, str(default)).lower()
    return val in ("1", "true", "yes")


def _env_int(key: str, default: int = 0) -> int:
    try:
        return int(os.environ.get(key, str(default)))
    except ValueError:
        return default


def _env_float(key: str, default: float = 0.0) -> float:
    try:
        return float(os.environ.get(key, str(default)))
    except ValueError:
        return default


@dataclass
class AppConfig:
    """Central configuration object for the application."""

    # Target URL
    samsung_base_url: str = field(
        default_factory=lambda: _env_str("SAMSUNG_BASE_URL", "https://www.samsung.com/")
    )

    # Browser settings
    headless: bool = field(default_factory=lambda: _env_bool("HEADLESS", True))
    viewport_width: int = field(default_factory=lambda: _env_int("VIEWPORT_WIDTH", 1440))
    viewport_height: int = field(default_factory=lambda: _env_int("VIEWPORT_HEIGHT", 900))
    playwright_timeout_ms: int = field(
        default_factory=lambda: _env_int("PLAYWRIGHT_TIMEOUT_MS", 30_000)
    )

    # Locale / language
    default_locale: str = field(
        default_factory=lambda: _env_str("DEFAULT_LOCALE", "en-US")
    )

    # Test-run limits
    max_questions: int = field(
        default_factory=lambda: _env_int("MAX_QUESTIONS", 3)
    )

    # OpenAI settings
    openai_api_key: str = field(
        default_factory=lambda: _env_str("OPENAI_API_KEY", "")
    )
    openai_model: str = field(
        default_factory=lambda: _env_str("OPENAI_MODEL", "gpt-4o")
    )

    # Answer-stability detection
    answer_stable_checks: int = field(
        default_factory=lambda: _env_int("ANSWER_STABLE_CHECKS", 3)
    )
    answer_stable_interval_sec: float = field(
        default_factory=lambda: _env_float("ANSWER_STABLE_INTERVAL_SEC", 1.0)
    )

    # Path roots (relative to repo root)
    repo_root: Path = field(default_factory=lambda: Path(__file__).parent.parent)

    @property
    def testcases_dir(self) -> Path:
        return self.repo_root / "testcases"

    @property
    def artifacts_dir(self) -> Path:
        return self.repo_root / "artifacts"

    @property
    def reports_dir(self) -> Path:
        return self.repo_root / "reports"

    def ensure_dirs(self) -> None:
        """Create output directories if they don't exist."""
        (self.artifacts_dir / "fullpage").mkdir(parents=True, exist_ok=True)
        (self.artifacts_dir / "chatbox").mkdir(parents=True, exist_ok=True)
        self.reports_dir.mkdir(parents=True, exist_ok=True)


# Singleton
config = AppConfig()
