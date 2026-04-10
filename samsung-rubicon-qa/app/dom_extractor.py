"""DOM-first, baseline-aware extraction helpers for Sprinklr chat responses."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from app.models import ResolvedChatContext
from app.utils import build_locator, ensure_parent


STATIC_UI_TEXTS = [
    "구매 상담사와 채팅 하세요",
    "삼성닷컴 구매 상담사와 채팅하세요",
    "구매 상담사와 채팅하세요",
    "Samsung AI Assistant",
    "Samsung AI assistant",
    "아래에서 원하는 항목을 선택해 주세요",
    "구매 상담사 연결",
    "주문·배송 조회",
    "주문 배송 조회",
    "모바일 케어플러스",
    "가전 케어플러스",
    "서비스 센터",
    "FAQ",
    "메시지를 입력",
    "질문을 입력",
    "무엇을 도와드릴까요",
    "입력 placeholder",
    "채팅 입력",
    "메시지 보내기",
    "보내기",
    "전송",
    "채팅 닫기",
    "닫기",
    "최소화",
    "최대화",
    "아이콘 설명",
    "Maximize Widget",
    "삼성닷컴 AI",
    "AI 생성 메시지는 부정확할 수 있습니다",
    "더보기",
    "리치 텍스트 메시지",
]

FOLLOW_UP_SPLIT_MARKERS = [
    "🔍 이어서 물어보세요",
    "이어서 물어보세요",
    "AI 생성 메시지는 부정확할 수 있습니다",
]

COMMERCE_TAIL_SPLIT_MARKERS = [
    "더 알아보기",
]

META_PREFIX_PATTERNS = [
    r"^자세한 내용을 보려면 Enter를 누르세요[.\s,:-]*",
    r"^리치 텍스트 메시지[.\s,:-]*",
    r"^첨부[.\s,:-]*",
    r"^더보기[.\s,:-]*",
]

MESSAGE_LIKE_SELECTORS = [
    "[data-message-author]",
    "[data-author]",
    "[role='log'] article",
    "[role='log'] li",
    "[role='list'] article",
    "[role='list'] li",
    "[aria-live] article",
    "[aria-live] li",
    "article[class*='message' i]",
    "div[class*='message' i]",
    "div[class*='chat' i]",
    "div[class*='bubble' i]",
    "div[class*='assistant' i]",
    "div[class*='agent' i]",
    "section[class*='message' i]",
]

USER_MESSAGE_SELECTORS = [
    ".user-message",
    "[data-message-author='user']",
    "[data-author='user']",
    "[data-author='customer']",
    "[class*='user' i][class*='message' i]",
    "[class*='customer' i][class*='message' i]",
    "[class*='outgoing' i]",
    "[class*='sent' i]",
]

HISTORY_DUMP_HINTS = [
    "Samsung AI CS Chat",
    "고객지원이 필요하신가요?",
    "안녕하세요",
    "프롬프트 생성 중 오류가 발생했습니다",
    "채팅을 다시 시작하세요",
    "삼성닷컴에서 어떤 제품들을 구매할 수 있나요?",
]


def normalize_text_for_diff(text: str) -> str:
    sanitized = re.sub(r"[\u200e\u200f\u202a-\u202e\ufeff]", "", str(text or ""))
    return " ".join(sanitized.replace("\xa0", " ").split())


def _static_ui_normalized() -> set[str]:
    return {normalize_text_for_diff(text).lower() for text in STATIC_UI_TEXTS}


def _normalize_multiline_text(text: str) -> str:
    return "\n".join(line.strip() for line in str(text or "").splitlines() if line.strip())


def _looks_like_product_card(text: str) -> bool:
    normalized = normalize_text_for_diff(text)
    if not normalized:
        return False

    has_cta = any(marker in normalized for marker in COMMERCE_TAIL_SPLIT_MARKERS)
    has_price = bool(re.search(r"\b\d[\d,]*\s*원\b", normalized))
    has_rating = "⭐" in normalized or bool(re.search(r"\b평점\b|\b리뷰\b", normalized))
    has_model_code = bool(re.search(r"\b[A-Z]{2,}-[A-Z0-9]{3,}\b", normalized))

    return has_cta and (has_price or has_rating or has_model_code)


def _looks_like_product_title(text: str) -> bool:
    normalized = normalize_text_for_diff(text)
    if not normalized:
        return False

    has_model_code = bool(re.search(r"\b(?:SM|KQ|NT|EF|GP|EP)-?[A-Z0-9]{3,}\b", normalized))
    has_title_hint = any(marker in normalized for marker in ("자급제", "전용컬러", "삼성 강남", "삼성닷컴"))
    has_sentence_ending = normalized.endswith((".", "다", "요", "니다"))
    looks_like_single_title = "\n" not in normalized and len(normalized.split()) <= 12

    return looks_like_single_title and (has_model_code or has_title_hint) and not has_sentence_ending


def _trim_product_card_tail(text: str) -> str:
    normalized = normalize_text_for_diff(text)
    if not normalized:
        return ""
    if not _looks_like_product_card(normalized) and "더 알아보기" not in normalized:
        return normalized

    for marker in COMMERCE_TAIL_SPLIT_MARKERS:
        marker_index = normalized.find(marker)
        if marker_index < 0:
            continue
        prefix = normalized[:marker_index].rstrip()
        sentence_break = max(prefix.rfind(". "), prefix.rfind("다 "), prefix.rfind("요 "), prefix.rfind("니다 "))
        if sentence_break >= 0:
            prefix = prefix[: sentence_break + 1].rstrip()
        price_match = re.search(r"\b\d[\d,]*\s*원\b", prefix)
        if price_match:
            prefix = prefix[: price_match.start()].rstrip()
        if prefix and not _looks_like_product_card(prefix):
            return prefix
    return normalized


def _strip_meta_text(text: str) -> str:
    normalized = normalize_text_for_diff(text)
    if not normalized:
        return ""

    for marker in FOLLOW_UP_SPLIT_MARKERS:
        if marker in normalized:
            normalized = normalized.split(marker, 1)[0].strip()

    cleaned = normalized
    prefix_trimmed = True
    while prefix_trimmed:
        prefix_trimmed = False
        for pattern in META_PREFIX_PATTERNS:
            updated = re.sub(pattern, " ", cleaned, flags=re.IGNORECASE)
            if updated != cleaned:
                cleaned = updated.strip()
                prefix_trimmed = True

    cleaned = re.sub(r"\b(?:좋아요|싫어요|싫어함|like|dislike|thumbs up|thumbs down)\b", " ", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"(?:오전|오후)\s*[0-9]{1,2}:[0-9]{2}(?::[0-9]{2})?", " ", cleaned)
    cleaned = re.sub(r"(?:AM|PM)\s*[0-9]{1,2}:[0-9]{2}(?::[0-9]{2})?", " ", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"[0-9]{1,2}:[0-9]{2}(?:\s?[AP]M)?", " ", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r",?\s*[0-9]{4}년\s*[0-9]{1,2}월\s*[0-9]{1,2}일\s*에\s*(?:수신됨|전송됨)", " ", cleaned)
    cleaned = _trim_product_card_tail(cleaned)
    return " ".join(cleaned.split())


def is_static_ui_text(text: str) -> bool:
    normalized = normalize_text_for_diff(text)
    normalized_lower = normalized.lower()
    if not normalized:
        return True
    if len(normalized) <= 1:
        return True
    if re.fullmatch(r"[0-9]{1,2}:[0-9]{2}(?:\s?[AP]M)?", normalized, re.IGNORECASE):
        return True
    if re.fullmatch(r"(?:오전|오후)\s*[0-9]{1,2}:[0-9]{2}(?::[0-9]{2})?", normalized):
        return True
    if re.fullmatch(r"(?:AM|PM)\s*[0-9]{1,2}:[0-9]{2}(?::[0-9]{2})?", normalized, re.IGNORECASE):
        return True
    if re.fullmatch(r"[0-9]{4}[./-][0-9]{1,2}[./-][0-9]{1,2}", normalized):
        return True
    return normalized_lower in _static_ui_normalized()


def _contains_embedded_static_ui_text(text: str) -> bool:
    normalized_lower = normalize_text_for_diff(text).lower()
    if not normalized_lower:
        return False
    return any(static_text in normalized_lower for static_text in _static_ui_normalized() if static_text and static_text != normalized_lower)


def looks_like_chat_history_dump(text: str) -> bool:
    normalized = _strip_meta_text(text)
    if not normalized or len(normalized) < 120:
        return False

    hint_count = sum(1 for hint in HISTORY_DUMP_HINTS if hint in normalized)
    question_like_count = normalized.count("?") + normalized.count("요?")

    if hint_count >= 2:
        return True
    if hint_count >= 1 and question_like_count >= 2:
        return True
    if _contains_embedded_static_ui_text(normalized) and question_like_count >= 2:
        return True

    return False


def remove_static_ui_segments(segments: list[str]) -> list[str]:
    filtered: list[str] = []
    seen: set[str] = set()
    for segment in segments:
        normalized = _strip_meta_text(segment)
        if not normalized or is_static_ui_text(normalized):
            continue
        if looks_like_chat_history_dump(normalized):
            continue
        if len(normalized) < 6:
            continue
        if normalized in seen:
            continue
        seen.add(normalized)
        filtered.append(_normalize_multiline_text(normalized))
    return filtered


def filter_out_static_ui_text(segments: list[str]) -> list[str]:
    return remove_static_ui_segments(segments)


def _ordered_unique_segments(segments: list[str]) -> list[str]:
    ordered: list[str] = []
    seen: set[str] = set()
    for segment in segments:
        normalized = _strip_meta_text(segment)
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        ordered.append(_normalize_multiline_text(normalized))
    return ordered


def _merge_answer_candidates(*candidate_groups: list[str]) -> list[str]:
    merged: list[str] = []
    seen: set[str] = set()
    for group in candidate_groups:
        for segment in group:
            normalized = _strip_meta_text(segment)
            if not normalized or normalized in seen:
                continue
            seen.add(normalized)
            merged.append(_normalize_multiline_text(normalized))
    return merged


def _remove_question_echo_segments(segments: list[str], question: str = "") -> list[str]:
    question_norm = _strip_meta_text(question).lower()
    if not question_norm:
        return segments

    filtered: list[str] = []
    for segment in segments:
        normalized = _strip_meta_text(segment).lower()
        if not normalized:
            continue
        if normalized == question_norm:
            continue
        filtered.append(segment)
    return filtered


def _candidate_snapshot_script() -> str:
    return r"""
