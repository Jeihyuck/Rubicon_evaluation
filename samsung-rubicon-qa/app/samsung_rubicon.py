"""Samsung /sec/ Rubicon chatbot UI automation using Playwright."""

from __future__ import annotations

import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from playwright.sync_api import Frame, Locator, Page

from app.config import AppConfig
from app.dom_extractor import count_bot_messages, extract_dom_payload, extract_last_bot_message_text
from app.models import BrowserArtifacts, ExtractedPair, ResolvedChatContext, TestCase
from app.ocr_fallback import extract_text_from_image
from app.utils import (
    artifact_timestamp,
    build_locator,
    compile_regex,
    first_visible_locator,
    relative_to_root,
    sanitize_filename,
    utc_now_timestamp,
)


LAUNCHER_CANDIDATES = [
    {"type": "role", "role": "button", "name": compile_regex(r"AI|Chat|챗봇|상담|Assistant|Help|Rubicon|루비콘")},
    {"type": "label", "value": compile_regex(r"AI|Chat|챗봇|상담|Assistant|Help|Rubicon|루비콘")},
    {"type": "testid", "value": "chat-launcher"},
    {"type": "testid", "value": "assistant-launcher"},
    {"type": "text", "value": compile_regex(r"AI|Chat|챗봇|상담|Assistant|Help|Rubicon|루비콘")},
    {"type": "css", "value": "#spr-chat__trigger-button, .spr-chat__trigger-box button"},
    {"type": "css", "value": "button[aria-label*='chat' i], button[aria-label*='assistant' i], button[aria-label*='rubicon' i]"},
    {"type": "css", "value": "[data-testid*='chat'], [data-testid*='assistant'], [data-testid*='rubicon']"},
    {"type": "css", "value": "button[class*='chat'], button[class*='assistant'], button[class*='floating']"},
    {"type": "css", "value": "div[style*='position: fixed'] button, a[style*='position: fixed'], div[style*='bottom'] button"},
]

INPUT_CANDIDATES = [
    {"type": "role", "role": "textbox", "name": compile_regex(r"질문|문의|메시지|채팅|입력|message|chat")},
    {"type": "label", "value": compile_regex(r"질문|문의|메시지|채팅|입력|message|chat")},
    {"type": "placeholder", "value": compile_regex(r"질문|문의|메시지|무엇을 도와|message|ask")},
    {"type": "testid", "value": "chat-input"},
    {"type": "testid", "value": "message-input"},
    {"type": "css", "value": "textarea[placeholder*='메시지'], textarea[aria-label*='메시지'], textarea[placeholder*='message' i], textarea[aria-label*='message' i]"},
    {"type": "css", "value": "textarea, input[type='text'], [contenteditable='true']"},
]

SEND_BUTTON_CANDIDATES = [
    {"type": "role", "role": "button", "name": compile_regex(r"Send|전송|제출|문의|보내기")},
    {"type": "label", "value": compile_regex(r"Send|전송|제출|문의|보내기")},
    {"type": "testid", "value": "send-button"},
    {"type": "testid", "value": "message-send"},
    {"type": "css", "value": "button[aria-label*='send' i], button[aria-label*='전송'], button[aria-label*='보내기']"},
    {"type": "css", "value": "button[aria-label*='send' i], button[aria-label*='전송'], button[type='submit']"},
    {"type": "css", "value": "button[class*='send'], button[class*='submit'], button svg"},
]

BOT_MESSAGE_CANDIDATES = [
    {"type": "css", "value": ".bot-message, .agent-message, [data-message-author='bot'], [data-author='assistant'], [data-author='bot']"},
    {"type": "css", "value": "[class*='agent' i], [class*='assistant' i], [class*='message' i], [data-testid*='message' i]"},
    {"type": "css", "value": "[role='log'] article, [role='log'] li, [role='list'] article, [role='list'] li"},
    {"type": "css", "value": "article[class*='assistant'], div[class*='assistant'], div[class*='response'], div[class*='message']"},
    {"type": "text", "value": compile_regex(r"서비스센터|삼성닷컴|도와드리|안내드리")},
]

HISTORY_CANDIDATES = [
    {"type": "css", "value": "[role='log'] *"},
    {"type": "css", "value": "[role='list'] *"},
    {"type": "css", "value": "article, li, [data-message-author], [data-author]"},
]

CONTAINER_CANDIDATES = [
    {"type": "css", "value": "[role='dialog'], [role='complementary'], aside, section[class*='chat'], div[class*='chat'], div[class*='assistant']"},
    {"type": "css", "value": "[class*='spr' i], [id*='spr' i], [title*='Sprinklr' i], iframe[title*='live chat' i], iframe[title*='라이브챗']"},
    {"type": "css", "value": "iframe, form, [data-testid*='chat'], [data-testid*='assistant']"},
]

