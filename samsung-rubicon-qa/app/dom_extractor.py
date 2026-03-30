"""DOM-first extraction helpers for Samsung Rubicon chatbot responses."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from app.models import ResolvedChatContext
from app.utils import build_locator, ensure_parent, locator_text


def count_bot_messages(chat_context: ResolvedChatContext) -> int:
    """Count bot message nodes matching the configured locator candidates."""

    max_count = 0
    for candidate in chat_context.bot_message_candidates:
        locator = build_locator(chat_context.scope, candidate)
        try:
            max_count = max(max_count, locator.count())
        except Exception:
            continue
    return max_count


def extract_last_bot_message_text(chat_context: ResolvedChatContext) -> str:
    """Extract the last visible bot response text from DOM locators."""

    for candidate in chat_context.bot_message_candidates:
        locator = build_locator(chat_context.scope, candidate)
        try:
            count = locator.count()
        except Exception:
            continue
        if count <= 0:
            continue
        for index in range(count - 1, -1, -1):
            text = locator_text(locator.nth(index))
            if text:
                return text
    return ""


def extract_message_history(chat_context: ResolvedChatContext) -> list[str]:
    """Extract normalized message history from DOM locators."""

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
    return messages


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
        "html_fragment_path": html_fragment_path,
    }
