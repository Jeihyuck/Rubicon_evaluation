"""Samsung /sec/ Rubicon chatbot UI automation using Playwright."""

from __future__ import annotations

import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from playwright.sync_api import Frame, Locator, Page

from app.config import AppConfig
from app.dom_extractor import (
    count_bot_messages,
    extract_bot_message_texts,
    extract_dom_payload,
    extract_message_history_candidates,
    extract_visible_chat_text,
)
from app.models import BrowserArtifacts, ExtractedPair, ResolvedChatContext, TestCase
from app.ocr_fallback import extract_text_from_image
from app.utils import artifact_timestamp, build_locator, compile_regex, first_visible_locator, sanitize_filename, utc_now_timestamp


LAUNCHER_CANDIDATES = [
    {"type": "role", "role": "button", "name": compile_regex(r"AI|Chat|챗봇|상담|Assistant|Help|Rubicon|루비콘")},
    {"type": "label", "value": compile_regex(r"AI|Chat|챗봇|상담|Assistant|Help|Rubicon|루비콘")},
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
    {"type": "css", "value": "textarea[placeholder*='메시지'], textarea[aria-label*='메시지'], textarea[placeholder*='message' i], textarea[aria-label*='message' i]"},
    {"type": "css", "value": "textarea, input[type='text'], [contenteditable='true']"},
]

