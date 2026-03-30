"""Core Samsung chat-widget automation logic.

Handles:
- Opening samsung.com
- Dismissing popups / cookie banners
- Locating and clicking the AI chat icon
- Resolving chat context (DOM vs. iframe)
- Submitting a question
- Waiting for a stable answer
- Extracting the last answer text
- Capturing screenshots
"""

from __future__ import annotations

import asyncio
import time
from pathlib import Path
from typing import List, Optional, Tuple, Union

from playwright.async_api import (
    Error as PlaywrightError,
    Frame,
    FrameLocator,
    Locator,
    Page,
    TimeoutError as PlaywrightTimeoutError,
)

from app.config import AppConfig, config as default_config
from app.logger import logger
from app.models import RunResult, TestCase
from app.utils import screenshot_name, utc_now_str, safe_normalize

# ---------------------------------------------------------------------------
# Type alias: a chat context is either a Page, Frame, or FrameLocator.
# ---------------------------------------------------------------------------
ChatContext = Union[Page, Frame]


# ---------------------------------------------------------------------------
# Selector candidate lists
# ---------------------------------------------------------------------------

# AI chat icon / FAB button
CHAT_ICON_CANDIDATES: List[str] = [
    "[aria-label*='Chat' i]",
    "[aria-label*='AI' i]",
    "[aria-label*='Assistant' i]",
    "[aria-label*='Support' i]",
    "[aria-label*='Help' i]",
    "[data-testid*='chat' i]",
    "[data-testid*='assistant' i]",
    "[class*='chat-icon' i]",
    "[class*='chatIcon' i]",
    "[class*='fab' i]",
    "[class*='floating' i]",
    "[class*='chat-btn' i]",
    "[class*='chatBtn' i]",
    "[class*='chat-bubble' i]",
    "[class*='ai-chat' i]",
    "button[class*='chat' i]",
    "div[class*='chat' i][role='button']",
    # Specific Samsung selectors (may change)
    ".chat-icon",
    "#chat-icon",
    ".samsung-chat-widget",
    "[id*='chat' i]",
    "[id*='ai-' i]",
    ".fixed button[class*='chat' i]",
]

# Question input field
INPUT_CANDIDATES: List[str] = [
    "textarea",
    "input[type='text']",
    "[role='textbox']",
    "[contenteditable='true']",
    "[placeholder*='question' i]",
    "[placeholder*='ask' i]",
    "[placeholder*='type' i]",
    "[placeholder*='message' i]",
    "[aria-label*='input' i]",
    "[aria-label*='message' i]",
    "[aria-label*='question' i]",
    "[data-testid*='input' i]",
    "[data-testid*='message' i]",
    "[class*='input' i]",
    "[class*='textarea' i]",
]

# Send button
SEND_BUTTON_CANDIDATES: List[str] = [
    "button[aria-label*='Send' i]",
    "button[aria-label*='Submit' i]",
    "button[type='submit']",
    "[data-testid*='send' i]",
    "[data-testid*='submit' i]",
    "button[class*='send' i]",
    "button[class*='submit' i]",
    "button svg[class*='send' i]",
    # Arrow-style icon buttons often used in chat UIs
    "button:has(svg)",
    "[role='button'][aria-label*='Send' i]",
    "[role='button'][aria-label*='전송' i]",
]

# Bot/answer message containers
BOT_MESSAGE_CANDIDATES: List[str] = [
    "[class*='bot-message' i]",
    "[class*='botMessage' i]",
    "[class*='agent-message' i]",
    "[class*='agentMessage' i]",
    "[data-message-author='bot']",
    "[data-message-author='assistant']",
    "[data-author='bot']",
    "[class*='assistant-message' i]",
    "[class*='chat-answer' i]",
    "[class*='chat-response' i]",
    "[class*='response-text' i]",
    "[role='log'] [class*='message' i]:last-child",
    "[role='list'] [class*='message' i]:last-child",
    "[class*='chat-message' i]:last-child",
    "[class*='message-bubble' i]:last-child",
]

