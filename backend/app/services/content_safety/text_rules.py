from __future__ import annotations

import re
import unicodedata
from collections import Counter

from app.services.content_safety.policy import TextSafetyResult

_URL_RE = re.compile(r"https?://|www\.", re.IGNORECASE)
_REPEATED_CHAR_RE = re.compile(r"(.)\1{11,}", re.IGNORECASE)
_PROMPT_INJECTION_RE = re.compile(
    r"(ignore (all )?(previous|prior) (instructions|prompts)|"
    r"you are now|system prompt|reveal (the )?system|"
    r"تجاهل (ال)?تعليمات|ignorez les instructions)",
    re.IGNORECASE,
)


def evaluate_text_rules(description: str | None) -> TextSafetyResult | None:
    """Return a terminal deterministic result, or None when Bedrock should run."""
    normalized = _normalize(description)
    if normalized is None:
        return TextSafetyResult(reason_code="TEXT_TOO_SHORT", severity="medium")
    if len(normalized) < 3:
        return TextSafetyResult(reason_code="TEXT_TOO_SHORT", severity="medium")

    letters = [ch for ch in normalized if unicodedata.category(ch).startswith("L")]
    if letters and len(set(letters)) / max(len(letters), 1) < 0.08 and len(letters) >= 20:
        return TextSafetyResult(reason_code="TEXT_GARBAGE", severity="high")

    symbol_count = sum(1 for ch in normalized if not ch.isalnum() and not ch.isspace())
    if len(normalized) >= 20 and symbol_count / len(normalized) > 0.55:
        return TextSafetyResult(reason_code="TEXT_GARBAGE", severity="high")

    if normalized.count("\ufffd") >= 8:
        return TextSafetyResult(reason_code="TEXT_GARBAGE", severity="high")

    if len(_URL_RE.findall(normalized)) >= 3:
        return TextSafetyResult(reason_code="TEXT_SPAM_LINKS", severity="high")

    if _REPEATED_CHAR_RE.search(normalized):
        return TextSafetyResult(reason_code="TEXT_REPETITION", severity="high")

    words = [part for part in re.split(r"\s+", normalized) if part]
    if len(words) >= 8:
        counts = Counter(words)
        top_word, top_count = counts.most_common(1)[0]
        if len(top_word) >= 3 and top_count / len(words) >= 0.6:
            return TextSafetyResult(reason_code="TEXT_REPETITION", severity="high")

    if _PROMPT_INJECTION_RE.search(normalized):
        # Not a reject: a civic report may quote abusive text. Staff should look.
        return TextSafetyResult(
            reason_code="TEXT_PROMPT_INJECTION",
            severity="medium",
            confidence=0.6,
        )
    return None


def _normalize(description: str | None) -> str | None:
    if description is None:
        return None
    collapsed = " ".join(description.replace("\x00", " ").split())
    return collapsed or None
