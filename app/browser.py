"""Playwright browser/context/page lifecycle management."""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import AsyncGenerator, Tuple

from playwright.async_api import (
    Browser,
    BrowserContext,
    Page,
    Playwright,
    async_playwright,
)

from app.config import AppConfig
from app.logger import logger


async def create_browser_context(
    playwright: Playwright, cfg: AppConfig
) -> Tuple[Browser, BrowserContext]:
    """Launch a Chromium browser and create a context with the given configuration."""
    logger.debug(
        "Launching browser: headless=%s, viewport=%dx%d, locale=%s",
        cfg.headless,
        cfg.viewport_width,
        cfg.viewport_height,
        cfg.default_locale,
    )
    browser: Browser = await playwright.chromium.launch(headless=cfg.headless)
    context: BrowserContext = await browser.new_context(
        viewport={"width": cfg.viewport_width, "height": cfg.viewport_height},
        locale=cfg.default_locale,
        ignore_https_errors=True,
    )
    context.set_default_timeout(cfg.playwright_timeout_ms)
    return browser, context


async def new_page(context: BrowserContext) -> Page:
    """Open a new page in *context*."""
    page = await context.new_page()
    return page


async def teardown(browser: Browser) -> None:
    """Close the browser and release all resources."""
    try:
        await browser.close()
        logger.debug("Browser closed.")
    except Exception as exc:
        logger.warning("Error while closing browser: %s", exc)


@asynccontextmanager
async def browser_session(
    cfg: AppConfig,
) -> AsyncGenerator[Tuple[BrowserContext, Page], None]:
    """Async context manager that yields ``(context, page)`` and tears down afterwards.

    Usage::

        async with browser_session(cfg) as (ctx, page):
            await page.goto(cfg.samsung_base_url)
    """
    async with async_playwright() as pw:
        browser, context = await create_browser_context(pw, cfg)
        page = await new_page(context)
        try:
            yield context, page
        finally:
            await teardown(browser)