# Loading / typing indicators (should disappear when answer is ready)
LOADING_CANDIDATES: List[str] = [
    "[class*='loading' i]",
    "[class*='typing' i]",
    "[class*='spinner' i]",
    "[class*='thinking' i]",
    "[class*='pending' i]",
    "[aria-label*='loading' i]",
    "[aria-label*='typing' i]",
]

# Popup / cookie banner dismiss buttons
POPUP_DISMISS_CANDIDATES: List[str] = [
    "button[id*='accept' i]",
    "button[class*='accept' i]",
    "button[aria-label*='accept' i]",
    "button[id*='cookie' i]",
    "[id*='cookie'] button",
    "[class*='cookie'] button",
    "button[class*='close' i]",
    "[aria-label*='close' i]",
    "[data-testid*='close' i]",
    ".modal button[class*='close' i]",
    ".modal button[class*='dismiss' i]",
]


# ---------------------------------------------------------------------------
# Helper: try a list of selectors, return first visible locator found
# ---------------------------------------------------------------------------

async def _find_first(
    ctx: ChatContext,
    selectors: List[str],
    timeout_ms: int = 3_000,
) -> Optional[Locator]:
    """Try each selector in *selectors*, return the first visible match.

    Returns ``None`` if none are found within *timeout_ms* each.
    """
    for sel in selectors:
        try:
            loc = ctx.locator(sel).first
            await loc.wait_for(state="visible", timeout=timeout_ms)
            return loc
        except (PlaywrightTimeoutError, PlaywrightError):
            continue
    return None


# ---------------------------------------------------------------------------
# Step 1 – open homepage
# ---------------------------------------------------------------------------

async def open_homepage(page: Page, url: str) -> None:
    """Navigate to the Samsung homepage and wait until networkidle."""
    logger.info("Opening homepage: %s", url)
    await page.goto(url, wait_until="domcontentloaded", timeout=60_000)
    # Give JS components time to mount without an unbounded wait
    try:
        await page.wait_for_load_state("networkidle", timeout=15_000)
    except PlaywrightTimeoutError:
        logger.debug("networkidle timeout – proceeding anyway")
    logger.info("Page opened: %s", page.url)


# ---------------------------------------------------------------------------
# Step 2 – dismiss popups
# ---------------------------------------------------------------------------

async def dismiss_popups(page: Page) -> None:
    """Best-effort popup/cookie-banner dismissal."""
    logger.debug("Attempting popup dismissal…")
    dismissed = 0
    for sel in POPUP_DISMISS_CANDIDATES:
        try:
            btn = page.locator(sel).first
            await btn.wait_for(state="visible", timeout=2_000)
            await btn.click(timeout=3_000)
            dismissed += 1
            logger.debug("Dismissed popup via selector: %s", sel)
            await page.wait_for_timeout(500)
        except (PlaywrightTimeoutError, PlaywrightError):
            continue
    if dismissed:
        logger.info("Dismissed %d popup(s)", dismissed)
    else:
        logger.debug("No dismissable popups found")


# ---------------------------------------------------------------------------
# Step 3 – open chat widget
# ---------------------------------------------------------------------------

async def open_chat_widget(page: Page, cfg: AppConfig) -> None:
    """Find and click the AI chat icon to open the widget."""
    logger.info("Searching for chat icon…")
    icon = await _find_first(page, CHAT_ICON_CANDIDATES, timeout_ms=5_000)
    if icon is None:
        # Scroll to bottom-right – FAB buttons are usually fixed but let's ensure
        await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
        await page.wait_for_timeout(1_000)
        icon = await _find_first(page, CHAT_ICON_CANDIDATES, timeout_ms=5_000)

    if icon is None:
        raise RuntimeError("Chat icon not found after exhausting all selector candidates.")

    await icon.scroll_into_view_if_needed()
    await icon.click(timeout=10_000)
    logger.info("Chat icon clicked – waiting for widget to open…")
    # Wait for any input field to appear (indicates widget is ready)
    await _wait_for_any_input(page, timeout_ms=cfg.playwright_timeout_ms)


