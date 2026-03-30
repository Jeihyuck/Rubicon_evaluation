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
    {"type": "css", "value": "button[aria-label*='chat' i], button[aria-label*='assistant' i], button[aria-label*='rubicon' i]"},
    {"type": "css", "value": "[data-testid*='chat'], [data-testid*='assistant'], [data-testid*='rubicon']"},
    {"type": "css", "value": "button[class*='chat'], button[class*='assistant'], button[class*='floating']"},
    {"type": "css", "value": "div[style*='position: fixed'] button, a[style*='position: fixed'], div[style*='bottom'] button"},
]

INPUT_CANDIDATES = [
    {"type": "role", "role": "textbox", "name": compile_regex(r"질문|문의|메시지|채팅|입력|message|chat")},
    {"type": "label", "value": compile_regex(r"질문|문의|메시지|채팅|입력|message|chat")},
    {"type": "placeholder", "value": compile_regex(r"질문|문의|메시지|무엇을 도와|message|ask")},
    {"type": "css", "value": "textarea, input[type='text'], [contenteditable='true']"},
]

SEND_BUTTON_CANDIDATES = [
    {"type": "role", "role": "button", "name": compile_regex(r"Send|전송|제출|문의|보내기")},
    {"type": "label", "value": compile_regex(r"Send|전송|제출|문의|보내기")},
    {"type": "css", "value": "button[aria-label*='send' i], button[aria-label*='전송'], button[type='submit']"},
    {"type": "css", "value": "button[class*='send'], button[class*='submit'], button svg"},
]

BOT_MESSAGE_CANDIDATES = [
    {"type": "css", "value": ".bot-message, .agent-message, [data-message-author='bot'], [data-author='assistant'], [data-author='bot']"},
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


def submit_question(context: ResolvedChatContext, question: str) -> None:
    """Submit a question through the resolved chat input control."""

    runtime = _runtime()
    context.baseline_bot_count = count_bot_messages(context)

    try:
        context.input_locator.click(timeout=1500)
    except Exception:
        pass

    filled = False
    try:
        context.input_locator.fill(question, timeout=2500)
        filled = True
    except Exception:
        filled = False

    if not filled:
        try:
            context.input_locator.press("Control+A")
            context.input_locator.press("Backspace")
        except Exception:
            pass
        context.input_locator.type(question, delay=25)

    if context.send_locator is not None:
        try:
            context.send_locator.click(timeout=2500)
            runtime.logger.info("question submitted")
            return
        except Exception:
            pass

    context.input_locator.press("Enter")
    runtime.logger.info("question submitted")


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

    try:
        open_homepage(page)
        dismiss_popups(page)
        open_rubicon_widget(page)
        context = resolve_chat_context(page)
        submit_question(context, test_case.question)
        answer, response_ms = wait_for_answer_completion(context)
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
    )
