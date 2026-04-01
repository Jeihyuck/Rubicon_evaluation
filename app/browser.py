"""Playwright browser / context / page lifecycle management."""
from __future__ import annotations

import logging
from typing import Optional, Tuple

from playwright.sync_api import (
    Browser,
    BrowserContext,
    Page,
    Playwright,
    sync_playwright,
)

from app.config import Config

log = logging.getLogger("samsung_chat_qa.browser")


class BrowserManager:
    """Manages the lifecycle of a single Playwright browser session.

    Usage::

        mgr = BrowserManager(config)
        mgr.start()
        page = mgr.page
        # ... automation ...
        mgr.stop()

    Or as a context manager::

        with BrowserManager(config) as mgr:
            page = mgr.page
    """

    def __init__(self, config: Config) -> None:
        self._config = config
        self._playwright: Optional[Playwright] = None
        self._browser: Optional[Browser] = None
        self._context: Optional[BrowserContext] = None
        self._page: Optional[Page] = None

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def page(self) -> Page:
        if self._page is None:
            raise RuntimeError("BrowserManager has not been started yet.")
        return self._page

    @property
    def context(self) -> BrowserContext:
        if self._context is None:
            raise RuntimeError("BrowserManager has not been started yet.")
        return self._context

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def start(self) -> "BrowserManager":
        """Launch Chromium and open a new page."""
        log.info(
            "Launching Chromium (headless=%s, viewport=%dx%d)",
            self._config.headless,
            self._config.viewport_width,
            self._config.viewport_height,
        )
        self._playwright = sync_playwright().start()
        self._browser = self._playwright.chromium.launch(
            headless=self._config.headless,
            args=[
                "--no-sandbox",
                "--disable-dev-shm-usage",
                "--disable-gpu",
            ],
        )
        self._context = self._browser.new_context(
            viewport={
                "width": self._config.viewport_width,
                "height": self._config.viewport_height,
            },
            locale=self._config.default_locale,
            # Accept common language headers to reach the correct regional site.
            extra_http_headers={"Accept-Language": self._config.default_locale},
        )
        self._context.set_default_timeout(self._config.playwright_timeout_ms)
        self._page = self._context.new_page()
        log.info("Browser started successfully.")
        return self

    def stop(self) -> None:
        """Close the browser and stop Playwright."""
        try:
            if self._page and not self._page.is_closed():
                self._page.close()
            if self._context:
                self._context.close()
            if self._browser:
                self._browser.close()
        except Exception as exc:  # pragma: no cover
            log.warning("Error during browser teardown: %s", exc)
        finally:
            if self._playwright:
                self._playwright.stop()
            self._page = None
            self._context = None
            self._browser = None
            self._playwright = None
            log.info("Browser stopped.")

    # ------------------------------------------------------------------
    # Context manager support
    # ------------------------------------------------------------------

    def __enter__(self) -> "BrowserManager":
        return self.start()

    def __exit__(self, *_: object) -> None:
        self.stop()