async def _wait_for_any_input(page: Page, timeout_ms: int = 30_000) -> None:
    """Wait until an input field becomes visible (indicates widget is ready)."""
    deadline = time.monotonic() + timeout_ms / 1_000
    while time.monotonic() < deadline:
        # Try page-level first
        loc = await _find_first(page, INPUT_CANDIDATES, timeout_ms=2_000)
        if loc:
            logger.debug("Chat input found in page DOM")
            return
        # Try frames
        for frame in page.frames:
            if frame == page.main_frame:
                continue
            try:
                for sel in INPUT_CANDIDATES:
                    try:
                        fl = frame.locator(sel).first
                        await fl.wait_for(state="visible", timeout=1_000)
                        logger.debug("Chat input found in frame: %s", frame.url)
                        return
                    except (PlaywrightTimeoutError, PlaywrightError):
                        continue
            except Exception:
                continue
        await asyncio.sleep(0.5)
    logger.warning("Chat input not visible after %d ms – continuing anyway", timeout_ms)


# ---------------------------------------------------------------------------
# Step 4 – resolve chat context (DOM or iframe)
# ---------------------------------------------------------------------------

async def resolve_chat_context(page: Page) -> Tuple[ChatContext, bool]:
    """Determine whether the chat UI lives in the page DOM or an iframe.

    Returns:
        A tuple ``(context, is_iframe)`` where *context* is the
        :class:`~playwright.async_api.Frame` or :class:`~playwright.async_api.Page`
        that contains the chat UI.
    """
    logger.debug("Resolving chat context…")

    # --- Try page DOM first ---
    input_loc = await _find_first(page, INPUT_CANDIDATES, timeout_ms=3_000)
    if input_loc:
        logger.info("Chat context: page DOM")
        return page, False

    # --- Traverse child frames ---
    best_frame: Optional[Frame] = None
    best_score = 0

    for frame in page.frames:
        if frame == page.main_frame:
            continue
        score = 0
        for sel_list in (INPUT_CANDIDATES, SEND_BUTTON_CANDIDATES, BOT_MESSAGE_CANDIDATES):
            for sel in sel_list:
                try:
                    loc = frame.locator(sel).first
                    await loc.wait_for(state="attached", timeout=500)
                    score += 1
                    break  # count this category only once
                except (PlaywrightTimeoutError, PlaywrightError):
                    continue
        if score > best_score:
            best_score = score
            best_frame = frame

    if best_frame is not None:
        logger.info(
            "Chat context: iframe (score=%d, url=%s)", best_score, best_frame.url
        )
        return best_frame, True

    # Fall back to page itself – maybe the widget hasn't fully loaded yet
    logger.warning("Could not isolate chat iframe; using page as context")
    return page, False


# ---------------------------------------------------------------------------
# Step 5 – submit question
# ---------------------------------------------------------------------------

async def submit_question(ctx: ChatContext, question: str, cfg: AppConfig) -> None:
    """Type *question* into the chat input and press Send."""
    logger.info("Submitting question: %s", question[:80])

    # --- Locate input ---
    input_loc = await _find_first(ctx, INPUT_CANDIDATES, timeout_ms=cfg.playwright_timeout_ms)
    if input_loc is None:
        raise RuntimeError("Could not find chat input field")

    await input_loc.scroll_into_view_if_needed()
    await input_loc.click()
    await input_loc.fill(question)
    logger.debug("Question typed into input")

    # --- Locate send button ---
    send_btn = await _find_first(ctx, SEND_BUTTON_CANDIDATES, timeout_ms=5_000)
    if send_btn:
        await send_btn.click(timeout=10_000)
        logger.debug("Send button clicked")
    else:
        # Fallback: press Enter
        await input_loc.press("Enter")
        logger.debug("Send via Enter key (no send button found)")


# ---------------------------------------------------------------------------
# Step 6 – wait for answer completion
# ---------------------------------------------------------------------------