LOADING_CANDIDATES = [
    {"type": "css", "value": ".typing, .loading, .spinner, [aria-busy='true'], [class*='typing'], [class*='loading']"},
    {"type": "text", "value": compile_regex(r"입력 중|작성 중|typing|loading")},
]

POPUP_CLOSE_CANDIDATES = [
    {"type": "role", "role": "button", "name": compile_regex(r"닫기|Close|취소|오늘 그만 보기")},
    {"type": "text", "value": compile_regex(r"닫기|Close|오늘 그만 보기")},
    {"type": "css", "value": "button[aria-label*='close' i], button[aria-label*='닫기'], .close, .btn-close"},
]

POPUP_ACCEPT_CANDIDATES = [
    {"type": "role", "role": "button", "name": compile_regex(r"동의|확인|Accept|허용")},
    {"type": "text", "value": compile_regex(r"동의|확인|Accept|허용")},
]


@dataclass(slots=True)
class _RuntimeState:
    config: AppConfig
    logger: Any
    current_case_id: str = ""
    current_case_timestamp: str = ""
    current_page_url: str = ""
    latest_html_fragment_path: str = ""
    current_page: Page | None = None


_RUNTIME: _RuntimeState | None = None


def configure_runtime(config: AppConfig, logger: Any) -> None:
    """Bind config and logger for the required module-level functions."""

    global _RUNTIME
    _RUNTIME = _RuntimeState(config=config, logger=logger)


def _runtime() -> _RuntimeState:
    if _RUNTIME is None:
        raise RuntimeError("samsung_rubicon.configure_runtime() must be called before use")
    return _RUNTIME


def _current_page() -> Page:
    runtime = _runtime()
    if runtime.current_page is None:
        raise RuntimeError("Current page is not bound")
    return runtime.current_page


def _iter_scopes(page: Page) -> list[tuple[str, Page | Frame]]:
    scopes: list[tuple[str, Page | Frame]] = [("page", page)]
    prioritized_frames: list[tuple[int, str, Frame]] = []
    for index, frame in enumerate(page.frames):
        frame_name = frame.name or frame.url or f"frame-{index}"
        lowered = f"{frame.name} {frame.url}".lower()
        priority = 50
        # Proactive / trigger / session-storage frames do NOT hold the main chat input
        # and become detached once the main chat opens → exclude from input search
        if any(k in lowered for k in ("proactive", "trigger", "session-storage", "session_storage")):
            priority = 75
        elif "live-chat" in lowered or ("spr" in lowered and "live" in lowered):
            # The main Sprinklr live-chat frame has the real input
            priority = 5
        elif "spr" in lowered or "rubicon" in lowered or "chat" in lowered:
            priority = 20
        elif frame.name and "video" in frame.name.lower():
            priority = 100
        elif frame.url == "about:blank":
            priority = 80
        prioritized_frames.append((priority, frame_name, frame))

    prioritized_frames.sort(key=lambda item: (item[0], item[1]))
    scopes.extend((frame_name, frame) for _, frame_name, frame in prioritized_frames)
    return scopes


def _maybe_visible(scope: Page | Frame, candidate: dict[str, Any]) -> Locator | None:
    locator = build_locator(scope, candidate).first
    try:
        if locator.is_visible(timeout=1500):
            return locator
    except Exception:
        return None
    return None


def _sprinklr_launcher_present(page: Page) -> bool:
    try:
        return page.locator("#spr-chat__trigger-button, .spr-chat__trigger-box button, iframe[title='라이브챗']").count() > 0
    except Exception:
        return False


def _open_sprinklr_widget(page: Page) -> bool:
    runtime = _runtime()
    script = """
() => {
  const button = document.querySelector('#spr-chat__trigger-button, .spr-chat__trigger-box button');
  if (button) {
    button.click();
    return true;
  }
  return false;
}
"""

    try:
        if page.evaluate(script):
            page.wait_for_timeout(1500)
    except Exception:
        pass

    frame_selectors = ["iframe[title='라이브챗']", "iframe[title='Sprinklr live chat']"]
    for selector in frame_selectors:
        try:
            trigger = page.frame_locator(selector).locator("button, [role='button']").first
            if trigger.count() <= 0:
                continue
            trigger.click(timeout=3000)
            page.wait_for_timeout(1500)
            runtime.logger.info("rubicon icon clicked")
            return True
        except Exception:
            continue

    if _sprinklr_launcher_present(page):
        runtime.logger.info("rubicon icon clicked")
        return True
    return False


def open_homepage(page: Page) -> None:
    """Open the Samsung /sec/ homepage without entering any login flow."""

    runtime = _runtime()
    target_url = runtime.current_page_url or runtime.config.samsung_base_url
    if not target_url.startswith(runtime.config.samsung_base_url):
        target_url = runtime.config.samsung_base_url
    page.goto(target_url, wait_until="domcontentloaded")
    try:
        page.wait_for_load_state("networkidle", timeout=min(runtime.config.playwright_timeout_ms, 10000))
    except Exception:
        pass
    runtime.logger.info("homepage opened")


