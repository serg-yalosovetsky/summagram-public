"""
Stage 1 implementation: rule-based candidate extraction.
Covers: @username mentions, common RU/UK phrase patterns for asking about a person.
No ML — deterministic Python. Runs first in the composite extractor.
"""

from __future__ import annotations

import re

from backend.session_pipeline.models.common import EntityKind
from backend.session_pipeline.models.stage0_normalize import NormalizedText
from backend.session_pipeline.models.stage1_candidates import (
    CandidateMention,
    CandidateExtractionResult,
)

# ---------------------------------------------------------------------------
# Phrase patterns
# Each captures a name in group 1. Case-insensitive, word-boundary aware.
# ---------------------------------------------------------------------------

# RU/UK asking-about patterns: "що задала Аліса", "что просил Лев", "що писав Льоша"
_RE_THEMATIC = re.compile(
    r"(?:що|что|чого|кого|кому|якщо|если|яку|яке|який|которую|которое|который)"
    r"\s+\w+\s+([А-ЯІЇЄҐA-Z][а-яіїєґёa-z]+)",
    re.IGNORECASE | re.UNICODE,
)

# "від Аліси", "у Льва", "с Игорем", "з Андрієм"
_RE_PREPOSITION_NAME = re.compile(
    r"(?:від|если|з\b|с\b|у\b|від|у\s|для|with|from)\s+([А-ЯІЇЄҐA-Z][а-яіїєґёa-z]+)",
    re.IGNORECASE | re.UNICODE,
)

# "link from Bob", "message from Ivan", "files from Nat"
_RE_FROM_EN = re.compile(
    r"(?:from|by|sent by)\s+([A-Z][a-z]+)",
    re.IGNORECASE,
)

# Direct name mention: "Аліса", "Лев", standalone capital-initial Cyrillic word ≥3 chars
# Only applied when surrounded by whitespace/punctuation (not inside a sentence word).
_RE_STANDALONE_NAME = re.compile(
    r"(?<!\w)([А-ЯІЇЄҐ][а-яіїєґё]{2,})(?!\w)",
    re.UNICODE,
)

_USERNAME_RE = re.compile(r"@([\w\d_]+)")


def _make_mention(
    text: str,
    raw: str,
    start: int,
    end: int,
    source: str = "rules",
    confidence: float = 0.9,
    kind: EntityKind = EntityKind.PERSON,
) -> CandidateMention:
    ctx_start = max(0, start - 20)
    ctx_end = min(len(text), end + 20)
    return CandidateMention(
        kind=kind,
        raw_text=raw,
        start_char=start,
        end_char=end,
        source=source,
        confidence=confidence,
        context_window=text[ctx_start:ctx_end],
    )


class RulesCandidateExtractor:
    """
    Rule-based entity candidate extractor.
    High precision for @username and common RU/UK asking-about patterns.
    Called first in the composite extractor.
    """

    async def extract(self, text: NormalizedText) -> CandidateExtractionResult:
        src = text.normalized_text
        candidates: list[CandidateMention] = []
        debug_msgs: list[str] = []

        # 1. @username (high confidence)
        for m in _USERNAME_RE.finditer(src):
            candidates.append(
                _make_mention(
                    src,
                    m.group(1),
                    m.start(),
                    m.end(),
                    "rules",
                    0.95,
                    EntityKind.USERNAME,
                )
            )
            debug_msgs.append(f"@username: {m.group(0)!r}")

        # 2. Thematic asking patterns (що задала X, что просил X)
        for m in _RE_THEMATIC.finditer(src):
            name = m.group(1)
            start = m.start(1)
            candidates.append(
                _make_mention(src, name, start, start + len(name), "rules", 0.9)
            )
            debug_msgs.append(f"thematic pattern: {name!r}")

        # 3. Preposition + name (від Аліси, з Льовом)
        for m in _RE_PREPOSITION_NAME.finditer(src):
            name = m.group(1)
            start = m.start(1)
            candidates.append(
                _make_mention(src, name, start, start + len(name), "rules", 0.85)
            )
            debug_msgs.append(f"preposition pattern: {name!r}")

        # 4. English "from X" patterns
        for m in _RE_FROM_EN.finditer(src):
            name = m.group(1)
            start = m.start(1)
            candidates.append(
                _make_mention(src, name, start, start + len(name), "rules", 0.85)
            )
            debug_msgs.append(f"from-EN pattern: {name!r}")

        # 5. Standalone capitalised Cyrillic name (lowest priority rules)
        # Only add if nothing found yet from more specific patterns
        existing_spans = {(c.start_char, c.end_char) for c in candidates}
        for m in _RE_STANDALONE_NAME.finditer(src):
            name = m.group(1)
            start, end = m.start(1), m.end(1)
            if (start, end) not in existing_spans:
                candidates.append(_make_mention(src, name, start, end, "rules", 0.7))
                debug_msgs.append(f"standalone name: {name!r}")

        return CandidateExtractionResult(
            candidates=candidates,
            debug={"rules": debug_msgs},
        )