async def wait_for_answer_completion(
    ctx: ChatContext, cfg: AppConfig
) -> Optional[str]:
    """Wait until the bot's reply is stable (text stops changing).

    Strategy:
        1. Wait for any bot-message element to be visible.
        2. Poll the last bot-message text.
        3. Declare stable after ``cfg.answer_stable_checks`` consecutive identical
           reads spaced ``cfg.answer_stable_interval_sec`` seconds apart.
        4. Return stable text, or best available on timeout.
    """
    logger.info("Waiting for answer to stabilise…")
    deadline = time.monotonic() + (cfg.playwright_timeout_ms / 1_000)

    # 1. Wait for loading indicators to disappear (best effort)
    for sel in LOADING_CANDIDATES:
        try:
            loc = ctx.locator(sel).first
            await loc.wait_for(state="hidden", timeout=cfg.playwright_timeout_ms)
        except (PlaywrightTimeoutError, PlaywrightError):
            pass

    # 2. Wait for at least one bot message to appear
    bot_msg_loc: Optional[Locator] = None
    while time.monotonic() < deadline:
        bot_msg_loc = await _find_first(ctx, BOT_MESSAGE_CANDIDATES, timeout_ms=2_000)
        if bot_msg_loc:
            break
        await asyncio.sleep(0.5)

    if bot_msg_loc is None:
        logger.warning("No bot message found; returning empty string")
        return ""

    # 3. Stability polling
    prev_texts: List[str] = []
    stable_count = 0
    last_text = ""

    while time.monotonic() < deadline:
        try:
            # Re-query the LAST bot message each iteration to handle newly appended messages
            last_bot = await _get_last_bot_message_text(ctx)
            normalised = safe_normalize(last_bot)

            if normalised == last_text and normalised:
                stable_count += 1
            else:
                stable_count = 0
                last_text = normalised

            if stable_count >= cfg.answer_stable_checks and last_text:
                logger.info("Answer stable after %d checks", stable_count)
                return last_text

        except Exception as exc:
            logger.debug("Error during stability poll: %s", exc)

        await asyncio.sleep(cfg.answer_stable_interval_sec)

    logger.warning("Answer stability timeout; returning last observed text")
    return last_text


async def _get_last_bot_message_text(ctx: ChatContext) -> str:
    """Return the text content of the most recent bot message element."""
    for sel in BOT_MESSAGE_CANDIDATES:
        try:
            # Locate ALL matching elements, take the last
            locs = ctx.locator(sel)
            count = await locs.count()
            if count > 0:
                last = locs.nth(count - 1)
                text = await last.inner_text(timeout=3_000)
                if text and text.strip():
                    return text.strip()
        except (PlaywrightTimeoutError, PlaywrightError):
            continue
    return ""


# ---------------------------------------------------------------------------
# Step 7 – extract last answer
# ---------------------------------------------------------------------------

async def extract_last_answer(ctx: ChatContext) -> str:
    """Extract the text of the last bot message."""
    text = await _get_last_bot_message_text(ctx)
    logger.info("Extracted answer (%d chars)", len(text))
    return text


# ---------------------------------------------------------------------------
# Step 8 – capture artifacts
# ---------------------------------------------------------------------------