def _score_scope(scope: Page | Frame, scope_name: str) -> tuple[int, Locator | None, Locator | None, Locator | None]:
    input_locator, _ = first_visible_locator(scope, INPUT_CANDIDATES, timeout_ms=300)
    if input_locator is None:
        return -1, None, None, None

    # Only accept ENABLED (editable) inputs; disabled inputs (e.g. Sprinklr session-closed textarea) are worthless
    try:
        enabled = input_locator.is_enabled(timeout=500)
    except Exception:
        enabled = True  # assume enabled if check fails

    send_locator, _ = first_visible_locator(scope, SEND_BUTTON_CANDIDATES, timeout_ms=200)
    container_locator, _ = first_visible_locator(scope, CONTAINER_CANDIDATES, timeout_ms=200)
    bot_count = 0
    history_count = 0

    for candidate in BOT_MESSAGE_CANDIDATES:
        try:
            bot_count = max(bot_count, build_locator(scope, candidate).count())
        except Exception:
            continue

    for candidate in HISTORY_CANDIDATES:
        try:
            history_count = max(history_count, build_locator(scope, candidate).count())
        except Exception:
            continue

    score = 100
    if not enabled:
        # Disabled input → heavily penalize so it's only used as absolute last resort
        score -= 200
    if send_locator is not None:
        score += 15
    if container_locator is not None:
        score += 10
    score += min(bot_count, 5) * 5
    score += min(history_count, 5) * 2
    lowered_name = scope_name.lower()
    # Boost real live-chat frame; penalize transient proactive/trigger frames
    if "live-chat" in lowered_name or ("spr" in lowered_name and "live" in lowered_name):
        score += 30
    elif any(k in lowered_name for k in ("proactive", "trigger", "session-storage", "session_storage")):
        score -= 50
    elif "spr" in lowered_name or "rubicon" in lowered_name or "chat" in lowered_name:
        score += 15
    return score, input_locator, send_locator, container_locator


def dismiss_popups(page: Page) -> None:
    """Close blocking popups that could obscure the chatbot widget."""

    runtime = _runtime()
    dismissed = False
    for _ in range(3):
        for candidate_group in (POPUP_CLOSE_CANDIDATES, POPUP_ACCEPT_CANDIDATES):
            locator, _ = first_visible_locator(page, candidate_group, timeout_ms=250)
            if locator is None:
                continue
            try:
                locator.click(timeout=1000)
                dismissed = True
                page.wait_for_timeout(200)
            except Exception:
                continue
    if dismissed:
        runtime.logger.info("popups dismissed")
    else:
        runtime.logger.info("popups dismissed")


def open_rubicon_widget(page: Page) -> None:
    """Locate and click the floating Rubicon launcher if the chat is not already open."""

    runtime = _runtime()

    def _live_chat_input_visible() -> bool:
        """Return True only if the real live-chat frame has an input (not the proactive frame)."""
        for scope_name, scope in _iter_scopes(page):
            lowered = scope_name.lower()
            if any(k in lowered for k in ("proactive", "trigger", "session-storage", "session_storage")):
                continue
            input_locator, _ = first_visible_locator(scope, INPUT_CANDIDATES, timeout_ms=300)
            if input_locator is not None:
                return True
        return False

    if _live_chat_input_visible():
        runtime.logger.info("rubicon icon clicked")
        return

    if _open_sprinklr_widget(page):
        for _ in range(15):
            if _live_chat_input_visible():
                return
            page.wait_for_timeout(1000)

    for scope_name, scope in _iter_scopes(page):
        launcher, _ = first_visible_locator(scope, LAUNCHER_CANDIDATES, timeout_ms=300)
        if launcher is None:
            continue
        try:
            launcher.scroll_into_view_if_needed(timeout=1500)
            launcher.click(timeout=2000)
            runtime.logger.info("rubicon icon clicked")
            # Wait for the live-chat input to appear
            for _ in range(15):
                if _live_chat_input_visible():
                    return
                page.wait_for_timeout(1000)
            return
        except Exception:
            runtime.logger.debug("launcher click failed in scope %s", scope_name, exc_info=True)
            continue
    raise RuntimeError("Rubicon chatbot icon not found")


