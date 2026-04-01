"""DOM-first extraction helpers for Samsung Rubicon chatbot responses."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from app.models import ResolvedChatContext
from app.utils import build_locator, ensure_parent, locator_text


def extract_bot_message_texts(chat_context: ResolvedChatContext) -> list[str]:
    """Extract normalized bot message texts from DOM locators."""

    messages: list[str] = []
    seen: set[str] = set()
    for candidate in chat_context.bot_message_candidates:
        locator = build_locator(chat_context.scope, candidate)
        try:
            count = locator.count()
        except Exception:
            continue
        for index in range(count):
            text = locator_text(locator.nth(index))
            if not text:
                continue
            key = f"{index}:{text}"
            if key in seen:
                continue
            seen.add(key)
            messages.append(text)
    return messages


def extract_visible_chat_text(chat_context: ResolvedChatContext) -> str:
    """Extract all visible text from the chat container or the active scope."""

    text = ""
    try:
        if chat_context.container_locator is not None:
            text = chat_context.container_locator.inner_text(timeout=1500)
    except Exception:
        text = ""

    if text:
        return "\n".join(line.strip() for line in text.splitlines() if line.strip())

    try:
        text = chat_context.scope.evaluate(
            "() => { const el = document.body || document.documentElement; return el ? (el.innerText || el.textContent || '') : ''; }"
        )
    except Exception:
        text = ""

    return "\n".join(line.strip() for line in str(text).splitlines() if line.strip())


def extract_message_history_candidates(chat_context: ResolvedChatContext) -> list[str]:
    """Extract chat history using structured selectors first, then visible text fallback."""

    messages: list[str] = []
    seen: set[str] = set()
    candidates = chat_context.history_candidates or chat_context.bot_message_candidates
    for candidate in candidates:
        locator = build_locator(chat_context.scope, candidate)
        try:
            count = locator.count()
        except Exception:
            continue
        for index in range(count):
            text = locator_text(locator.nth(index))
            if not text or text in seen:
                continue
            seen.add(text)
            messages.append(text)

    if messages:
        return messages

    visible_text = extract_visible_chat_text(chat_context)
    for line in visible_text.splitlines():
        normalized = " ".join(line.split())
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        messages.append(normalized)
    return messages


def count_bot_messages(chat_context: ResolvedChatContext) -> int:
    """Count bot message nodes matching the configured locator candidates."""

    return len(extract_bot_message_texts(chat_context))


def extract_last_bot_message_text(chat_context: ResolvedChatContext) -> str:
    """Extract the last visible bot response text from DOM locators."""

    bot_messages = extract_bot_message_texts(chat_context)
    return bot_messages[-1] if bot_messages else ""


def extract_message_history(chat_context: ResolvedChatContext) -> list[str]:
    """Extract normalized message history from DOM locators."""

    return extract_message_history_candidates(chat_context)


def save_html_fragment(chat_context: ResolvedChatContext, output_path: Path | None) -> str:
    """Persist the current chat widget DOM fragment for debugging."""

    if output_path is None:
        return ""

    html = ""
    try:
        if chat_context.container_locator is not None:
            html = chat_context.container_locator.evaluate("node => node.outerHTML")
        else:
            html = chat_context.input_locator.evaluate(
                "node => node.closest('form,section,article,aside,div')?.outerHTML || node.outerHTML"
            )
    except Exception:
        html = ""

    if not html:
        return ""

    ensure_parent(output_path)
    output_path.write_text(html, encoding="utf-8")
    return str(output_path)


def extract_dom_payload(chat_context: ResolvedChatContext, fragment_path: Path | None) -> dict[str, Any]:
    """Extract the DOM-based answer, history, and optional HTML fragment."""

    answer = extract_last_bot_message_text(chat_context)
    history = extract_message_history(chat_context)
    html_fragment_path = save_html_fragment(chat_context, fragment_path)
    return {
        "success": bool(answer),
        "answer": answer,
        "history": history,
        "visible_chat_text": extract_visible_chat_text(chat_context),
        "html_fragment_path": html_fragment_path,
    }