async def capture_artifacts(
    page: Page,
    ctx: ChatContext,
    case_id: str,
    cfg: AppConfig,
) -> Tuple[str, str]:
    """Save full-page and chat-area screenshots.

    Returns:
        A tuple ``(fullpage_path, chatbox_path)``.
    """
    full_path = ""
    chat_path = ""

    fullpage_dir = cfg.artifacts_dir / "fullpage"
    chatbox_dir = cfg.artifacts_dir / "chatbox"
    fullpage_dir.mkdir(parents=True, exist_ok=True)
    chatbox_dir.mkdir(parents=True, exist_ok=True)

    ts = utc_now_str()

    # Full-page screenshot
    try:
        fname = f"{ts}_{case_id}_fullpage.png"
        full_path_obj = fullpage_dir / fname
        await page.screenshot(path=str(full_path_obj), full_page=True)
        full_path = str(full_path_obj)
        logger.info("Full-page screenshot saved: %s", full_path)
    except Exception as exc:
        logger.warning("Failed to capture full-page screenshot: %s", exc)

    # Chat-area screenshot (last bot message or whole context)
    try:
        fname = f"{ts}_{case_id}_chatbox.png"
        chat_path_obj = chatbox_dir / fname

        # Try to screenshot just the last bot message element
        bot_el: Optional[Locator] = None
        for sel in BOT_MESSAGE_CANDIDATES:
            try:
                locs = ctx.locator(sel)
                count = await locs.count()
                if count > 0:
                    bot_el = locs.nth(count - 1)
                    break
            except (PlaywrightTimeoutError, PlaywrightError):
                continue

        if bot_el:
            await bot_el.screenshot(path=str(chat_path_obj))
        else:
            # Fall back to full page when chat element not isolatable
            await page.screenshot(path=str(chat_path_obj), full_page=False)

        chat_path = str(chat_path_obj)
        logger.info("Chat screenshot saved: %s", chat_path)
    except Exception as exc:
        logger.warning("Failed to capture chat screenshot: %s", exc)

    return full_path, chat_path


# ---------------------------------------------------------------------------
# Top-level: run a single test case
# ---------------------------------------------------------------------------

async def run_single_question(
    page: Page,
    test_case: TestCase,
    cfg: AppConfig,
) -> RunResult:
    """Execute one QA test case and return a populated :class:`RunResult`.

    This function is the main entry point called by the orchestrator for each
    test case. It handles all automation steps and records errors without
    propagating exceptions to the caller.
    """
    from app.utils import iso_utc_now  # local import to avoid circulars

    result = RunResult(
        run_timestamp=iso_utc_now(),
        case_id=test_case.id,
        category=test_case.category,
        question=test_case.question,
    )

    target_url = test_case.page_url or cfg.samsung_base_url

    try:
        # 1. Open page
        await open_homepage(page, target_url)

        # 2. Dismiss popups
        await dismiss_popups(page)

        # 3. Open chat widget
        await open_chat_widget(page, cfg)
        logger.info("Chat widget opened")

        # 4. Resolve context
        ctx, is_iframe = await resolve_chat_context(page)
        logger.info("Chat context resolved (iframe=%s)", is_iframe)

        # 5. Submit question & measure response time
        t_start = time.monotonic()
        await submit_question(ctx, test_case.question, cfg)

        # 6. Wait for stable answer
        answer = await wait_for_answer_completion(ctx, cfg)
        result.response_ms = (time.monotonic() - t_start) * 1_000

        if answer:
            result.answer = answer
            result.status = "success"
            logger.info("Answer received (%.0f ms)", result.response_ms)
        else:
            result.status = "failed"
            result.error_message = "No answer received from chat widget"
            logger.warning("No answer received for case %s", test_case.id)

        # 7. Extract last answer (re-confirm)
        if not result.answer:
            result.answer = await extract_last_answer(ctx)

        # 8. Capture artifacts
        full_path, chat_path = await capture_artifacts(page, ctx, test_case.id, cfg)
        result.full_screenshot_path = full_path
        result.chat_screenshot_path = chat_path
        logger.info("Screenshots saved for case %s", test_case.id)

    except Exception as exc:
        result.status = "failed"
        result.error_message = str(exc)
        logger.exception("Error running test case %s: %s", test_case.id, exc)

        # Attempt to save error screenshot
        try:
            error_dir = cfg.artifacts_dir / "fullpage"
            error_dir.mkdir(parents=True, exist_ok=True)
            ts = utc_now_str()
            err_path = error_dir / f"{ts}_{test_case.id}_error.png"
            await page.screenshot(path=str(err_path), full_page=True)
            result.full_screenshot_path = str(err_path)
            logger.info("Error screenshot saved: %s", err_path)
        except Exception as ss_exc:
            logger.warning("Failed to save error screenshot: %s", ss_exc)

    return result
