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


def verify_input_text(locator: Locator, question: str, input_type: str) -> bool:
    """Return True when the question text is confirmed present in the input element."""

    try:
        if input_type in ("input", "textarea"):
            value = locator.input_value(timeout=1500)
            return value.strip() == question.strip()
        else:
            text = locator.inner_text(timeout=1500)
            return question.strip() in text.strip()
    except Exception:
        return False


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

    return fp_str, cb_str


def submit_question(
    page: Page,
    context: ResolvedChatContext,
    question: str,
) -> tuple[bool, str, str]:
    """Submit *question* through the resolved chat input with DOM verification.

    Returns ``(input_verified, input_method_used, before_send_chatbox_path)``.
    The question is sent **only** if at least one input strategy passes
    text-content verification.  On total failure the function raises
    ``RuntimeError`` so the caller can mark the case as failed.
    """

    runtime = _runtime()
    context.baseline_bot_count = count_bot_messages(context)

    input_verified, method_used = enter_question_with_verification(
        context.scope, context.input_locator, question, runtime.logger
    )

    if not input_verified:
        runtime.logger.error(
            "[INPUT] verification failed — will not send question: %.60s", question
        )
        raise RuntimeError(
            f"Question input not verified after all strategies: {question[:60]}"
        )

    runtime.logger.info(
        "[INPUT] verification success: %.60s  (method=%s)", question, method_used
    )

    _, before_send_chatbox = _capture_stage(
        page,
        context,
        runtime.current_case_id,
        runtime.current_case_timestamp,
        "before_send",
        runtime.config,
        runtime.logger,
    )

    if context.send_locator is not None:
        try:
            context.send_locator.click(timeout=2500)
            runtime.logger.info("[INPUT] send clicked")
            runtime.logger.info("question submitted")
            return input_verified, method_used, before_send_chatbox
        except Exception:
            pass

    context.input_locator.press("Enter")
    runtime.logger.info("[INPUT] send clicked (Enter key)")
    runtime.logger.info("question submitted")
    return input_verified, method_used, before_send_chatbox


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
        if latest_text and current_count >= max(1, context.baseline_bot_count):
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
    error_message = ""
    input_verified = False
    input_method_used = ""
    before_send_screenshot_path = ""
    font_fix_applied = False

    try:
        open_homepage(page)
        font_fix_applied = inject_korean_font(page)
        dismiss_popups(page)
        open_rubicon_widget(page)

        _capture_stage(
            page,
            None,
            test_case.id,
            runtime.current_case_timestamp,
            "opened",
            runtime.config,
            runtime.logger,
        )

        context = resolve_chat_context(page)
        input_verified, input_method_used, before_send_screenshot_path = submit_question(
            page, context, test_case.question
        )
        answer, response_ms = wait_for_answer_completion(context)

        _capture_stage(
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
        full_screenshot_path=str(artifacts.fullpage_screenshot or ""),
        chat_screenshot_path=str(artifacts.chatbox_screenshot or ""),
        video_path="",
        trace_path="",
        html_fragment_path=str(artifacts.html_fragment_path or runtime.latest_html_fragment_path or ""),
        input_verified=input_verified,
        input_method_used=input_method_used,
        before_send_screenshot_path=before_send_screenshot_path,
        font_fix_applied=font_fix_applied,
    )