def resolve_chat_context(page: Page) -> ResolvedChatContext:
    """Resolve the active chat context from the page DOM or nested iframes."""

    runtime = _runtime()

    def _find_best() -> ResolvedChatContext | None:
        best_context: ResolvedChatContext | None = None
        best_score = -1
        for scope_name, scope in _iter_scopes(page):
            score, input_locator, send_locator, container_locator = _score_scope(scope, scope_name)
            if input_locator is None or score < best_score:
                continue
            best_score = score
            best_context = ResolvedChatContext(
                scope=scope,
                scope_name=scope_name,
                input_locator=input_locator,
                send_locator=send_locator,
                container_locator=container_locator,
                bot_message_candidates=BOT_MESSAGE_CANDIDATES,
                history_candidates=HISTORY_CANDIDATES,
                loading_candidates=LOADING_CANDIDATES,
            )
        return best_context

    # Try up to 30 seconds to find an enabled input  
    # (Sprinklr textarea starts disabled during initialization)
    best_context = None
    for wait_round in range(6):
        best_context = _find_best()
        if best_context is not None:
            try:
                enabled = best_context.input_locator.is_enabled(timeout=500)
            except Exception:
                enabled = True
            if enabled:
                break
            # Input found but disabled — wait for it to become editable
            runtime.logger.info(
                "chat input found but disabled (round %d/6) — waiting for editable state", wait_round + 1
            )
            try:
                best_context.input_locator.wait_for(state="editable", timeout=5000)
                break
            except Exception:
                pass
        page.wait_for_timeout(5000)

    if best_context is not None:
        runtime.logger.info("chat context resolved")
        return best_context
    raise RuntimeError("Chat iframe/input context could not be resolved")


def _resolve_chat_context_for_retry() -> ResolvedChatContext:
    return resolve_chat_context(_current_page())


def submit_question(context: ResolvedChatContext, question: str) -> dict[str, Any]:
    """
    Submit a question through the resolved chat input control.

    Verifies the input text via DOM before clicking send.
    Returns a dict with:
      - input_verified: bool
      - input_method_used: str ('fill' | 'press_sequentially' | 'keyboard' | 'js' | 'none')
      - before_send_screenshot_path: str (relative path, empty on failure)

    Raises RuntimeError if all input strategies fail (question not verified).
    """
    runtime = _runtime()
    page = _current_page()
    context.baseline_bot_count = count_bot_messages(context)
    context.baseline_last_answer = extract_last_bot_message_text(context)

    def _maybe_refresh() -> None:
        try:
            refreshed = _resolve_chat_context_for_retry()
            context.scope = refreshed.scope
            context.scope_name = refreshed.scope_name
            context.input_locator = refreshed.input_locator
            context.send_locator = refreshed.send_locator
            context.container_locator = refreshed.container_locator
        except Exception:
            pass

    # Enter question with DOM verification
    try:
        verified, method_used = _enter_question_with_verification(context, question)
    except Exception as exc:
        if "Frame was detached" in str(exc):
            _maybe_refresh()
            try:
                verified, method_used = _enter_question_with_verification(context, question)
            except Exception:
                verified, method_used = False, "none"
        else:
            runtime.logger.warning("[INPUT] unexpected error during input: %s", exc)
            verified, method_used = False, "none"

    # If first attempt failed (e.g. frame detached on proactive frame), re-resolve context and retry once
    if not verified:
        runtime.logger.info("[INPUT] first attempt failed — re-resolving chat context for retry")
        try:
            _maybe_refresh()
            verified, method_used = _enter_question_with_verification(context, question)
        except Exception:
            verified, method_used = False, "none"

    # Save before-send screenshots only if input was verified
    before_send_path = ""
    if verified:
        # Brief pause so typing is visible in the video
        try:
            page.wait_for_timeout(600)
        except Exception:
            pass
        before_send_path = _save_before_send_screenshots(page, context)
    else:
        runtime.logger.error("[INPUT] question input verification failed - aborting send")
        raise RuntimeError(
            f"Question input could not be verified in the chat input field "
            f"(question: {question[:60]!r})"
        )

    # Click send button
    runtime.logger.info("[INPUT] send clicked")
    if context.send_locator is not None:
        try:
            context.send_locator.click(timeout=2500)
            runtime.logger.info("question submitted")
            return {
                "input_verified": True,
                "input_method_used": method_used,
                "before_send_screenshot_path": before_send_path,
            }
        except Exception as exc:
            if "Frame was detached" in str(exc):
                _maybe_refresh()
                try:
                    context.send_locator.click(timeout=2500)
                    runtime.logger.info("question submitted")
                    return {
                        "input_verified": True,
                        "input_method_used": method_used,
                        "before_send_screenshot_path": before_send_path,
                    }
                except Exception:
                    pass

    # Fallback: Enter key
    try:
        context.input_locator.press("Enter")
    except Exception:
        pass
    runtime.logger.info("question submitted")
    return {
        "input_verified": True,
        "input_method_used": method_used,
        "before_send_screenshot_path": before_send_path,
    }


