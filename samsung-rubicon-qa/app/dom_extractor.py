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

FOLLOWUP_CTA_PATTERNS = [
    r"추천 질문",
    r"다음 질문",
    r"관련 질문",
    r"함께 보면 좋은",
    r"자주 묻는 질문",
    r"더 알아보기",
    r"자세히 보기",
    r"CS AI 챗봇에 문의",
    r"AI 챗봇에 문의",
    r"상담원 연결",
    r"문의하기",
    r"채팅 상담",
    r"추가로 궁금하시면",
    r"원하시면 .* 추천",
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

PROMO_PATTERNS = [
    r"구매 혜택",
    r"할인",
    r"쿠폰",
    r"사은품",
    r"더 알아보기",
    r"리뷰에서는",
    r"실사용자 반응",
    r"사용자 반응",
    r"즉시 구매",
    r"현재 구매 가능",
    r"재고",
    r"⭐",
]

PROMO_REVIEW_PATTERNS = [
    r"리뷰 한줄 요약",
    r"실사용자 반응",
    r"리뷰에서는",
    r"구매 혜택",
    r"할인",
    r"쿠폰",
    r"사은품",
    r"현재 구매 가능",
    r"재고",
    r"대표 모델 예시",
    r"모델 추천",
    r"⭐",
    r"원$",
    r"더 알아보기",
]

PROMO_QUESTION_HINTS = [
    "가격",
    "혜택",
    "재고",
    "구매",
    "할인",
    "쿠폰",
    "사은품",
    "price",
    "stock",
    "availability",
    "benefit",
    "discount",
    "coupon",
]

TOPIC_FAMILY_KEYWORDS = {
    "phone": ["갤럭시", "울트라", "플러스", "z fold", "z flip", "스마트폰", "phone", "smartphone", "s24", "s25", "s26"],
    "laptop": ["갤럭시북", "노트북", "북", "laptop", "notebook", "book4", "book5"],
    "earbuds": ["버즈", "buds", "이어버드", "이어폰", "earbuds", "earbud", "anc", "ip57"],
    "watch": ["갤럭시 워치", "워치", "watch", "smartwatch"],
    "tv": ["tv", "neo qled", "oled tv", "qled", "티비", "television"],
    "washer": ["세탁기", "건조기", "콤보", "washer", "dryer", "laundry"],
    "refrigerator": ["냉장고", "김치냉장고", "비스포크 냉장고", "refrigerator", "fridge"],
    "monitor": ["모니터", "odyssey", "smart monitor", "monitor"],
    "ring": ["갤럭시 링", "galaxy ring", "ring"],
}

TRUNCATED_ENDINGS = (
    ":",
    "보시는 게 .",
    "체감이 .",
    "하기 .",
    "좋아요 .",
    "매칭이 .",
    "더 알아보기",
)

MIN_CLEAN_ANSWER_LEN = 6


def normalize_text_for_diff(text: str) -> str:
    sanitized = re.sub(r"[\u200e\u200f\u202a-\u202e\ufeff]", "", str(text or ""))
    return " ".join(sanitized.replace("\xa0", " ").split())


def _normalize_text(text: str) -> str:
    return normalize_text_for_diff(text).lower()


def _is_question_repetition(question: str, answer: str) -> bool:
    nq = _normalize_text(question)
    na = _normalize_text(answer)
    if not nq or not na:
        return False
    if na == nq or na == f"{nq} , {nq}" or na == f"{nq}, {nq}":
        return True
    return nq in na and len(na) <= len(nq) * 1.4


def _detect_topic_family(text: str) -> str:
    normalized = _normalize_text(text)
    if not normalized:
        return "unknown"

    best_family = "unknown"
    best_score = 0
    for family, keywords in TOPIC_FAMILY_KEYWORDS.items():
        score = sum(1 for keyword in keywords if keyword in normalized)
        if score > best_score:
            best_family = family
            best_score = score
    return best_family if best_score > 0 else "unknown"


def _looks_truncated(answer: str) -> bool:
    normalized = _normalize_text(answer)
    if not normalized:
        return False
    if normalized.endswith(TRUNCATED_ENDINGS):
        return True
    return bool(re.search(r"(?:sm-[a-z0-9]+|\d{2,3}(?:,\d{3})+원)$", normalized))


def _question_allows_promo_text(question: str) -> bool:
    normalized_question = _normalize_text(question)
    return any(hint in normalized_question for hint in PROMO_QUESTION_HINTS)


def _strip_followup_cta(text: str) -> tuple[str, bool]:
    normalized = _normalize_multiline_text(text)
    if not normalized:
        return "", False

    kept_lines: list[str] = []
    stripped = False
    for line in normalized.splitlines():
        current = line.strip()
        if not current:
            continue
        earliest_match = None
        for pattern in FOLLOWUP_CTA_PATTERNS:
            match = re.search(pattern, current, re.IGNORECASE)
            if match is None:
                continue
            if earliest_match is None or match.start() < earliest_match.start():
                earliest_match = match
        if earliest_match is None:
            kept_lines.append(current)
            continue
        prefix = current[: earliest_match.start()].rstrip(" ,:;")
        if prefix:
            kept_lines.append(prefix)
        stripped = True
        break

    candidate = "\n".join(kept_lines).strip() if stripped else normalized
    earliest_match = None
    for pattern in FOLLOWUP_CTA_PATTERNS:
        match = re.search(pattern, candidate, re.IGNORECASE)
        if match is None:
            continue
        if earliest_match is None or match.start() < earliest_match.start():
            earliest_match = match
    if earliest_match is not None:
        prefix = candidate[: earliest_match.start()].rstrip(" ,:;")
        return prefix, True
    return candidate, stripped


def _strip_promo_review_blocks(text: str, question: str = "") -> tuple[str, bool]:
    normalized = normalize_text_for_diff(text)
    if not normalized or _question_allows_promo_text(question):
        return normalized, False

    kept_lines: list[str] = []
    stripped = False
    for line in str(text or "").splitlines():
        line_n = normalize_text_for_diff(line)
        if not line_n:
            continue
        if any(re.search(pattern, line_n, re.IGNORECASE) for pattern in PROMO_REVIEW_PATTERNS):
            stripped = True
            continue
        kept_lines.append(line_n)

    if kept_lines:
        return "\n".join(kept_lines).strip(), stripped

    if any(re.search(pattern, normalized, re.IGNORECASE) for pattern in PROMO_REVIEW_PATTERNS):
        for pattern in PROMO_REVIEW_PATTERNS:
            match = re.search(pattern, normalized, re.IGNORECASE)
            if not match:
                continue
            prefix = normalized[: match.start()].rstrip(" ,")
            if prefix and len(prefix) >= 20:
                return prefix, True
        return "", True
    return normalized, stripped


def _remove_promo_review_lines(text: str, question: str = "") -> str:
    return _strip_promo_review_blocks(text, question=question)[0]


def _strip_trailing_broken_sentence(text: str) -> str:
    normalized = _normalize_multiline_text(text)
    if not normalized or not _looks_truncated(normalized):
        return normalized

    sentence_breaks = [normalized.rfind(marker) for marker in (". ", "다. ", "요. ", "니다. ", "! ", "? ")]
    last_break = max(sentence_breaks)
    if last_break >= 0:
        trimmed = normalized[: last_break + 1].rstrip()
        if trimmed and not _looks_truncated(trimmed):
            return trimmed
    return normalized


def _clean_answer_candidate_details(text: str, question: str = "") -> dict[str, Any]:
    raw_answer = _normalize_multiline_text(text)
    if not raw_answer:
        return {
            "raw_answer": "",
            "cleaned_answer": "",
            "question_repetition_detected": False,
            "truncated_detected": False,
            "cta_stripped": False,
            "promo_stripped": False,
        }

    cleaned = raw_answer
    for marker in FOLLOW_UP_SPLIT_MARKERS:
        if marker in cleaned:
            cleaned = cleaned.split(marker, 1)[0].strip()

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
    had_followup_marker = any(marker in raw_answer for marker in FOLLOW_UP_SPLIT_MARKERS) or any(
        re.search(pattern, raw_answer, re.IGNORECASE) for pattern in FOLLOWUP_CTA_PATTERNS
    )

    question_repetition_detected = _is_question_repetition(question, cleaned)
    cta_stripped = False
    promo_stripped = False
    if question_repetition_detected:
        cleaned = ""
    else:
        cleaned, cta_stripped = _strip_followup_cta(cleaned)
        cleaned, promo_stripped = _strip_promo_review_blocks(cleaned, question=question)
        cleaned = _strip_trailing_broken_sentence(cleaned)
        cleaned = " ".join(cleaned.split()).strip()
        cta_stripped = cta_stripped or had_followup_marker

    truncated_detected = bool(cleaned) and _looks_truncated(cleaned)
    if truncated_detected:
        cleaned = ""
    elif cleaned and len(cleaned) < MIN_CLEAN_ANSWER_LEN:
        cleaned = ""

    return {
        "raw_answer": raw_answer,
        "cleaned_answer": cleaned,
        "question_repetition_detected": question_repetition_detected,
        "truncated_detected": truncated_detected,
        "cta_stripped": cta_stripped,
        "promo_stripped": promo_stripped,
    }


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


def _strip_meta_text(text: str, question: str = "") -> str:
    return _clean_answer_candidate_details(text, question=question)["cleaned_answer"]


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
    if not _strip_meta_text(question):
        return segments

    filtered: list[str] = []
    for segment in segments:
        normalized = _strip_meta_text(segment)
        if not normalized:
            continue
        if _is_question_repetition(question, normalized):
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


def choose_best_answer_segment(segments: list[str], question: str = "") -> str:
    return choose_best_answer_candidate(segments, question=question)["cleaned_answer"]


def choose_best_answer_candidate(segments: list[str], question: str = "") -> dict[str, Any]:
    filtered = filter_out_static_ui_text(segments)
    if not filtered:
        return _clean_answer_candidate_details("", question=question)
    best_candidate = _clean_answer_candidate_details("", question=question)
    best_score = -10**9
    for index, segment in enumerate(filtered):
        details = _clean_answer_candidate_details(segment, question=question)
        normalized = details["cleaned_answer"]
        raw_answer = details["raw_answer"]
        if not raw_answer:
            continue
        if looks_like_chat_history_dump(raw_answer) or looks_like_chat_history_dump(normalized):
            continue
        if details["question_repetition_detected"] or not normalized:
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
        if _looks_like_product_card(raw_answer):
            score -= 80
        if _looks_like_product_title(raw_answer):
            score -= 70
        if normalized.endswith("?"):
            score -= 30
        if len(normalized) <= 40 and normalized.endswith("?"):
            score -= 20
        if details["truncated_detected"]:
            score -= 25
        if score >= best_score:
            best_score = score
            best_candidate = details
    return best_candidate


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

    cleaned_candidates = [
        _clean_answer_candidate_details(segment, question=question)
        for segment in new_bot_by_count + new_bot_segments + new_history_segments + diff_segments
    ]
    question_repetition_detected = any(item["question_repetition_detected"] for item in cleaned_candidates)
    truncated_detected = any(item["truncated_detected"] for item in cleaned_candidates)

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

    selected_candidate = _clean_answer_candidate_details("", question=question)
    if all_candidates:
        selected_candidate = choose_best_answer_candidate(all_candidates, question=question)

    return {
        "answer": selected_candidate["cleaned_answer"],
        "raw_answer": selected_candidate["raw_answer"],
        "cleaned_answer": selected_candidate["cleaned_answer"],
        "question_repetition_detected": question_repetition_detected,
        "truncated_detected": truncated_detected or selected_candidate["truncated_detected"],
        "cta_stripped": selected_candidate["cta_stripped"],
        "promo_stripped": selected_candidate["promo_stripped"],
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
        "success": bool(candidate_data["cleaned_answer"]),
        "answer": candidate_data["cleaned_answer"],
        "raw_answer": candidate_data["raw_answer"],
        "cleaned_answer": candidate_data["cleaned_answer"],
        "question_repetition_detected": candidate_data["question_repetition_detected"],
        "truncated_detected": candidate_data["truncated_detected"],
        "cta_stripped": candidate_data["cta_stripped"],
        "promo_stripped": candidate_data["promo_stripped"],
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
