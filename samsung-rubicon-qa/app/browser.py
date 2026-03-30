"""Playwright browser lifecycle management for per-case execution."""

from __future__ import annotations

import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from playwright.sync_api import Browser, BrowserContext, Page, Playwright, sync_playwright

from app.config import AppConfig
from app.utils import ensure_parent


@dataclass(slots=True)
class CaseBrowserSession:
    """Per-case browser session holding context and page objects."""

    case_id: str
    context: BrowserContext
    page: Page
    config: AppConfig

    def close(self, trace_target: Path | None = None, video_target: Path | None = None) -> tuple[str, str]:
        """Stop tracing, close the context, and move the recorded video if present."""

        video_source: Any = self.page.video
        trace_path = ""
        video_path = ""

        if self.config.enable_trace:
            if trace_target is not None:
                ensure_parent(trace_target)
                self.context.tracing.stop(path=str(trace_target))
                trace_path = str(trace_target)
            else:
                self.context.tracing.stop()

        self.context.close()

        if self.config.enable_video and video_source is not None:
            raw_video_path = Path(video_source.path())
            if video_target is not None:
                ensure_parent(video_target)
                shutil.copy2(raw_video_path, video_target)
                video_path = str(video_target)
            else:
                video_path = str(raw_video_path)

        return trace_path, video_path


class BrowserManager:
    """Manage the shared Playwright browser and create isolated case contexts."""

    def __init__(self, config: AppConfig, logger: Any) -> None:
        self.config = config
        self.logger = logger
        self._playwright: Playwright | None = None
        self._browser: Browser | None = None

    def start(self) -> None:
        """Start Playwright and launch Chromium."""

        self._playwright = sync_playwright().start()
        self._browser = self._playwright.chromium.launch(headless=self.config.headless)

    def new_case_session(self, case_id: str) -> CaseBrowserSession:
        """Create a new isolated browser context and page for a single case."""

        if self._browser is None:
            raise RuntimeError("BrowserManager.start() must be called first")

        context_kwargs: dict[str, Any] = {
            "locale": self.config.default_locale,
            "viewport": {"width": 1440, "height": 1200},
        }
        if self.config.enable_video:
            context_kwargs["record_video_dir"] = str(self.config.video_dir)
            context_kwargs["record_video_size"] = {"width": 1440, "height": 1200}

        context = self._browser.new_context(**context_kwargs)
        context.set_default_timeout(self.config.playwright_timeout_ms)
        page = context.new_page()
        page.set_default_timeout(self.config.playwright_timeout_ms)

        if self.config.enable_trace:
            context.tracing.start(screenshots=True, snapshots=True, sources=True)

        return CaseBrowserSession(case_id=case_id, context=context, page=page, config=self.config)

    def stop(self) -> None:
        """Close browser and Playwright runtime."""

        if self._browser is not None:
            self._browser.close()
        if self._playwright is not None:
            self._playwright.stop()