def _loading_visible(context: ResolvedChatContext) -> bool:
    for candidate in context.loading_candidates:
        locator = _maybe_visible(context.scope, candidate)
        if locator is not None:
            return True
    return False


def wait_for_answer_completion(context: ResolvedChatContext) -> tuple[str, int]:
    """Wait until the last bot answer becomes stable or timeout occurs."""

    runtime = _runtime()
    started = time.perf_counter()
    deadline = started + (runtime.config.playwright_timeout_ms / 1000.0)
    stable_checks = 0
    previous_text = ""
    latest_text = ""

    while time.perf_counter() < deadline:
        current_count = count_bot_messages(context)
        latest_text = extract_last_bot_message_text(context)
        has_new_answer = current_count > context.baseline_bot_count or latest_text != context.baseline_last_answer
        if latest_text and has_new_answer:
            if latest_text == previous_text:
                stable_checks += 1
            else:
                stable_checks = 1
                previous_text = latest_text
            if stable_checks >= runtime.config.answer_stable_checks and not _loading_visible(context):
                response_ms = int((time.perf_counter() - started) * 1000)
                runtime.logger.info("answer stabilized")
                return latest_text, response_ms

        if hasattr(context.scope, "wait_for_timeout"):
            context.scope.wait_for_timeout(int(runtime.config.answer_stable_interval_sec * 1000))
        else:
            time.sleep(runtime.config.answer_stable_interval_sec)

    runtime.logger.info("answer stabilized")
    return latest_text, int((time.perf_counter() - started) * 1000)


def capture_artifacts(page: Page, context: ResolvedChatContext | None, case_id: str) -> BrowserArtifacts:
    """Capture full-page and chatbox screenshots plus optional DOM fragment."""

    runtime = _runtime()
    timestamp = runtime.current_case_timestamp or artifact_timestamp()
    safe_case_id = sanitize_filename(case_id)
    fullpage_path = runtime.config.fullpage_dir / f"{timestamp}_{safe_case_id}.png"
    chatbox_path = runtime.config.chatbox_dir / f"{timestamp}_{safe_case_id}.png"
    html_fragment_path = runtime.config.chatbox_dir / f"{timestamp}_{safe_case_id}.html"

    try:
        page.screenshot(path=str(fullpage_path), full_page=True)
    except Exception as exc:
        runtime.logger.exception("Failed to capture full page screenshot: %s", exc)
        fullpage_path = None

    try:
        if context is not None and context.container_locator is not None:
            context.container_locator.screenshot(path=str(chatbox_path))
        elif context is not None:
            context.input_locator.screenshot(path=str(chatbox_path))
        else:
            page.screenshot(path=str(chatbox_path))
    except Exception as exc:
        runtime.logger.exception("Failed to capture chat screenshot: %s", exc)
        chatbox_path = None

    if context is not None:
        dom_payload = extract_dom_payload(context, html_fragment_path)
        runtime.latest_html_fragment_path = dom_payload.get("html_fragment_path", "")
        html_fragment_path = Path(runtime.latest_html_fragment_path) if runtime.latest_html_fragment_path else None
    else:
        html_fragment_path = None

    runtime.logger.info("artifacts saved")
    return BrowserArtifacts(
        fullpage_screenshot=fullpage_path,
        chatbox_screenshot=chatbox_path,
        html_fragment_path=html_fragment_path,
    )


def capture_chat_state(page: Page, context: ResolvedChatContext | None, case_id: str, label: str) -> str:
    runtime = _runtime()
    timestamp = runtime.current_case_timestamp or artifact_timestamp()
    safe_case_id = sanitize_filename(case_id)
    chatbox_path = runtime.config.chatbox_dir / f"{timestamp}_{safe_case_id}_{label}.png"

    try:
        if context is None:
            page.screenshot(path=str(chatbox_path))
        else:
            try:
                refreshed = _resolve_chat_context_for_retry()
                context.scope = refreshed.scope
                context.scope_name = refreshed.scope_name
                context.input_locator = refreshed.input_locator
                context.send_locator = refreshed.send_locator
                context.container_locator = refreshed.container_locator
            except Exception:
                pass

            if context.container_locator is not None:
                context.container_locator.screenshot(path=str(chatbox_path))
            else:
                context.input_locator.screenshot(path=str(chatbox_path))
        return relative_to_root(chatbox_path, runtime.config.project_root)
    except Exception as exc:
        runtime.logger.exception("Failed to capture %s chat screenshot: %s", label, exc)
        return ""


# ---------------------------------------------------------------------------
# Input entry helpers
# ---------------------------------------------------------------------------

def _detect_input_type(locator: Locator) -> str:
    """Return 'input', 'textarea', or 'contenteditable' based on the DOM element."""
    try:
        tag = locator.evaluate("el => el.tagName.toLowerCase()")
        if tag == "textarea":
            return "textarea"
        if tag == "input":
            return "input"
        ce = locator.evaluate("el => el.getAttribute('contenteditable')")
        if ce is not None:
            return "contenteditable"
    except Exception:
        pass
    return "input"


