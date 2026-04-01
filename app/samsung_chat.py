"""Samsung.com chat widget automation.

This module implements every step required to interact with the AI chat
widget embedded on www.samsung.com:

1. Open the home page.
2. Dismiss cookie/popup overlays.
3. Locate and click the chat icon.
4. Resolve the chat context (page DOM *or* iframe).
5. Submit a question.
6. Wait for the answer to stabilise.
7. Extract the final answer text.
8. Capture screenshots.
"""
from __future__ import annotations

import logging
import time
from pathlib import Path
from typing import List, Optional, Tuple, Union

from playwright.sync_api import (
    ElementHandle,
    Frame,
    FrameLocator,
    Locator,
    Page,
    TimeoutError as PWTimeoutError,
)

from app.config import Config
from app.models import TestCase
from app.utils import build_screenshot_name

log = logging.getLogger("samsung_chat_qa.samsung_chat")

# ---------------------------------------------------------------------------
# Type alias: a chat context is either the main Page or a Frame
# ---------------------------------------------------------------------------
ChatContext = Union[Page, Frame]

# ---------------------------------------------------------------------------
# Selector candidate lists
# ---------------------------------------------------------------------------

# AI chat icon / FAB (bottom-right)
_CHAT_ICON_CANDIDATES: List[str] = [
    "[aria-label*='chat' i]",
    "[aria-label*='AI' i]",
    "[aria-label*='assistant' i]",
    "[aria-label*='support' i]",
    "[aria-label*='help' i]",
    "[data-testid*='chat']",
    "[data-testid*='ai']",
    "[class*='chat-icon']",
    "[class*='chatbot']",
    "[class*='live-chat']",
    "[class*='floating']",
    "[class*='fab']",
    "button[class*='chat']",
    "a[class*='chat']",
    "#chat-icon",
    "#chatbot-button",
    ".chat-btn",
    ".open-chat",
    # Generic fixed/absolute positioned buttons in the lower-right area
    "div[style*='fixed'] button",
    "div[style*='position:fixed'] button",
]

# Question input
_INPUT_CANDIDATES: List[str] = [
    "textarea",
    "input[type='text']",
    "[contenteditable='true']",
    "[role='textbox']",
    "[aria-label*='message' i]",
    "[aria-label*='question' i]",
    "[aria-label*='input' i]",
    "[placeholder*='message' i]",
    "[placeholder*='question' i]",
    "[placeholder*='ask' i]",
    "[placeholder*='type' i]",
    "[data-testid*='input']",
    "[class*='input']",
    "[class*='message-input']",
    "[class*='chat-input']",
]

# Send button
_SEND_BUTTON_CANDIDATES: List[str] = [
    "button[aria-label*='send' i]",
    "button[aria-label*='submit' i]",
    "button[type='submit']",
    "[data-testid*='send']",
    "[class*='send-btn']",
    "[class*='submit-btn']",
    "button[class*='send']",
    "button[class*='submit']",
    # Icon-only buttons near the input
    "button > svg",
    "button > img",
    "button",
]

# Bot / assistant message elements
_BOT_MESSAGE_CANDIDATES: List[str] = [
    "[data-message-author='bot']",
    "[data-message-author='assistant']",
    "[data-sender='bot']",
    "[data-sender='assistant']",
    ".bot-message",
    ".agent-message",
    ".assistant-message",
    "[class*='bot-message']",
    "[class*='agent-message']",
    "[class*='assistant']",
    "[role='log'] > *",
    "[role='feed'] > *",
    "[aria-live] > *",
    ".chat-bubble",
    ".message-bubble",
    "[class*='message']",
]

# Loading / typing / spinner indicators
_LOADING_CANDIDATES: List[str] = [
    "[class*='typing']",
    "[class*='loading']",
    "[class*='spinner']",
    "[class*='dots']",
    "[aria-label*='loading' i]",
    "[aria-busy='true']",
    ".thinking",
    ".pending",
]

# Popup / overlay close buttons
_POPUP_CLOSE_CANDIDATES: List[str] = [
    "button[aria-label*='close' i]",
    "button[aria-label*='dismiss' i]",
    "button[aria-label*='accept' i]",
    "[id*='cookie'] button",
    "[class*='cookie'] button",
    "[class*='modal'] button[class*='close']",
    "[class*='overlay'] button",
    "[class*='popup'] button[class*='close']",
    "#onetrust-accept-btn-handler",
    ".accept-cookies",
    "[data-testid*='close']",
]


# ---------------------------------------------------------------------------
# Helper: try locators in sequence
# ---------------------------------------------------------------------------