(node) => {
  const normalize = (value) => (value || '').replace(/\u00a0/g, ' ').replace(/\s+/g, ' ').trim();
  const visible = (el) => {
    if (!el) return false;
    const style = window.getComputedStyle(el);
    if (!style || style.display === 'none' || style.visibility === 'hidden') return false;
    const rect = el.getBoundingClientRect();
    return rect.width > 0 && rect.height > 0;
  };
  const depthFrom = (root, el) => {
    let depth = 0;
    let cursor = el;
    while (cursor && cursor !== root) {
      depth += 1;
      cursor = cursor.parentElement;
    }
    return depth;
  };
  const descendants = [node, ...node.querySelectorAll('*')]
    .filter((el) => visible(el))
    .map((el) => {
      const text = normalize(el.innerText || el.textContent || '');
      if (!text) return null;
      return {
        text,
        depth: depthFrom(node, el),
        tag: (el.tagName || '').toLowerCase(),
        className: typeof el.className === 'string' ? el.className : '',
        role: el.getAttribute('role') || '',
        testId: el.getAttribute('data-testid') || '',
        ariaLabel: el.getAttribute('aria-label') || '',
      };
    })
    .filter(Boolean);
  return {
    wrapperText: normalize(node.innerText || node.textContent || ''),
    descendants,
    className: typeof node.className === 'string' ? node.className : '',
    role: node.getAttribute('role') || '',
    tag: (node.tagName || '').toLowerCase(),
    testId: node.getAttribute('data-testid') || '',
    ariaLabel: node.getAttribute('aria-label') || '',
  };
}
"""


def find_text_containing_descendants(node: dict[str, Any]) -> list[str]:
    descendants = node.get("descendants", []) if isinstance(node, dict) else []
    texts: list[str] = []
    seen: set[str] = set()
    for descendant in descendants:
        text = normalize_text_for_diff(descendant.get("text", ""))
        if not text or text in seen:
            continue
        seen.add(text)
        texts.append(text)
    return texts


def extract_clean_text_from_message_node(node: dict[str, Any]) -> str:
    options = find_text_containing_descendants(node)
    if isinstance(node, dict):
        wrapper_text = normalize_text_for_diff(node.get("wrapperText", ""))
        if wrapper_text and not looks_like_chat_history_dump(wrapper_text):
            options.append(wrapper_text)

    best_text = ""
    best_score = -10**9
    for option in options:
        normalized = _strip_meta_text(option)
        if not normalized or is_static_ui_text(normalized):
            continue
        score = len(normalized)
        if "\n" in option:
            score += 12
        if len(normalized.split()) >= 5:
            score += 8
        if len(normalized) <= 8:
            score -= 12
        if _contains_embedded_static_ui_text(normalized):
            score -= 20
        if best_text and normalized in normalize_text_for_diff(best_text):
            continue
        if score >= best_score:
            best_score = score
            best_text = _normalize_multiline_text(normalized)
    return best_text


def _collect_candidate_snapshots(locator: Any) -> list[dict[str, Any]]:
    try:
        return locator.evaluate_all(
            f"""