def _focus_input(locator: Locator) -> bool:
    """Scroll into view, click, and verify focus. Returns True on success."""
    runtime = _runtime()
    try:
        # Wait for element to become editable before attempting interaction
        try:
            locator.wait_for(state="editable", timeout=3000)
        except Exception:
            pass
        locator.scroll_into_view_if_needed(timeout=2000)
        locator.click(timeout=2000)
        try:
            locator.wait_for(state="visible", timeout=1500)
        except Exception:
            pass
        runtime.logger.info("[INPUT] focus success")
        return True
    except Exception:
        try:
            locator.click(timeout=1500)
            runtime.logger.info("[INPUT] focus success (fallback click)")
            return True
        except Exception:
            runtime.logger.warning("[INPUT] focus fail")
            return False


def _clear_input(locator: Locator, input_type: str) -> None:
    """Remove any existing text from the input element."""
    try:
        if input_type in ("input", "textarea"):
            try:
                locator.fill("", timeout=1500)
            except Exception:
                pass
        else:
            try:
                locator.evaluate("el => { el.textContent = ''; }")
            except Exception:
                pass
        try:
            locator.press("Control+A")
            locator.press("Backspace")
        except Exception:
            pass
    except Exception:
        pass


def _verify_input_text(locator: Locator, question: str, input_type: str) -> bool:
    """Verify the exact text was entered. Returns True when the input matches the question."""
    runtime = _runtime()
    normalized_question = " ".join(question.split())
    try:
        if input_type in ("input", "textarea"):
            actual = locator.input_value(timeout=2000)
            normalized_actual = " ".join(actual.split())
            ok = normalized_actual == normalized_question
        else:
            actual = locator.inner_text(timeout=2000)
            if not actual:
                actual = locator.text_content(timeout=2000) or ""
            normalized_actual = " ".join(actual.split())
            ok = normalized_question in normalized_actual
        if ok:
            runtime.logger.info('[INPUT] verification success: "%s"', question)
        else:
            runtime.logger.warning('[INPUT] verification failed: expected "%s", got "%s"', question, actual[:80])
        return ok
    except Exception as exc:
        runtime.logger.warning("[INPUT] verification error: %s", exc)
        return False


def _try_fill(locator: Locator, question: str, input_type: str) -> bool:
    """Strategy 1: locator.fill(). Returns True if verification passes."""
    runtime = _runtime()
    try:
        locator.fill(question, timeout=2500)
        result = _verify_input_text(locator, question, input_type)
        if result:
            runtime.logger.info("[INPUT] fill attempt success")
        else:
            runtime.logger.warning("[INPUT] fill failed: empty or mismatched after fill")
        return result
    except Exception as exc:
        runtime.logger.warning("[INPUT] fill attempt failed: %s", exc)
        return False


def _try_press_sequentially(locator: Locator, question: str, input_type: str) -> bool:
    """Strategy 2: press_sequentially (visible character-by-character). Returns True if verification passes."""
    runtime = _runtime()
    try:
        locator.press_sequentially(question, delay=40)
        try:
            _current_page().wait_for_timeout(400)
        except Exception:
            pass
        result = _verify_input_text(locator, question, input_type)
        if result:
            runtime.logger.info("[INPUT] press_sequentially attempt success")
        else:
            runtime.logger.warning("[INPUT] press_sequentially failed: mismatch after sequential input")
        return result
    except Exception as exc:
        runtime.logger.warning("[INPUT] press_sequentially attempt failed: %s", exc)
        return False


def _try_keyboard_type(locator: Locator, question: str, input_type: str) -> bool:
    """Strategy 3: click then page.keyboard.type(). Returns True if verification passes."""
    runtime = _runtime()
    try:
        page = _current_page()
        locator.click(timeout=1500)
        page.keyboard.type(question, delay=30)
        page.wait_for_timeout(400)
        result = _verify_input_text(locator, question, input_type)
        if result:
            runtime.logger.info("[INPUT] keyboard.type attempt success")
        else:
            runtime.logger.warning("[INPUT] keyboard.type failed: mismatch after type")
        return result
    except Exception as exc:
        runtime.logger.warning("[INPUT] keyboard.type attempt failed: %s", exc)
        return False