def _first_visible(ctx: ChatContext, selectors: List[str], timeout_ms: int = 5000) -> Optional[Locator]:
    """Return the first visible locator that resolves within *timeout_ms*.

    Parameters
    ----------
    ctx:
        A Playwright :class:`Page` or :class:`Frame`.
    selectors:
        CSS selector candidates to try in order.
    timeout_ms:
        Per-candidate timeout in milliseconds.
    """
    for sel in selectors:
        try:
            loc = ctx.locator(sel).first
            loc.wait_for(state="visible", timeout=timeout_ms)
            return loc
        except PWTimeoutError:
            continue
        except Exception as exc:
            log.debug("Selector '%s' error: %s", sel, exc)
    return None


def _click_first_visible(
    ctx: ChatContext, selectors: List[str], label: str, timeout_ms: int = 5000
) -> bool:
    """Click the first visible element matching any selector in *selectors*.

    Returns ``True`` on success, ``False`` otherwise.
    """
    loc = _first_visible(ctx, selectors, timeout_ms)
    if loc is not None:
        try:
            loc.scroll_into_view_if_needed()
            loc.click()
            log.info("Clicked %s.", label)
            return True
        except Exception as exc:
            log.warning("Failed to click %s: %s", label, exc)
    log.warning("Could not find %s.", label)
    return False


# ---------------------------------------------------------------------------
# Step 1 – Open home page
# ---------------------------------------------------------------------------

def open_homepage(page: Page, url: str) -> None:
    """Navigate to *url* and wait for the page to be interactive.

    Parameters
    ----------
    page:
        Active Playwright page.
    url:
        Full URL to load (e.g. ``https://www.samsung.com/``).
    """
    log.info("Opening URL: %s", url)
    page.goto(url, wait_until="domcontentloaded", timeout=60_000)
    # Give dynamic content a moment to inject the chat widget.
    page.wait_for_load_state("networkidle", timeout=15_000)
    log.info("Page opened: %s", page.url)


# ---------------------------------------------------------------------------
# Step 2 – Dismiss popups / cookie banners
# ---------------------------------------------------------------------------

def dismiss_popups(page: Page) -> None:
    """Best-effort dismissal of cookie consent / overlay dialogs."""
    log.info("Attempting to dismiss popups / cookie banners …")
    dismissed = 0
    for sel in _POPUP_CLOSE_CANDIDATES:
        try:
            loc = page.locator(sel).first
            if loc.is_visible(timeout=2000):
                loc.click(timeout=3000)
                dismissed += 1
                log.debug("Dismissed popup via selector: %s", sel)
                page.wait_for_timeout(500)
        except Exception:
            pass
    log.info("Dismissed %d popup element(s).", dismissed)


# ---------------------------------------------------------------------------
# Step 3 – Open chat widget
# ---------------------------------------------------------------------------

def open_chat_widget(page: Page) -> None:
    """Locate and click the AI chat FAB in the lower-right corner.

    Raises :class:`RuntimeError` if the chat icon cannot be found.
    """
    log.info("Searching for the AI chat icon …")

    # Scroll to the bottom of the page to ensure the FAB is in view.
    page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
    page.wait_for_timeout(1000)

    success = _click_first_visible(page, _CHAT_ICON_CANDIDATES, "chat icon", timeout_ms=8000)
    if not success:
        # Take a diagnostic screenshot before raising.
        _save_debug_screenshot(page, "chat_icon_not_found")
        raise RuntimeError(
            "Could not locate the AI chat icon. "
            "Check selector candidates in samsung_chat.py."
        )

    # Wait briefly for the widget to animate open.
    page.wait_for_timeout(2000)
    log.info("Chat widget opened.")


# ---------------------------------------------------------------------------
# Step 4 – Resolve chat context (main DOM or iframe)
# ---------------------------------------------------------------------------

def resolve_chat_context(page: Page) -> ChatContext:
    """Return the :class:`Page` or :class:`Frame` that hosts the chat widget.

    Strategy
    --------
    1. Check whether an input box is visible directly on the main page.
    2. If not, iterate ``page.frames`` and look for the frame that contains
       *both* an input and at least one send-button candidate.
    3. Fall back to the first frame that contains a textbox.
    """
    log.info("Resolving chat context …")

    # --- Try main page first ---
    for sel in _INPUT_CANDIDATES:
        try:
            if page.locator(sel).first.is_visible(timeout=3000):
                log.info("Chat context: main page DOM (selector: %s)", sel)
                return page
        except Exception:
            pass

    # --- Iterate frames ---
    best_frame: Optional[Frame] = None
    best_score = 0

    for frame in page.frames:
        if frame == page.main_frame:
            continue
        score = _score_frame(frame)
        log.debug("Frame %s score=%d", frame.url, score)
        if score > best_score:
            best_score = score
            best_frame = frame

    if best_frame is not None and best_score > 0:
        log.info("Chat context: iframe (url=%s, score=%d)", best_frame.url, best_score)
        return best_frame

    log.warning(
        "Could not confirm chat context; falling back to main page. "
        "Widget interaction may fail."
    )
    return page