(nodes) => {{
  const collect = {_candidate_snapshot_script().strip()};
  return nodes.map((node) => collect(node));
}}
"""
        )
    except Exception:
        return []


def _collect_candidates_from_specs(chat_context: ResolvedChatContext, specs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    collected: list[dict[str, Any]] = []
    for spec in specs:
        try:
            locator = build_locator(chat_context.scope, spec)
        except Exception:
            continue
        collected.extend(_collect_candidate_snapshots(locator))
    return collected


def find_message_candidate_nodes(chat_context: ResolvedChatContext) -> list[dict[str, Any]]:
    candidates = _collect_candidates_from_specs(chat_context, chat_context.bot_message_candidates)
    candidates.extend(_collect_candidates_from_specs(chat_context, chat_context.history_candidates))
    for selector in MESSAGE_LIKE_SELECTORS:
        try:
            locator = chat_context.scope.locator(selector)
        except Exception:
            continue
        candidates.extend(_collect_candidate_snapshots(locator))
    return candidates


def _visible_block_script() -> str:
    return r"""
(root) => {
  const normalize = (value) => (value || '').replace(/\u00a0/g, ' ').replace(/\s+/g, ' ').trim();
  const visible = (el) => {
    if (!el) return false;
    const style = window.getComputedStyle(el);
    if (!style || style.display === 'none' || style.visibility === 'hidden') return false;
    const rect = el.getBoundingClientRect();
    return rect.width > 0 && rect.height > 0;
  };
  const selectors = ['article', 'li', 'p', 'div', 'section', 'span'];
  const nodes = [root, ...root.querySelectorAll(selectors.join(','))];
  const seen = new Set();
  const blocks = [];
  for (const node of nodes) {
    if (!visible(node)) continue;
    const text = normalize(node.innerText || node.textContent || '');
    if (!text || seen.has(text)) continue;
    seen.add(text);
    blocks.push(text);
  }
  return blocks;
}
"""


def extract_visible_text_blocks(chat_context: ResolvedChatContext) -> list[str]:
    try:
        if chat_context.container_locator is not None:
            blocks = chat_context.container_locator.evaluate(_visible_block_script())
            return filter_out_static_ui_text([_normalize_multiline_text(block) for block in blocks])
    except Exception:
        pass

    visible_text = extract_visible_chat_text(chat_context)
    return filter_out_static_ui_text([line for line in visible_text.splitlines() if line.strip()])


def extract_message_like_blocks(chat_context: ResolvedChatContext) -> list[str]:
    blocks: list[str] = []
    seen: set[str] = set()
    for node in find_message_candidate_nodes(chat_context):
        text = extract_clean_text_from_message_node(node)
        normalized = normalize_text_for_diff(text)
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        blocks.append(text)
    return blocks


def compute_new_text_segments(before: str | list[str], after: str | list[str]) -> list[str]:
    before_segments = before if isinstance(before, list) else str(before or "").splitlines()
    after_segments = after if isinstance(after, list) else str(after or "").splitlines()
    before_set = {normalize_text_for_diff(item) for item in before_segments if normalize_text_for_diff(item)}
    result: list[str] = []
    seen: set[str] = set()
    for segment in after_segments:
        normalized = normalize_text_for_diff(segment)
        if not normalized or normalized in before_set or normalized in seen:
            continue
        seen.add(normalized)
        result.append(_normalize_multiline_text(segment))
    return result


def choose_best_answer_segment(segments: list[str]) -> str:
    filtered = filter_out_static_ui_text(segments)
    if not filtered:
        return ""
    best_text = ""
    best_score = -10**9
    for index, segment in enumerate(filtered):
        normalized = _strip_meta_text(segment)
        if not normalized:
            continue
        if looks_like_chat_history_dump(normalized):
            continue
        sentence_like_count = sum(normalized.count(marker) for marker in (". ", "다. ", "요. ", "니다. "))
        score = len(normalized) + (index * 2)
        if len(normalized.split()) >= 5:
            score += 8
        if "\n" in segment:
            score += 10
        if len(normalized) >= 40:
            score += 10
        if sentence_like_count >= 1:
            score += 10
        if normalized.endswith((".", "다", "요", "니다")):
            score += 4
        if _looks_like_product_card(normalized):
            score -= 80
        if _looks_like_product_title(normalized):
            score -= 70
        if normalized.endswith("?"):
            score -= 30
        if len(normalized) <= 40 and normalized.endswith("?"):
            score -= 20
        if score >= best_score:
            best_score = score
            best_text = _normalize_multiline_text(normalized)
    return best_text


def _flatten_scope_text(scope_result: Any) -> str:
    return _normalize_multiline_text(str(scope_result or ""))


def extract_visible_chat_text(chat_context: ResolvedChatContext) -> str:
    text = ""
    try:
        if chat_context.container_locator is not None:
            text = chat_context.container_locator.inner_text(timeout=1500)
    except Exception:
        text = ""

    if text:
        return _flatten_scope_text(text)

    try:
        text = chat_context.scope.evaluate(
            "() => { const el = document.body || document.documentElement; return el ? (el.innerText || el.textContent || '') : ''; }"
        )
    except Exception:
        text = ""

    return _flatten_scope_text(text)


def diff_visible_text_against_baseline(chat_context: ResolvedChatContext) -> list[str]:
    current_blocks = extract_visible_text_blocks(chat_context)
    return compute_new_text_segments(chat_context.baseline_visible_blocks, current_blocks)


def build_post_baseline_answer_candidates(chat_context: ResolvedChatContext, question: str = "") -> dict[str, Any]:
    structured_history = extract_structured_message_history(chat_context)
    bot_texts = extract_bot_message_texts(chat_context)
    current_bot_count = len(bot_texts)
    bot_count_increased = current_bot_count > chat_context.baseline_bot_count
    new_bot_by_count = bot_texts[chat_context.baseline_bot_count:current_bot_count] if bot_count_increased else []
    new_bot_segments = compute_new_text_segments(chat_context.baseline_bot_messages, bot_texts)
    new_history_segments = compute_new_text_segments(
        chat_context.baseline_message_nodes_snapshot,
        structured_history.get("history", []),
    )
    diff_segments = diff_visible_text_against_baseline(chat_context)

    strict_candidates = _ordered_unique_segments(
        _remove_question_echo_segments(
            filter_out_static_ui_text(new_bot_by_count + new_bot_segments),
            question,
        )
    )
    fallback_candidates = _ordered_unique_segments(
        _remove_question_echo_segments(
            filter_out_static_ui_text(new_history_segments + diff_segments),
            question,
        )
    )

    all_candidates = _merge_answer_candidates(strict_candidates, fallback_candidates)

    answer = ""
    if all_candidates:
        answer = choose_best_answer_segment(all_candidates)

    return {
        "answer": answer,
        "history": structured_history.get("history", []),
        "structured_message_history_count": structured_history.get("count", 0),
        "fallback_diff_used": structured_history.get("fallback_diff_used", False) or bool(diff_segments),
        "visible_chat_text": extract_visible_chat_text(chat_context),
        "visible_text_blocks": extract_visible_text_blocks(chat_context),
        "bot_texts": bot_texts,
        "current_bot_count": current_bot_count,
        "bot_count_increased": bot_count_increased,
        "new_bot_segments": new_bot_segments,
        "new_history_segments": new_history_segments,
        "diff_segments": diff_segments,
        "strict_candidates": strict_candidates,
        "fallback_candidates": fallback_candidates,
        "all_candidates": all_candidates,
    }


def extract_bot_message_texts(chat_context: ResolvedChatContext) -> list[str]:
    messages: list[str] = []
    seen: set[str] = set()
    for node in _collect_candidates_from_specs(chat_context, chat_context.bot_message_candidates):
        text = extract_clean_text_from_message_node(node)
        normalized = normalize_text_for_diff(text)
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        messages.append(text)
    return messages


def extract_structured_message_history(chat_context: ResolvedChatContext) -> dict[str, Any]:
    messages: list[str] = []
    seen: set[str] = set()
    fallback_diff_used = False

    for spec_group in [chat_context.bot_message_candidates, chat_context.history_candidates]:
        for node in _collect_candidates_from_specs(chat_context, spec_group):
            text = extract_clean_text_from_message_node(node)
            normalized = normalize_text_for_diff(text)
            if not normalized or normalized in seen:
                continue
            seen.add(normalized)
            messages.append(text)

    for selector in USER_MESSAGE_SELECTORS + MESSAGE_LIKE_SELECTORS:
        try:
            locator = chat_context.scope.locator(selector)
        except Exception:
            continue
        for node in _collect_candidate_snapshots(locator):
            text = extract_clean_text_from_message_node(node)
            normalized = normalize_text_for_diff(text)
            if not normalized or normalized in seen:
                continue
            seen.add(normalized)
            messages.append(text)

    messages = filter_out_static_ui_text(messages)
    if messages:
        return {"history": messages, "count": len(messages), "fallback_diff_used": fallback_diff_used}

    blocks = extract_message_like_blocks(chat_context)
    if blocks:
        fallback_diff_used = True
        return {"history": blocks, "count": len(blocks), "fallback_diff_used": fallback_diff_used}

    diff_segments = diff_visible_text_against_baseline(chat_context)
    fallback_diff_used = True
    return {
        "history": filter_out_static_ui_text(diff_segments),
        "count": len(filter_out_static_ui_text(diff_segments)),
        "fallback_diff_used": fallback_diff_used,
    }


def extract_message_history_candidates(chat_context: ResolvedChatContext) -> list[str]:
    return extract_structured_message_history(chat_context).get("history", [])


def count_bot_messages(chat_context: ResolvedChatContext) -> int:
    return len(extract_bot_message_texts(chat_context))


def extract_last_bot_message_text(chat_context: ResolvedChatContext) -> str:
    bot_messages = extract_bot_message_texts(chat_context)
    return bot_messages[-1] if bot_messages else ""


def extract_message_history(chat_context: ResolvedChatContext) -> list[str]:
    return extract_structured_message_history(chat_context).get("history", [])


def save_html_fragment(chat_context: ResolvedChatContext, output_path: Path | None) -> str:
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


def extract_dom_payload(chat_context: ResolvedChatContext, fragment_path: Path | None, question: str = "") -> dict[str, Any]:
    candidate_data = build_post_baseline_answer_candidates(chat_context, question=question)
    html_fragment_path = save_html_fragment(chat_context, fragment_path)
    return {
        "success": bool(candidate_data["answer"]),
        "answer": candidate_data["answer"],
        "history": candidate_data["history"],
        "structured_message_history_count": candidate_data["structured_message_history_count"],
        "fallback_diff_used": candidate_data["fallback_diff_used"],
        "visible_chat_text": candidate_data["visible_chat_text"],
        "visible_text_blocks": candidate_data["visible_text_blocks"],
        "new_bot_segments": candidate_data["new_bot_segments"],
        "new_history_segments": candidate_data["new_history_segments"],
        "diff_segments": candidate_data["diff_segments"],
        "current_bot_count": candidate_data["current_bot_count"],
        "bot_count_increased": candidate_data["bot_count_increased"],
        "strict_candidates": candidate_data["strict_candidates"],
        "fallback_candidates": candidate_data["fallback_candidates"],
        "all_candidates": candidate_data["all_candidates"],
        "html_fragment_path": html_fragment_path,
    }