def _try_js_fallback(locator: Locator, question: str, input_type: str) -> bool:
    """Strategy 4 (last resort): set value via JavaScript and dispatch events. Returns True if verification passes."""
    runtime = _runtime()
    runtime.logger.warning("[INPUT] JS fallback used")
    try:
        page = _current_page()
        locator.evaluate(
            """(el, value) => {
                if (el.tagName === 'INPUT' || el.tagName === 'TEXTAREA') {
                    var nativeInputValueSetter = Object.getOwnPropertyDescriptor(
                        window.HTMLInputElement.prototype, 'value') ||
                        Object.getOwnPropertyDescriptor(window.HTMLTextAreaElement.prototype, 'value');
                    if (nativeInputValueSetter) {
                        nativeInputValueSetter.set.call(el, value);
                    } else {
                        el.value = value;
                    }
                    el.dispatchEvent(new Event('input', { bubbles: true }));
                    el.dispatchEvent(new Event('change', { bubbles: true }));
                } else {
                    el.textContent = value;
                    el.dispatchEvent(new InputEvent('input', { bubbles: true }));
                    el.dispatchEvent(new Event('change', { bubbles: true }));
                }
            }""",
            question,
        )
        page.wait_for_timeout(300)
        result = _verify_input_text(locator, question, input_type)
        if result:
            runtime.logger.info("[INPUT] JS fallback success")
        else:
            runtime.logger.warning("[INPUT] JS fallback: verification still failed")
        return result
    except Exception as exc:
        runtime.logger.warning("[INPUT] JS fallback failed: %s", exc)
        return False


def _enter_question_with_verification(context: ResolvedChatContext, question: str) -> tuple[bool, str]:
    """
    Try entering the question using multiple strategies in priority order.
    Returns (input_verified: bool, method_used: str).
    """
    runtime = _runtime()
    locator = context.input_locator

    input_type = _detect_input_type(locator)
    runtime.logger.info("[INPUT] locator found via scope: %s", context.scope_name)
    runtime.logger.info("[INPUT] detected type: %s", input_type)

    _focus_input(locator)

    # Strategy 1: fill
    _clear_input(locator, input_type)
    if _try_fill(locator, question, input_type):
        return True, "fill"

    # Strategy 2: press_sequentially
    _clear_input(locator, input_type)
    if _try_press_sequentially(locator, question, input_type):
        return True, "press_sequentially"

    # Strategy 3: keyboard.type
    _clear_input(locator, input_type)
    if _try_keyboard_type(locator, question, input_type):
        return True, "keyboard"

    # Strategy 4: JS fallback (last resort)
    _clear_input(locator, input_type)
    if _try_js_fallback(locator, question, input_type):
        return True, "js"

    runtime.logger.error("[INPUT] all input strategies failed for question: %s", question[:40])
    return False, "none"


def _save_before_send_screenshots(page: Page, context: ResolvedChatContext | None) -> str:
    """
    Save fullpage and chatbox screenshots immediately after input, before clicking send.
    Returns the relative chatbox screenshot path.
    """
    runtime = _runtime()
    timestamp = runtime.current_case_timestamp or artifact_timestamp()
    safe_case_id = sanitize_filename(runtime.current_case_id or "case")
    chatbox_path = runtime.config.chatbox_dir / f"{timestamp}_{safe_case_id}_before_send.png"
    fullpage_path = runtime.config.fullpage_dir / f"{timestamp}_{safe_case_id}_before_send.png"

    try:
        page.screenshot(path=str(fullpage_path), full_page=True)
    except Exception as exc:
        runtime.logger.warning("[ARTIFACT] fullpage before-send screenshot failed: %s", exc)

    try:
        if context is not None and context.container_locator is not None:
            context.container_locator.screenshot(path=str(chatbox_path))
        elif context is not None:
            context.input_locator.screenshot(path=str(chatbox_path))
        else:
            page.screenshot(path=str(chatbox_path))
        rel = relative_to_root(chatbox_path, runtime.config.project_root)
        runtime.logger.info("[ARTIFACT] before-send screenshot saved: %s", rel)
        return rel
    except Exception as exc:
        runtime.logger.warning("[ARTIFACT] chatbox before-send screenshot failed: %s", exc)
        return ""


def _inject_korean_font_css(page: Page) -> None:
    """Inject Korean font fallback CSS to prevent Hangul rendering issues."""
    runtime = _runtime()
    font_css = (
        "* { font-family: 'Noto Sans KR', 'Noto Sans CJK KR', 'Nanum Gothic',"
        " 'Apple SD Gothic Neo', sans-serif !important; }"
    )
    try:
        page.add_style_tag(content=font_css)
        runtime.logger.info("[FONT] Korean font CSS injected into main page")
    except Exception as exc:
        runtime.logger.warning("[FONT] main page font CSS injection failed: %s", exc)

    # Also try to inject into known chat frames
    try:
        for frame in page.frames:
            url = frame.url or ""
            name = frame.name or ""
            lowered = f"{name} {url}".lower()
            if any(k in lowered for k in ("spr", "chat", "rubicon", "live")):
                try:
                    frame.add_style_tag(content=font_css)
                    runtime.logger.info("[FONT] Korean font CSS injected into frame: %s", name or url[:60])
                except Exception:
                    pass
    except Exception:
        pass