def _score_frame(frame: Frame) -> int:
    """Assign a numeric score to *frame* based on chat-widget indicator presence."""
    score = 0
    for sel in _INPUT_CANDIDATES:
        try:
            if frame.locator(sel).count() > 0:
                score += 2
                break
        except Exception:
            pass
    for sel in _SEND_BUTTON_CANDIDATES:
        try:
            if frame.locator(sel).count() > 0:
                score += 1
                break
        except Exception:
            pass
    for sel in _BOT_MESSAGE_CANDIDATES:
        try:
            if frame.locator(sel).count() > 0:
                score += 1
                break
        except Exception:
            pass
    return score


# ---------------------------------------------------------------------------
# Step 5 – Submit question
# ---------------------------------------------------------------------------

def submit_question(ctx: ChatContext, question: str) -> None:
    """Type *question* into the chat input and send it.

    Raises :class:`RuntimeError` when neither the input nor the send button
    can be located.
    """
    log.info("Submitting question: %s", question[:80])

    # Find input
    input_loc = _first_visible(ctx, _INPUT_CANDIDATES, timeout_ms=10_000)
    if input_loc is None:
        raise RuntimeError("Could not find the chat input field.")

    input_loc.click()
    input_loc.fill(question)
    log.debug("Question typed into input.")

    # Find send button – try clicking it first; fall back to Enter key.
    send_loc = _first_visible(ctx, _SEND_BUTTON_CANDIDATES, timeout_ms=5000)
    if send_loc is not None:
        send_loc.click()
        log.debug("Send button clicked.")
    else:
        # Fallback: press Enter in the input field.
        input_loc.press("Enter")
        log.debug("Pressed Enter to send question.")


# ---------------------------------------------------------------------------
# Step 6 – Wait for answer completion
# ---------------------------------------------------------------------------

def wait_for_answer_completion(
    ctx: ChatContext,
    config: Config,
) -> str:
    """Poll until the last bot message has stabilised.

    Returns
    -------
    str
        The stable answer text.  May be empty if no answer arrived within
        the timeout.
    """
    log.info("Waiting for answer to stabilise …")

    timeout_sec = config.playwright_timeout_ms / 1000.0
    stable_needed = config.answer_stable_checks
    interval = config.answer_stable_interval_sec

    deadline = time.monotonic() + timeout_sec
    consecutive_stable = 0
    last_text = ""

    while time.monotonic() < deadline:
        # 1. Check whether a loading indicator is still visible.
        loading_visible = _any_visible(ctx, _LOADING_CANDIDATES)
        if loading_visible:
            log.debug("Loading indicator still present; waiting …")
            time.sleep(interval)
            consecutive_stable = 0
            continue

        # 2. Extract latest bot message text.
        current_text = _get_last_bot_message_text(ctx)

        # 3. Stability check.
        if current_text and current_text == last_text:
            consecutive_stable += 1
            log.debug(
                "Stable check %d/%d (len=%d)",
                consecutive_stable,
                stable_needed,
                len(current_text),
            )
            if consecutive_stable >= stable_needed:
                log.info("Answer stabilised (len=%d).", len(current_text))
                return current_text
        else:
            consecutive_stable = 0
            last_text = current_text

        time.sleep(interval)

    # Timeout – return whatever we have.
    log.warning("Answer wait timed out; returning last captured text (len=%d).", len(last_text))
    return last_text


def _any_visible(ctx: ChatContext, selectors: List[str]) -> bool:
    """Return ``True`` if any selector is currently visible."""
    for sel in selectors:
        try:
            if ctx.locator(sel).first.is_visible(timeout=500):
                return True
        except Exception:
            pass
    return False


def _get_last_bot_message_text(ctx: ChatContext) -> str:
    """Return the text content of the last bot-message element."""
    for sel in _BOT_MESSAGE_CANDIDATES:
        try:
            items = ctx.locator(sel)
            count = items.count()
            if count > 0:
                text = items.nth(count - 1).inner_text(timeout=2000)
                if text and text.strip():
                    return text.strip()
        except Exception:
            continue
    return ""


# ---------------------------------------------------------------------------
# Step 7 – Extract last answer
# ---------------------------------------------------------------------------

def extract_last_answer(ctx: ChatContext) -> str:
    """Return the text of the most-recent bot reply."""
    text = _get_last_bot_message_text(ctx)
    if not text:
        log.warning("No bot message text could be extracted.")
    else:
        log.info("Answer extracted (len=%d).", len(text))
    return text


# ---------------------------------------------------------------------------
# Step 8 – Capture screenshots
# ---------------------------------------------------------------------------