SEND_BUTTON_CANDIDATES = [
    {"type": "role", "role": "button", "name": compile_regex(r"Send|전송|제출|문의|보내기")},
    {"type": "label", "value": compile_regex(r"Send|전송|제출|문의|보내기")},
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

USER_MESSAGE_CANDIDATES = [
    {"type": "css", "value": ".user-message, [data-message-author='user'], [data-author='user'], [data-author='customer']"},
    {"type": "css", "value": "[class*='user' i][class*='message' i], [class*='customer' i][class*='message' i]"},
    {"type": "css", "value": "[class*='outgoing' i], [class*='sent' i], [class*='right' i][class*='message' i]"},
    {"type": "css", "value": "[role='log'] [data-message-author='user'], [role='list'] [data-message-author='user']"},
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

KOREAN_FONT_CSS = (
    '* { font-family: "Noto Sans KR", "Noto Sans CJK KR", "Nanum Gothic",'
    ' "Apple SD Gothic Neo", sans-serif !important; }'
)

# Delay (ms / s) after submit to let the UI render the user-message bubble
ECHO_RENDER_DELAY_MS = 600
ECHO_RENDER_DELAY_SEC = ECHO_RENDER_DELAY_MS / 1000.0

BASELINE_MENU_TEXTS = [
    "아래에서 원하는 항목을 선택해 주세요",
    "구매 상담사 연결",
    "주문·배송 조회",
    "모바일 케어플러스",
    "가전 케어플러스",
    "서비스 센터",
    "FAQ",
]


@dataclass(slots=True)
class SubmissionEvidence:
    input_dom_verified: bool
    submit_effect_verified: bool
    input_verified: bool
    input_method_used: str
    submit_method_used: str
    before_send_chatbox_path: str
    before_send_fullpage_path: str
    after_send_chatbox_path: str
    after_send_fullpage_path: str
    user_message_echo_verified: bool
    capture_reason: str


@dataclass(slots=True)
class AnswerWaitResult:
    answer: str
    response_ms: int
    new_bot_response_detected: bool
    baseline_menu_detected: bool
    reason: str


@dataclass(slots=True)
class _RuntimeState:
    config: AppConfig
    logger: Any
    current_case_id: str = ""
    current_case_timestamp: str = ""
    latest_html_fragment_path: str = ""


_RUNTIME: _RuntimeState | None = None


def configure_runtime(config: AppConfig, logger: Any) -> None:
    """Bind config and logger for the required module-level functions."""

    global _RUNTIME
    _RUNTIME = _RuntimeState(config=config, logger=logger)


def _runtime() -> _RuntimeState:
    if _RUNTIME is None:
        raise RuntimeError("samsung_rubicon.configure_runtime() must be called before use")
    return _RUNTIME


def _iter_scopes(page: Page) -> list[tuple[str, Page | Frame]]:
    scopes: list[tuple[str, Page | Frame]] = [("page", page)]
    for index, frame in enumerate(page.frames):
        frame_name = frame.name or frame.url or f"frame-{index}"
        scopes.append((frame_name, frame))
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


def inject_korean_font(page: Page) -> bool:
    """Inject Korean font fallback CSS into the page and all loaded frames.

    Returns True when the style tag was injected successfully.
    """

    runtime = _runtime()
    success = False
    try:
        page.add_style_tag(content=KOREAN_FONT_CSS)
        success = True
        runtime.logger.info("[FONT] Korean font fallback injected into main page")
    except Exception as exc:
        runtime.logger.warning("[FONT] font injection failed on main page: %s", exc)

    for frame in page.frames:
        try:
            frame.add_style_tag(content=KOREAN_FONT_CSS)
        except Exception:
            pass

    return success


def open_homepage(page: Page) -> None:
    """Open the Samsung /sec/ homepage without entering any login flow."""

    runtime = _runtime()
    page.goto(runtime.config.samsung_base_url, wait_until="domcontentloaded")
    try:
        page.wait_for_load_state("networkidle", timeout=min(runtime.config.playwright_timeout_ms, 10000))
    except Exception:
        pass
    runtime.logger.info("homepage opened")


def dismiss_popups(page: Page) -> None:
    """Close blocking popups that could obscure the chatbot widget."""

    runtime = _runtime()
    dismissed = False
    for _ in range(3):
        for scopes in _iter_scopes(page):
            _, scope = scopes
            for candidate_group in (POPUP_CLOSE_CANDIDATES, POPUP_ACCEPT_CANDIDATES):
                locator, _ = first_visible_locator(scope, candidate_group, timeout_ms=1200)
                if locator is None:
                    continue
                try:
                    locator.click(timeout=1500)
                    dismissed = True
                    page.wait_for_timeout(250)
                except Exception:
                    continue
    if dismissed:
        runtime.logger.info("popups dismissed")
    else:
        runtime.logger.info("popups dismissed")


def open_rubicon_widget(page: Page) -> None:
    """Locate and click the floating Rubicon launcher if the chat is not already open."""

    runtime = _runtime()
    for scope_name, scope in _iter_scopes(page):
        input_locator, _ = first_visible_locator(scope, INPUT_CANDIDATES, timeout_ms=1200)
        if input_locator is not None:
            runtime.logger.info("rubicon icon clicked")
            return

    if _open_sprinklr_widget(page):
        for _ in range(10):
            for _, scope in _iter_scopes(page):
                input_locator, _ = first_visible_locator(scope, INPUT_CANDIDATES, timeout_ms=600)
                if input_locator is not None:
                    return
            page.wait_for_timeout(1000)

    for scope_name, scope in _iter_scopes(page):
        launcher, _ = first_visible_locator(scope, LAUNCHER_CANDIDATES, timeout_ms=1500)
        if launcher is None:
            continue
        try:
            launcher.scroll_into_view_if_needed(timeout=1500)
            launcher.click(timeout=2000)
            runtime.logger.info("rubicon icon clicked")
            return
        except Exception:
            runtime.logger.debug("launcher click failed in scope %s", scope_name, exc_info=True)
            continue
    raise RuntimeError("Rubicon chatbot icon not found")


def resolve_chat_context(page: Page) -> ResolvedChatContext:
    """Resolve the active chat context from the page DOM or nested iframes."""

    runtime = _runtime()
    for scope_name, scope in _iter_scopes(page):
        input_locator, _ = first_visible_locator(scope, INPUT_CANDIDATES, timeout_ms=1800)
        if input_locator is None:
            continue
        send_locator, _ = first_visible_locator(scope, SEND_BUTTON_CANDIDATES, timeout_ms=900)
        container_locator, _ = first_visible_locator(scope, CONTAINER_CANDIDATES, timeout_ms=900)
        context = ResolvedChatContext(
            scope=scope,
            scope_name=scope_name,
            input_locator=input_locator,
            send_locator=send_locator,
            container_locator=container_locator,
            bot_message_candidates=BOT_MESSAGE_CANDIDATES,
            history_candidates=HISTORY_CANDIDATES,
            loading_candidates=LOADING_CANDIDATES,
        )
        runtime.logger.info("chat context resolved")
        return context
    raise RuntimeError("Chat iframe/input context could not be resolved")


# ---------------------------------------------------------------------------
# Input verification helpers
# ---------------------------------------------------------------------------

def _detect_input_type(locator: Locator) -> str:
    """Detect whether the locator targets an input, textarea, or contenteditable."""

    try:
        tag = locator.evaluate("el => el.tagName.toLowerCase()")
        if tag in ("input", "textarea"):
            return tag
        ce = locator.evaluate("el => el.contentEditable")
        if ce and ce not in ("inherit", "false"):
            return "contenteditable"
    except Exception:
        pass
    return "input"


def detect_input_kind(locator: Locator) -> str:
    """Return the resolved kind of chat input element."""

    return _detect_input_type(locator)


def _focus_input(locator: Locator, logger: Any) -> bool:
    """Click the input to give it focus; return True on success."""

    try:
        locator.scroll_into_view_if_needed(timeout=1500)
        locator.click(timeout=2000)
        logger.info("[INPUT] focus success")
        return True
    except Exception as exc:
        logger.warning("[INPUT] focus fail: %s", exc)
        return False


def focus_input(locator: Locator) -> bool:
    """Focus the chat input using the configured runtime logger."""

    return _focus_input(locator, _runtime().logger)


def _clear_input(locator: Locator, input_type: str) -> None:
    """Remove any existing text from the input element."""

    try:
        if input_type in ("input", "textarea"):
            locator.fill("", timeout=1500)
        else:
            locator.press("Control+A")
            locator.press("Backspace")
    except Exception:
        try:
            locator.press("Control+A")
            locator.press("Backspace")
        except Exception:
            pass


def clear_input(locator: Locator) -> None:
    """Clear the chat input using the detected input type."""

    _clear_input(locator, detect_input_kind(locator))


def verify_input_text(locator: Locator, question: str, input_type: str) -> bool:
    """Return True when the question text is confirmed present in the input element."""

    try:
        if input_type in ("input", "textarea"):
            value = locator.input_value(timeout=1500)
            return value.strip() == question.strip()
        else:
            text = locator.inner_text(timeout=1500) or locator.text_content(timeout=1500) or ""
            return question.strip() in text.strip()
    except Exception:
        return False


def _read_input_value(locator: Locator, input_type: str) -> str:
    try:
        if input_type in ("input", "textarea"):
            return locator.input_value(timeout=1500).strip()
        return (locator.inner_text(timeout=1500) or locator.text_content(timeout=1500) or "").strip()
    except Exception:
        return ""


def verify_input_dom_state(locator: Locator, question: str) -> bool:
    """Verify that the DOM input element reflects the question text."""

    logger = _runtime().logger
    input_type = detect_input_kind(locator)
    verified = verify_input_text(locator, question, input_type)
    logger.info("[INPUT] DOM input verification %s", "success" if verified else "fail")
    return verified


def _is_send_button_enabled(locator: Locator | None) -> bool | None:
    if locator is None:
        return None
    try:
        return locator.is_enabled()
    except Exception:
        return None


def is_initial_menu_text(text: str) -> bool:
    """Return True if the text matches an initial menu or baseline CTA."""

    return _contains_baseline_menu(text)


def _normalize_text(value: str) -> str:
    return " ".join(value.split())


def _contains_baseline_menu(text: str) -> bool:
    normalized = _normalize_text(text)
    return any(menu_text in normalized for menu_text in BASELINE_MENU_TEXTS)


def capture_baseline_bot_snapshot(context: ResolvedChatContext) -> list[str]:
    """Capture the baseline bot text snapshot before a question is submitted."""

    baseline_messages = extract_bot_message_texts(context)
    context.baseline_bot_messages = baseline_messages
    context.baseline_bot_count = len(baseline_messages)
    _runtime().logger.info("[ANSWER] baseline bot count: %s", context.baseline_bot_count)
    _runtime().logger.info("[ANSWER] baseline bot texts count: %s", len(context.baseline_bot_messages))
    return baseline_messages


def detect_new_bot_text(context: ResolvedChatContext, baseline_texts: list[str]) -> str:
    """Detect newly appeared bot text that was not present in the baseline snapshot."""

    baseline_normalized = {_normalize_text(item) for item in baseline_texts}
    for message in extract_bot_message_texts(context):
        normalized = _normalize_text(message)
        if not normalized:
            continue
        if normalized in baseline_normalized:
            continue
        if is_initial_menu_text(normalized):
            continue
        return message
    return ""


def _is_new_response_candidate(text: str, baseline_messages: list[str]) -> bool:
    normalized = _normalize_text(text)
    if not normalized:
        return False
    if _contains_baseline_menu(normalized):
        return False
    if normalized in {_normalize_text(item) for item in baseline_messages}:
        return False
    return True


def verify_user_message_echo(context: ResolvedChatContext, question: str, logger: Any) -> bool:
    """Return True if the submitted question appears as a user message bubble.

    After the question is sent, the chat should echo it back as a user-side
    message element.  This check tries specific user-message selectors first,
    then falls back to searching all chat history nodes for the question text,
    and finally does a full JavaScript text-scan of the entire scope so that
    Sprinklr-specific class names or shadow DOM structures are not a blocker.
    The check is best-effort: a ``False`` result is logged but does not by
    itself fail the case (it contributes to the overall verification signal).
    """

    scope = context.scope
    question_norm = " ".join(question.strip().split())

    # 1. Try dedicated user-message CSS selectors
    for candidate in USER_MESSAGE_CANDIDATES:
        try:
            locator = build_locator(scope, candidate)
            if locator is None:
                continue
            count = locator.count()
            for i in range(count):
                try:
                    text = locator.nth(i).inner_text(timeout=1000).strip()
                    if question_norm in " ".join(text.split()):
                        logger.info("[ECHO] user message echo confirmed via user-message selector")
                        return True
                except Exception:
                    continue
        except Exception:
            continue

    # 2. Fallback: scan structured history candidates for the question text
    for text in extract_message_history_candidates(context):
        if question_norm in " ".join(text.split()):
            logger.info("[ECHO] user message echo confirmed via history scan")
            logger.info("[SUBMIT] user echo detected: True")
            return True

    # 3. Last resort: JavaScript full-text scan of the entire scope.
    #    This catches Sprinklr widget structures that use opaque class names or
    #    shadow DOM — the text of every visible element is searched for the
    #    question string without requiring specific CSS selectors.
    visible_text = extract_visible_chat_text(context)
    if visible_text and question_norm in " ".join(str(visible_text).split()):
        logger.info("[ECHO] user message echo confirmed via visible chat text scan")
        logger.info("[SUBMIT] user echo detected: True")
        return True

    try:
        js = (
            "() => {"
            "  const el = document.body || document.documentElement;"
            "  return el ? (el.innerText || el.textContent || '') : '';"
            "}"
        )
        full_text = scope.evaluate(js)
        if full_text and question_norm in " ".join(str(full_text).split()):
            logger.info("[ECHO] user message echo confirmed via JS full-scope text scan")
            logger.info("[SUBMIT] user echo detected: True")
            return True
    except Exception as exc:
        logger.debug("[ECHO] JS text scan failed: %s", exc)

    logger.warning("[ECHO] user message echo not found in chat DOM (best-effort)")
    logger.info("[SUBMIT] user echo detected: False")
    return False


def find_chat_container(page: Page) -> Locator | None:
    """Find the visible chat container in the page or in a nested iframe."""

    for _, scope in _iter_scopes(page):
        container_locator, _ = first_visible_locator(scope, CONTAINER_CANDIDATES, timeout_ms=1500)
        if container_locator is not None:
            return container_locator
    return None


def find_input_locator(context: Page | Frame | ResolvedChatContext) -> Locator | None:
    """Find the visible input locator from a page, frame, or resolved chat context."""

    if isinstance(context, ResolvedChatContext):
        return context.input_locator
    input_locator, _ = first_visible_locator(context, INPUT_CANDIDATES, timeout_ms=1500)
    return input_locator


def find_send_button(context: Page | Frame | ResolvedChatContext) -> Locator | None:
    """Find the send button from a page, frame, or resolved chat context."""

    if isinstance(context, ResolvedChatContext):
        return context.send_locator
    send_locator, _ = first_visible_locator(context, SEND_BUTTON_CANDIDATES, timeout_ms=1200)
    return send_locator


def _try_fill(locator: Locator, question: str, input_type: str, logger: Any) -> bool:
    try:
        locator.fill(question, timeout=2500)
        if verify_input_text(locator, question, input_type):
            logger.info("[INPUT] fill attempt success")
            return True
        logger.warning("[INPUT] fill failed: empty or mismatched after fill")
        return False
    except Exception as exc:
        logger.warning("[INPUT] fill attempt failed: %s", exc)
        return False


def _try_press_sequentially(locator: Locator, question: str, input_type: str, logger: Any) -> bool:
    try:
        locator.press_sequentially(question, delay=30)
        if verify_input_text(locator, question, input_type):
            logger.info("[INPUT] press_sequentially success")
            return True
        logger.warning("[INPUT] press_sequentially failed: verification failed")
        return False
    except Exception as exc:
        logger.warning("[INPUT] press_sequentially attempt failed: %s", exc)
        return False


def _try_keyboard_type(
    scope: Page | Frame,
    locator: Locator,
    question: str,
    input_type: str,
    logger: Any,
) -> bool:
    try:
        locator.click(timeout=1500)
        if hasattr(scope, "keyboard"):
            scope.keyboard.type(question, delay=20)
        else:
            locator.press_sequentially(question, delay=20)
        if verify_input_text(locator, question, input_type):
            logger.info("[INPUT] keyboard.type attempt success")
            return True
        logger.warning("[INPUT] keyboard.type failed: verification failed")
        return False
    except Exception as exc:
        logger.warning("[INPUT] keyboard.type attempt failed: %s", exc)
        return False


def _try_js_fallback(locator: Locator, question: str, input_type: str, logger: Any) -> bool:
    logger.warning("[INPUT] JS fallback used")
    try:
        if input_type in ("input", "textarea"):
            locator.evaluate(
                "(el, v) => { el.value = v;"
                " el.dispatchEvent(new Event('input', {bubbles: true}));"
                " el.dispatchEvent(new Event('change', {bubbles: true})); }",
                question,
            )
        else:
            locator.evaluate(
                "(el, v) => { el.textContent = v;"
                " el.dispatchEvent(new Event('input', {bubbles: true}));"
                " el.dispatchEvent(new Event('change', {bubbles: true})); }",
                question,
            )
        if verify_input_text(locator, question, input_type):
            logger.info("[INPUT] JS fallback success")
            return True
        logger.warning("[INPUT] JS fallback failed: verification failed")
        return False
    except Exception as exc:
        logger.warning("[INPUT] JS fallback failed: %s", exc)
        return False


def enter_question_with_verification(
    scope: Page | Frame,
    input_locator: Locator,
    question: str,
    logger: Any,
) -> tuple[bool, str]:
    """Try multiple strategies to type *question* and verify it was accepted.

    Returns ``(input_verified, method_used)`` where *method_used* is one of
    ``"fill"``, ``"press_sequentially"``, ``"keyboard"``, ``"js"`` or ``""``
    when all strategies fail.
    """

    input_type = _detect_input_type(input_locator)
    logger.info("[INPUT] locator found via resolved context")
    logger.info("[INPUT] detected type: %s", input_type)

    _focus_input(input_locator, logger)
    _clear_input(input_locator, input_type)

    if _try_fill(input_locator, question, input_type, logger):
        return True, "fill"

    _clear_input(input_locator, input_type)
    _focus_input(input_locator, logger)

    if _try_press_sequentially(input_locator, question, input_type, logger):
        return True, "press_sequentially"

    _clear_input(input_locator, input_type)
    _focus_input(input_locator, logger)

    if _try_keyboard_type(scope, input_locator, question, input_type, logger):
        return True, "keyboard"

    _clear_input(input_locator, input_type)

    if _try_js_fallback(input_locator, question, input_type, logger):
        return True, "js"

    logger.error("[INPUT] all strategies failed for question: %.60s", question)
    return False, ""


def capture_baseline_state(context: ResolvedChatContext) -> dict[str, Any]:
    """Capture the pre-submit bot-message baseline used for strict answer detection."""

    capture_baseline_bot_snapshot(context)
    context.baseline_history = extract_message_history_candidates(context)
    context.baseline_visible_text = extract_visible_chat_text(context)
    context.baseline_send_button_enabled = _is_send_button_enabled(context.send_locator)
    return {
        "baseline_bot_count": context.baseline_bot_count,
        "baseline_bot_messages": list(context.baseline_bot_messages),
        "baseline_history": list(context.baseline_history),
        "baseline_visible_text": context.baseline_visible_text,
        "baseline_send_button_enabled": context.baseline_send_button_enabled,
    }


def extract_last_new_bot_message(context: ResolvedChatContext) -> str:
    """Return the latest post-baseline bot message that is not menu text."""

    bot_messages = extract_bot_message_texts(context)
    current_count = len(bot_messages)
    if current_count <= context.baseline_bot_count:
        return ""
    new_messages = bot_messages[context.baseline_bot_count:current_count]
    candidates = [
        message for message in new_messages if _is_new_response_candidate(message, context.baseline_bot_messages)
    ]
    return candidates[-1] if candidates else ""


def _capture_stage(
    page: Page,
    context: ResolvedChatContext | None,
    case_id: str,
    timestamp: str,
    stage: str,
    config: AppConfig,
    logger: Any,
) -> tuple[str, str]:
    """Capture fullpage + chatbox screenshots for a named stage.

    Returns ``(fullpage_path, chatbox_path)`` strings (empty on failure).
    """

    safe_id = sanitize_filename(case_id)
    fullpage_path = config.fullpage_dir / f"{timestamp}_{safe_id}_{stage}.png"
    chatbox_path = config.chatbox_dir / f"{timestamp}_{safe_id}_{stage}.png"

    fp_str = ""
    cb_str = ""

    try:
        page.screenshot(path=str(fullpage_path), full_page=True)
        fp_str = str(fullpage_path)
    except Exception as exc:
        logger.warning("stage %s fullpage screenshot failed: %s", stage, exc)

    try:
        if context is not None and context.container_locator is not None:
            context.container_locator.screenshot(path=str(chatbox_path))
        elif context is not None:
            context.input_locator.screenshot(path=str(chatbox_path))
        else:
            page.screenshot(path=str(chatbox_path))
        cb_str = str(chatbox_path)
    except Exception as exc:
        logger.warning("stage %s chatbox screenshot failed: %s", stage, exc)

    if cb_str:
        logger.info("[ARTIFACT] %s screenshot saved: %s", stage, cb_str)
    if fp_str:
        logger.info("[ARTIFACT] %s fullpage saved: %s", stage, fp_str)

    return fp_str, cb_str


def verify_submit_effect(context: ResolvedChatContext, question: str, input_locator: Locator) -> bool:
    """Verify that submitting the question had a real effect on the chat UI."""

    runtime = _runtime()
    input_type = detect_input_kind(input_locator)
    after_value = _read_input_value(input_locator, input_type)
    input_cleared = after_value == ""
    runtime.logger.info("[SUBMIT] after_send input value: %s", after_value)
    runtime.logger.info("[SUBMIT] input cleared %s", input_cleared)

    history_after = extract_message_history_candidates(context)
    history_count_changed = len(history_after) > len(context.baseline_history)
    history_contains_question = any(_normalize_text(question) in _normalize_text(item) for item in history_after)
    visible_text = extract_visible_chat_text(context)
    visible_text_changed = _normalize_text(visible_text) != _normalize_text(context.baseline_visible_text)
    visible_contains_question = _normalize_text(question) in _normalize_text(visible_text)
    user_echo = verify_user_message_echo(context, question, runtime.logger)
    send_button_enabled_after = _is_send_button_enabled(context.send_locator)
    send_button_state_changed = send_button_enabled_after != context.baseline_send_button_enabled

    runtime.logger.info("[HISTORY] history extracted count: %s", len(history_after))
    runtime.logger.info("[SUBMIT] user echo verified %s", user_echo)
    runtime.logger.info("[SUBMIT] history count increased %s", history_count_changed)
    runtime.logger.info("[SUBMIT] history contains question %s", history_contains_question)
    runtime.logger.info("[SUBMIT] visible text changed %s", visible_text_changed)
    runtime.logger.info("[SUBMIT] send button state changed %s", send_button_state_changed)

    verified = any(
        [
            input_cleared,
            user_echo,
            history_count_changed,
            history_contains_question,
            visible_contains_question,
            visible_text_changed,
            send_button_state_changed,
        ]
    )
    runtime.logger.info("[SUBMIT] submit effect verified %s", verified)
    if not verified:
        runtime.logger.warning("[SUBMIT] after_send input value unchanged" if not input_cleared else "[SUBMIT] input cleared true")
        runtime.logger.warning("[SUBMIT] submission effect not verified")
    return verified


def trigger_submit(page: Page, context: ResolvedChatContext, question: str) -> tuple[bool, str, bool, str, str]:
    """Trigger submit using button click first, then Enter, and verify its effect."""

    runtime = _runtime()
    input_locator = context.input_locator
    before_value = _read_input_value(input_locator, detect_input_kind(input_locator))
    runtime.logger.info("[SUBMIT] before_send input value: %s", before_value)
    runtime.logger.info("[SUBMIT] send button found: %s", context.send_locator is not None)

    methods: list[tuple[str, bool]] = []
    if context.send_locator is not None:
        methods.append(("button_click", True))
    methods.append(("enter", False))

    for method_name, use_button in methods:
        try:
            if use_button and context.send_locator is not None:
                context.send_locator.click(timeout=2500)
                runtime.logger.info("[SUBMIT] send button clicked")
            else:
                input_locator.click(timeout=1500)
                input_locator.press("Enter")
                runtime.logger.info("[SUBMIT] Enter submit attempted")
        except Exception as exc:
            runtime.logger.warning("[SUBMIT] %s failed: %s", method_name, exc)
            continue

        after_send_fullpage, after_send_chatbox = _capture_stage(
            page,
            context,
            runtime.current_case_id,
            runtime.current_case_timestamp,
            "after_send",
            runtime.config,
            runtime.logger,
        )

        try:
            if hasattr(context.scope, "wait_for_timeout"):
                context.scope.wait_for_timeout(ECHO_RENDER_DELAY_MS)
            else:
                time.sleep(ECHO_RENDER_DELAY_SEC)
        except Exception:
            pass

        submit_effect_verified = verify_submit_effect(context, question, input_locator)
        user_echo_verified = verify_user_message_echo(context, question, runtime.logger)
        if submit_effect_verified:
            return True, method_name, user_echo_verified, after_send_chatbox, after_send_fullpage

    return False, "unknown", False, "", ""


def submit_question(
    page: Page,
    context: ResolvedChatContext,
    question: str,
) -> SubmissionEvidence:
    """Enter a question, verify DOM state, trigger submit, and verify submit effect."""

    runtime = _runtime()
    capture_baseline_state(context)

    input_dom_verified, method_used = enter_question_with_verification(
        context.scope, context.input_locator, question, runtime.logger
    )
    input_dom_verified = input_dom_verified and verify_input_dom_state(context.input_locator, question)

    if not input_dom_verified:
        runtime.logger.error(
            "[INPUT] verification failed — will not send question: %.60s", question
        )
        raise RuntimeError(
            f"Question input not verified after all strategies: {question[:60]}"
        )

    runtime.logger.info(
        "[INPUT] verification success: %.60s  (method=%s)", question, method_used
    )

    before_send_fullpage, before_send_chatbox = _capture_stage(
        page,
        context,
        runtime.current_case_id,
        runtime.current_case_timestamp,
        "before_send",
        runtime.config,
        runtime.logger,
    )

    if not before_send_chatbox or not before_send_fullpage:
        runtime.logger.error("[VERIFY] before_send evidence missing; capture is invalid")
        raise RuntimeError("before_send screenshot missing")

    submit_effect_verified, submit_method_used, echo_verified, after_send_chatbox, after_send_fullpage = trigger_submit(
        page, context, question
    )
    input_verified = input_dom_verified and submit_effect_verified

    capture_reason = ""
    if not submit_effect_verified:
        capture_reason = (
            "Input value changed but submit effect not verified"
            if method_used == "js"
            else "Question submission effect not verified"
        )

    return SubmissionEvidence(
        input_dom_verified=input_dom_verified,
        submit_effect_verified=submit_effect_verified,
        input_verified=input_verified,
        input_method_used=method_used,
        submit_method_used=submit_method_used,
        before_send_chatbox_path=before_send_chatbox,
        before_send_fullpage_path=before_send_fullpage,
        after_send_chatbox_path=after_send_chatbox,
        after_send_fullpage_path=after_send_fullpage,
        user_message_echo_verified=echo_verified,
        capture_reason=capture_reason,
    )


def _loading_visible(context: ResolvedChatContext) -> bool:
    for candidate in context.loading_candidates:
        locator = _maybe_visible(context.scope, candidate)
        if locator is not None:
            return True
    return False


def wait_for_answer_completion(context: ResolvedChatContext) -> AnswerWaitResult:
    """Wait until a post-baseline bot answer becomes stable or timeout occurs."""

    runtime = _runtime()
    started = time.perf_counter()
    deadline = started + (runtime.config.playwright_timeout_ms / 1000.0)
    stable_checks = 0
    previous_text = ""
    latest_text = ""
    baseline_menu_detected = False
    count_increase_observed = False
    text_diff_observed = False

    while time.perf_counter() < deadline:
        bot_messages = extract_bot_message_texts(context)
        current_count = len(bot_messages)
        count_increased = current_count > context.baseline_bot_count
        new_text = detect_new_bot_text(context, context.baseline_bot_messages)
        if count_increased:
            count_increase_observed = True
        if new_text:
            text_diff_observed = True

        runtime.logger.info("[ANSWER] new bot count detected %s", count_increased)
        runtime.logger.info("[ANSWER] new bot text diff detected %s", bool(new_text))

        if count_increased or new_text:
            new_messages = bot_messages[context.baseline_bot_count : current_count] if count_increased else []
            candidate_messages = [
                message for message in new_messages if _is_new_response_candidate(message, context.baseline_bot_messages)
            ]
            if candidate_messages:
                latest_text = candidate_messages[-1]
            elif new_text:
                latest_text = new_text
            elif any(
                _contains_baseline_menu(message)
                or _normalize_text(message) in {_normalize_text(item) for item in context.baseline_bot_messages}
                for message in new_messages
            ):
                baseline_menu_detected = True
                latest_text = ""
            if latest_text:
                if latest_text == previous_text:
                    stable_checks += 1
                else:
                    stable_checks = 1
                    previous_text = latest_text
                if stable_checks >= runtime.config.answer_stable_checks and not _loading_visible(context):
                    response_ms = int((time.perf_counter() - started) * 1000)
                    runtime.logger.info("[ANSWER] answer stabilized true")
                    return AnswerWaitResult(
                        answer=latest_text,
                        response_ms=response_ms,
                        new_bot_response_detected=True,
                        baseline_menu_detected=baseline_menu_detected,
                        reason="",
                    )

        if hasattr(context.scope, "wait_for_timeout"):
            context.scope.wait_for_timeout(int(runtime.config.answer_stable_interval_sec * 1000))
        else:
            time.sleep(runtime.config.answer_stable_interval_sec)

    runtime.logger.info("[ANSWER] answer stabilized false")
    if baseline_menu_detected:
        reason = "Baseline menu only; no answer generated"
    elif count_increase_observed or text_diff_observed:
        reason = "No new bot response after successful submit"
    else:
        reason = "Question submission not reflected in chat history"
    return AnswerWaitResult(
        answer="",
        response_ms=int((time.perf_counter() - started) * 1000),
        new_bot_response_detected=False,
        baseline_menu_detected=baseline_menu_detected,
        reason=reason,
    )


def wait_for_new_bot_response(context: ResolvedChatContext, baseline_bot_count: int) -> AnswerWaitResult:
    """Wait until a new bot response appears after the recorded baseline count."""

    context.baseline_bot_count = baseline_bot_count
    if not context.baseline_bot_messages:
        context.baseline_bot_messages = extract_bot_message_texts(context)[:baseline_bot_count]
    return wait_for_answer_completion(context)


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


def run_single_case(page: Page, test_case: TestCase) -> ExtractedPair:
    """Execute one public, non-login Rubicon chatbot scenario end-to-end."""

    runtime = _runtime()
    runtime.current_case_id = test_case.id
    runtime.current_case_timestamp = artifact_timestamp()
    runtime.latest_html_fragment_path = ""

    context: ResolvedChatContext | None = None
    artifacts = BrowserArtifacts()
    answer = ""
    extraction_source = "unknown"
    extraction_confidence = 0.0
    response_ms = 0
    status = "passed"
    reason = ""
    error_message = ""
    input_dom_verified = False
    submit_effect_verified = False
    input_verified = False
    input_method_used = ""
    submit_method_used = "unknown"
    opened_chat_screenshot_path = ""
    opened_full_screenshot_path = ""
    before_send_screenshot_path = ""
    before_send_full_screenshot_path = ""
    after_send_screenshot_path = ""
    after_send_full_screenshot_path = ""
    font_fix_applied = False
    user_message_echo_verified = False
    new_bot_response_detected = False
    baseline_menu_detected = False
    message_history: list[str] = []
    after_answer_screenshot_path = ""
    after_answer_full_screenshot_path = ""

    try:
        open_homepage(page)
        font_fix_applied = inject_korean_font(page)
        dismiss_popups(page)
        open_rubicon_widget(page)

        opened_full_screenshot_path, opened_chat_screenshot_path = _capture_stage(
            page,
            None,
            test_case.id,
            runtime.current_case_timestamp,
            "opened",
            runtime.config,
            runtime.logger,
        )

        context = resolve_chat_context(page)
        opened_full_screenshot_path, opened_chat_screenshot_path = _capture_stage(
            page,
            context,
            test_case.id,
            runtime.current_case_timestamp,
            "opened",
            runtime.config,
            runtime.logger,
        )

        submission = submit_question(page, context, test_case.question)
        input_dom_verified = submission.input_dom_verified
        submit_effect_verified = submission.submit_effect_verified
        input_verified = submission.input_verified
        input_method_used = submission.input_method_used
        submit_method_used = submission.submit_method_used
        before_send_screenshot_path = submission.before_send_chatbox_path
        before_send_full_screenshot_path = submission.before_send_fullpage_path
        after_send_screenshot_path = submission.after_send_chatbox_path
        after_send_full_screenshot_path = submission.after_send_fullpage_path
        user_message_echo_verified = submission.user_message_echo_verified

        if not input_dom_verified or not before_send_screenshot_path or not before_send_full_screenshot_path:
            status = "invalid_capture"
            reason = "Question input DOM state was not verified or before_send evidence is missing"
            error_message = reason
            runtime.logger.error("[VERIFY] invalid capture before send for %s", test_case.id)
        elif not submit_effect_verified:
            status = "invalid_capture"
            reason = submission.capture_reason or "Question submission effect not verified"
            error_message = reason
            runtime.logger.error("[VERIFY] invalid capture after send for %s", test_case.id)
        else:
            wait_result = wait_for_new_bot_response(context, context.baseline_bot_count)
            answer = wait_result.answer
            response_ms = wait_result.response_ms
            new_bot_response_detected = wait_result.new_bot_response_detected
            baseline_menu_detected = wait_result.baseline_menu_detected

            after_answer_full_screenshot_path, after_answer_screenshot_path = _capture_stage(
                page,
                context,
                test_case.id,
                runtime.current_case_timestamp,
                "after_answer",
                runtime.config,
                runtime.logger,
            )

            artifacts = capture_artifacts(page, context, test_case.id)

            dom_payload = extract_dom_payload(context, artifacts.html_fragment_path)
            message_history = dom_payload.get("history", [])
            if not message_history:
                runtime.logger.warning(
                    "[HISTORY] no structured message history extracted; falling back to visible chat text scan"
                )
                visible_text = dom_payload.get("visible_chat_text", "")
                message_history = [line for line in visible_text.splitlines() if line.strip()]
                runtime.logger.info("[HISTORY] visible chat text fallback used")
            runtime.logger.info("[HISTORY] history extracted count: %s", len(message_history))

            if not new_bot_response_detected:
                status = "invalid_capture"
                reason = wait_result.reason
                error_message = wait_result.reason
            elif answer:
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
                status = "invalid_capture"
                reason = reason or "Message history extraction failed"
                error_message = error_message or reason
            elif not user_message_echo_verified and not (submit_effect_verified and new_bot_response_detected):
                status = "invalid_capture"
                reason = "Question submission not reflected in chat history"
                error_message = reason
            elif status == "passed":
                reason = "Validated submitted question effect and detected a new bot response after baseline"
    except RuntimeError as exc:
        # RuntimeError raised by submit_question means input was never verified
        err_str = str(exc)
        if "not verified" in err_str or "before_send screenshot missing" in err_str:
            status = "invalid_capture"
            reason = err_str
        else:
            status = "failed"
            reason = err_str
        error_message = err_str
        runtime.logger.error("exception details: %s", exc)
        try:
            if artifacts.fullpage_screenshot is None and artifacts.chatbox_screenshot is None:
                artifacts = capture_artifacts(page, context, test_case.id)
        except Exception:
            pass
    except Exception as exc:
        status = "failed"
        reason = str(exc)
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
        reason=reason,
        error_message=error_message,
        full_screenshot_path=after_answer_full_screenshot_path or str(artifacts.fullpage_screenshot or ""),
        chat_screenshot_path=after_answer_screenshot_path or str(artifacts.chatbox_screenshot or ""),
        video_path="",
        trace_path="",
        html_fragment_path=str(artifacts.html_fragment_path or runtime.latest_html_fragment_path or ""),
        input_dom_verified=input_dom_verified,
        submit_effect_verified=submit_effect_verified,
        input_verified=input_verified,
        input_method_used=input_method_used,
        submit_method_used=submit_method_used,
        opened_chat_screenshot_path=opened_chat_screenshot_path,
        opened_full_screenshot_path=opened_full_screenshot_path,
        before_send_screenshot_path=before_send_screenshot_path,
        before_send_full_screenshot_path=before_send_full_screenshot_path,
        after_send_screenshot_path=after_send_screenshot_path,
        after_send_full_screenshot_path=after_send_full_screenshot_path,
        after_answer_screenshot_path=after_answer_screenshot_path,
        after_answer_full_screenshot_path=after_answer_full_screenshot_path,
        font_fix_applied=font_fix_applied,
        user_message_echo_verified=user_message_echo_verified,
        new_bot_response_detected=new_bot_response_detected,
        baseline_menu_detected=baseline_menu_detected,
        message_history=message_history,
    )