# ---------------------------------------------------------------------------


def _question_echo_from_history(question: str, history: list[str]) -> str:
    normalized_question = " ".join(question.split())
    for item in history:
        if normalized_question and normalized_question in item:
            return item
    return ""


def run_single_case(page: Page, test_case: TestCase) -> ExtractedPair:
    """Execute one public, non-login Rubicon chatbot scenario end-to-end."""

    runtime = _runtime()
    runtime.current_case_id = test_case.id
    runtime.current_case_timestamp = artifact_timestamp()
    runtime.current_page_url = test_case.page_url or runtime.config.samsung_base_url
    runtime.latest_html_fragment_path = ""
    runtime.current_page = page

    context: ResolvedChatContext | None = None
    artifacts = BrowserArtifacts()
    answer = ""
    question_echo = ""
    message_history: list[str] = []
    extraction_source = "unknown"
    extraction_confidence = 0.0
    response_ms = 0
    status = "passed"
    error_message = ""
    submitted_chat_screenshot_path = ""
    answered_chat_screenshot_path = ""
    input_verified = False
    input_method_used = ""
    before_send_screenshot_path = ""
    font_fix_applied = False

    try:
        open_homepage(page)

        # Inject Korean font CSS immediately after page load
        _inject_korean_font_css(page)
        font_fix_applied = True

        dismiss_popups(page)
        open_rubicon_widget(page)

        # Re-inject into any chat frames that appeared after widget open
        _inject_korean_font_css(page)

        context = resolve_chat_context(page)

        # Stage 1 artifact: chat widget is open
        capture_chat_state(page, context, test_case.id, "opened")

        submit_info = submit_question(context, test_case.question)
        input_verified = submit_info.get("input_verified", False)
        input_method_used = submit_info.get("input_method_used", "")
        before_send_screenshot_path = submit_info.get("before_send_screenshot_path", "")

        # Stage 2 artifact: before send (already saved inside submit_question)
        submitted_chat_screenshot_path = capture_chat_state(page, context, test_case.id, "submitted")

        answer, response_ms = wait_for_answer_completion(context)

        # Stage 3 artifact: after answer
        answered_chat_screenshot_path = capture_chat_state(page, context, test_case.id, "answered")
        artifacts = capture_artifacts(page, context, test_case.id)

        dom_payload = extract_dom_payload(context, artifacts.html_fragment_path)
        message_history = dom_payload.get("history", [])
        question_echo = _question_echo_from_history(test_case.question, message_history)
        if dom_payload["success"]:
            answer = dom_payload["answer"]
            extraction_source = "dom"
            extraction_confidence = 1.0
            runtime.logger.info("DOM extracted")
        elif runtime.config.enable_ocr_fallback and artifacts.chatbox_screenshot is not None:
            ocr_text, confidence = extract_text_from_image(artifacts.chatbox_screenshot, runtime.logger)
            if ocr_text:
                answer = ocr_text
                extraction_source = "ocr"
                extraction_confidence = confidence
                runtime.logger.info("OCR fallback used")

        if not answer:
            raise RuntimeError("No answer text could be extracted from DOM or OCR")
    except Exception as exc:
        status = "failed"
        error_message = str(exc)
        runtime.logger.exception("exception details: %s", exc)
        try:
            if artifacts.fullpage_screenshot is None and artifacts.chatbox_screenshot is None:
                artifacts = capture_artifacts(page, context, test_case.id)
        except Exception:
            pass

    return ExtractedPair(
        run_timestamp=utc_now_timestamp(),
        case_id=test_case.id,
        category=test_case.category,
        page_url=test_case.page_url,
        locale=test_case.locale,
        question=test_case.question,
        answer=answer,
        extraction_source=extraction_source,
        extraction_confidence=extraction_confidence,
        response_ms=response_ms,
        status=status,
        error_message=error_message,
        question_echo=question_echo,
        message_history=message_history,
        full_screenshot_path=relative_to_root(artifacts.fullpage_screenshot, runtime.config.project_root),
        chat_screenshot_path=relative_to_root(artifacts.chatbox_screenshot, runtime.config.project_root),
        submitted_chat_screenshot_path=submitted_chat_screenshot_path,
        answered_chat_screenshot_path=answered_chat_screenshot_path,
        before_send_screenshot_path=before_send_screenshot_path,
        input_verified=input_verified,
        input_method_used=input_method_used,
        font_fix_applied=font_fix_applied,
        video_path="",
        trace_path="",
        html_fragment_path=relative_to_root(
            artifacts.html_fragment_path or (Path(runtime.latest_html_fragment_path) if runtime.latest_html_fragment_path else None),
            runtime.config.project_root,
        ),
    )