def capture_artifacts(
    page: Page,
    ctx: ChatContext,
    case_id: str,
    config: Config,
) -> Tuple[str, str]:
    """Save full-page and chat-area screenshots.

    Returns
    -------
    Tuple[str, str]
        ``(fullpage_path, chatbox_path)`` as strings.
    """
    ts_name = build_screenshot_name(case_id)

    fullpage_path = config.artifacts_fullpage_dir / f"{ts_name}.png"
    chatbox_path = config.artifacts_chatbox_dir / f"{ts_name}.png"

    # Full-page screenshot
    try:
        page.screenshot(path=str(fullpage_path), full_page=True)
        log.info("Full-page screenshot saved: %s", fullpage_path)
    except Exception as exc:
        log.warning("Full-page screenshot failed: %s", exc)
        fullpage_path = Path("")

    # Chat-area screenshot: try to find a specific chat container.
    chat_element = _first_chat_element(ctx)
    if chat_element is not None:
        try:
            chat_element.screenshot(path=str(chatbox_path))
            log.info("Chat-area screenshot saved: %s", chatbox_path)
        except Exception as exc:
            log.warning("Chat-area screenshot failed (%s); falling back to viewport.", exc)
            _fallback_viewport_screenshot(page, chatbox_path)
    else:
        _fallback_viewport_screenshot(page, chatbox_path)

    return str(fullpage_path), str(chatbox_path)


def _first_chat_element(ctx: ChatContext) -> Optional[Locator]:
    """Try to locate a chat container element."""
    container_candidates = [
        "[class*='chat-window']",
        "[class*='chat-container']",
        "[class*='chat-widget']",
        "[class*='chat-box']",
        "[class*='chatbot']",
        "[role='dialog']",
        "[role='complementary']",
        "[role='log']",
    ]
    for sel in container_candidates:
        try:
            loc = ctx.locator(sel).first
            if loc.is_visible(timeout=2000):
                return loc
        except Exception:
            pass
    # Fall back to the last bot message element.
    return _first_visible(ctx, _BOT_MESSAGE_CANDIDATES, timeout_ms=2000)


def _fallback_viewport_screenshot(page: Page, path: Path) -> None:
    """Save a viewport (non-full-page) screenshot to *path*."""
    try:
        page.screenshot(path=str(path))
        log.info("Viewport screenshot saved (fallback): %s", path)
    except Exception as exc:
        log.warning("Viewport screenshot also failed: %s", exc)


def _save_debug_screenshot(page: Page, label: str) -> None:
    """Save a debug screenshot to ``artifacts/fullpage``."""
    try:
        from app.utils import build_screenshot_name, get_project_root
        out = get_project_root() / "artifacts" / "fullpage" / f"DEBUG_{build_screenshot_name(label)}.png"
        out.parent.mkdir(parents=True, exist_ok=True)
        page.screenshot(path=str(out), full_page=True)
        log.info("Debug screenshot saved: %s", out)
    except Exception as exc:
        log.warning("Could not save debug screenshot: %s", exc)


# ---------------------------------------------------------------------------
# Top-level: run one test case
# ---------------------------------------------------------------------------

def run_single_question(
    page: Page,
    test_case: TestCase,
    config: Config,
) -> Tuple[str, str, str, float, str, str]:
    """Execute one full chat Q&A cycle for *test_case*.

    Returns
    -------
    Tuple[str, str, str, float, str, str]
        ``(answer, full_screenshot, chat_screenshot, response_ms, status, error_message)``
    """
    answer = ""
    full_screenshot = ""
    chat_screenshot = ""
    response_ms = 0.0
    status = "failed"
    error_message = ""
    # Initialise ctx to page so it is always defined in the finally block.
    ctx: ChatContext = page

    try:
        target_url = test_case.page_url or config.base_url
        open_homepage(page, target_url)
        dismiss_popups(page)
        open_chat_widget(page)
        ctx = resolve_chat_context(page)

        t_start = time.monotonic()
        submit_question(ctx, test_case.question)
        answer = wait_for_answer_completion(ctx, config)
        response_ms = (time.monotonic() - t_start) * 1000.0

        if answer:
            status = "success"
        else:
            status = "failed"
            error_message = "No answer text extracted."

    except Exception as exc:
        log.error("Error during run_single_question for case %s: %s", test_case.id, exc, exc_info=True)
        status = "failed"
        error_message = str(exc)

    finally:
        # Always attempt to capture screenshots.
        try:
            full_screenshot, chat_screenshot = capture_artifacts(page, ctx, test_case.id, config)
        except Exception as exc:
            log.warning("Artifact capture failed: %s", exc)

    log.info(
        "Case %s finished: status=%s, response_ms=%.0f",
        test_case.id,
        status,
        response_ms,
    )
    return answer, full_screenshot, chat_screenshot, response_ms, status, error_message
