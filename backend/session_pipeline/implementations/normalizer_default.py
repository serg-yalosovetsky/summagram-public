"""
Stage 0 implementation: lightweight rule-based text normalisation.
No ML — pure regex. Fast, deterministic, deployable without GPU.
"""

from __future__ import annotations

import re
import unicodedata

from backend.session_pipeline.models.common import LanguageCode
from backend.session_pipeline.models.stage0_normalize import NormalizedText

# Match Telegram/generic @usernames
_RE_USERNAME = re.compile(r"@[\w\d_]+")
# Match URLs (http/https/bare domains)
_RE_URL = re.compile(r"https?://\S+|www\.\S+", re.IGNORECASE)
# Match standalone numbers (incl. digit words used for time: 5, 10, 14)
_RE_NUMBER = re.compile(r"\b\d+\b")

# Cyrillic character ranges for language detection
_CYRILLIC_CHARS = frozenset(
    "абвгдеёжзийклмнопрстуфхцчшщъыьэюяАБВГДЕЁЖЗИЙКЛМНОПРСТУФХЦЧШЩЪЫЬЭЮЯ"
)
# Ukrainian-specific chars (not in Russian)
_UK_SPECIFIC = frozenset("іїєґІЇЄҐ")


def _detect_language(text: str) -> LanguageCode:
    """Heuristic RU/UK/EN/MIXED detection. Checks Ukrainian-specific chars."""
    cyrillic = sum(1 for c in text if c in _CYRILLIC_CHARS)
    uk_specific = sum(1 for c in text if c in _UK_SPECIFIC)
    latin = sum(1 for c in text if c.isalpha() and c.isascii())

    if cyrillic == 0 and latin > 0:
        return LanguageCode.EN
    if cyrillic > 0 and latin > 0:
        return LanguageCode.MIXED
    if uk_specific >= 1:
        return LanguageCode.UK
    if cyrillic > 0:
        return LanguageCode.RU
    return LanguageCode.UNKNOWN


def _remove_control_chars(text: str) -> str:
    """Strip Unicode control characters while preserving printable ones."""
    return "".join(
        c for c in text if unicodedata.category(c)[0] not in ("C",) or c in "\n\t "
    )


class DefaultTextNormalizer:
    """
    Lightweight regex-based text normaliser.

    Steps:
    1. Strip control characters.
    2. Normalise whitespace.
    3. Extract @usernames, URLs, numbers.
    4. Detect language.
    5. Simple whitespace tokenisation on the cleaned text.
    """

    async def normalize(self, text: str) -> NormalizedText:
        cleaned = _remove_control_chars(text).strip()
        # Collapse runs of whitespace
        cleaned = re.sub(r"[ \t]+", " ", cleaned)

        usernames = _RE_USERNAME.findall(cleaned)
        urls = _RE_URL.findall(cleaned)
        numbers = _RE_NUMBER.findall(cleaned)

        # Build a version usable for NER (remove URLs to reduce noise)
        normalized = _RE_URL.sub(" ", cleaned).strip()
        lowered = normalized.lower()

        tokens = lowered.split()
        lang = _detect_language(normalized)

        return NormalizedText(
            raw_text=text,
            normalized_text=normalized,
            lowered_text=lowered,
            detected_language=lang,
            tokens=tokens,
            usernames=[u.lstrip("@") for u in usernames],
            urls=urls,
            numbers=numbers,
            notes=[],
        )
