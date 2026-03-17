"""
Stage 2: Entity resolution using pymorphy3 (RU/UK morphology) + RapidFuzz.

Pipeline per candidate:
1. Pymorphy3 → nominative lemma (handles all declension cases)
2. Build common prefix/translit variants
3. DB lookup via find_chats_by_contact_name (existing function)
4. RapidFuzz fuzzy fallback if DB returns nothing

Local imports pymorphy3 and rapidfuzz are intentional:
loaded lazily to avoid startup cost when NLP_PIPELINE_ENABLED=false.
"""

from __future__ import annotations

import asyncio

from loguru import logger

from backend.session_pipeline.models.common import EntityKind, LanguageCode
from backend.session_pipeline.models.stage0_normalize import NormalizedText
from backend.session_pipeline.models.stage1_candidates import CandidateExtractionResult
from backend.session_pipeline.models.stage2_entities import (
    ContactRef,
    EntityResolutionResult,
    ResolvedEntity,
)

_morph_ru = None
_morph_uk = None
_morph_initialized = False


def _init_morph() -> None:
    global _morph_ru, _morph_uk, _morph_initialized
    if _morph_initialized:
        return
    import pymorphy3  # noqa: PLC0415

    _morph_ru = pymorphy3.MorphAnalyzer(lang="ru")
    try:
        _morph_uk = pymorphy3.MorphAnalyzer(lang="uk")
    except Exception:
        _morph_uk = None
        logger.warning("pymorphy3 Ukrainian dictionary not available.")
    _morph_initialized = True


def _nominative(word: str, lang: LanguageCode) -> str:
    """Return nominative case form of word using pymorphy3."""
    _init_morph()
    morph = _morph_uk if lang == LanguageCode.UK and _morph_uk else _morph_ru
    if morph is None:
        return word.capitalize()
    try:
        parsed = morph.parse(word)
        if not parsed:
            return word.capitalize()
        best = parsed[0]
        inflected = best.inflect({"nomn"})
        if inflected:
            result = inflected.word
            return result[0].upper() + result[1:] if result else word.capitalize()
    except Exception:
        pass
    return word.capitalize()


def _translit_variants(name: str) -> list[str]:
    """Generate simple RU↔Latin transliteration variants for fuzzy matching."""
    _map: dict[str, str] = {
        "а": "a",
        "б": "b",
        "в": "v",
        "г": "h",
        "д": "d",
        "е": "ye",
        "є": "ye",
        "ж": "zh",
        "з": "z",
        "и": "y",
        "і": "i",
        "й": "y",
        "к": "k",
        "л": "l",
        "м": "m",
        "н": "n",
        "о": "o",
        "п": "p",
        "р": "r",
        "с": "s",
        "т": "t",
        "у": "u",
        "ф": "f",
        "х": "kh",
        "ц": "ts",
        "ч": "ch",
        "ш": "sh",
        "щ": "shch",
        "ы": "y",
        "э": "e",
        "ю": "yu",
        "я": "ya",
        "ї": "yi",
        "ґ": "g",
    }
    lower = name.lower()
    latin = "".join(_map.get(c, c) for c in lower)
    variants = [name]
    if latin != lower:
        variants.append(latin.capitalize())
    return variants


async def _db_lookup(name: str, limit: int = 5) -> list[dict]:
    """Look up contacts/chats by name via existing etl.db function."""
    from etl.db.chats import find_chats_by_contact_name  # noqa: PLC0415

    try:
        matches = await find_chats_by_contact_name(name, limit=limit)
        return [
            {"chat_id": m.chat_id, "display_name": getattr(m, "title", name)}
            for m in matches
        ]
    except Exception as exc:
        logger.warning(f"DB lookup failed for {name!r}: {exc}")
        return []


def _fuzzy_match(
    name: str, contacts: list[dict], threshold: float = 75.0
) -> dict | None:
    """RapidFuzz fuzzy match against a contact list."""
    from rapidfuzz import process, fuzz  # noqa: PLC0415

    if not contacts:
        return None
    names = [c.get("display_name", "") for c in contacts]
    result = process.extractOne(name, names, scorer=fuzz.WRatio)
    if result and result[1] >= threshold:
        idx = result[2]
        return contacts[idx]
    return None


class DefaultEntityResolver:
    """
    Resolves entity candidates:
    1. Nominative form via pymorphy3
    2. DB prefix match
    3. RapidFuzz fuzzy fallback
    """

    def __init__(self, fuzzy_threshold: float = 75.0) -> None:
        self._fuzzy_threshold = fuzzy_threshold

    async def resolve(
        self,
        text: NormalizedText,
        candidates: CandidateExtractionResult,
    ) -> EntityResolutionResult:
        lang = text.detected_language
        resolved: list[ResolvedEntity] = []

        for cand in candidates.candidates:
            # Only resolve persons; others pass through unmatched
            if cand.kind not in (EntityKind.PERSON, EntityKind.USERNAME):
                continue

            source_chain: list[str] = [cand.source]
            notes: list[str] = []

            # 1. Nominative form
            lemma = await asyncio.to_thread(_nominative, cand.raw_text, lang)
            source_chain.append("pymorphy3")
            notes.append(f"nominative: {cand.raw_text!r} → {lemma!r}")

            # 2. Translit variants
            translit = _translit_variants(lemma)
            prefix_variants = [lemma[: i + 1] for i in range(min(3, len(lemma)))]

            # 3. DB lookup (nominative first, then raw_text as fallback)
            matched_ref: ContactRef | None = None
            for lookup_name in [lemma] + translit:
                db_results = await _db_lookup(lookup_name)
                if db_results:
                    hit = db_results[0]
                    matched_ref = ContactRef(
                        chat_id=hit.get("chat_id"),
                        display_name=hit.get("display_name"),
                    )
                    source_chain.append("db_prefix")
                    notes.append(
                        f"DB match on {lookup_name!r}: chat_id={matched_ref.chat_id}"
                    )
                    break

            # 4. Fuzzy fallback if no DB hit
            if not matched_ref:
                all_contacts = await _db_lookup(lemma[:3], limit=50)
                fuzzy_hit = _fuzzy_match(lemma, all_contacts, self._fuzzy_threshold)
                if fuzzy_hit:
                    matched_ref = ContactRef(
                        chat_id=fuzzy_hit.get("chat_id"),
                        display_name=fuzzy_hit.get("display_name"),
                    )
                    source_chain.append("rapidfuzz")
                    notes.append(f"fuzzy match: {fuzzy_hit.get('display_name')!r}")
                else:
                    notes.append("no DB match found")

            resolved.append(
                ResolvedEntity(
                    kind=cand.kind,
                    raw_text=cand.raw_text,
                    normalized_text=lemma,
                    lemma=lemma,
                    translit_variants=translit,
                    prefix_variants=prefix_variants,
                    matched=matched_ref,
                    source_chain=source_chain,
                    resolution_notes=notes,
                    confidence=cand.confidence,
                )
            )

        # Elect primary_person: highest confidence PERSON with a DB match; fallback: highest conf
        persons = [e for e in resolved if e.kind == EntityKind.PERSON]
        primary = None
        if persons:
            with_match = [p for p in persons if p.matched]
            primary = (
                max(with_match, key=lambda p: p.confidence)
                if with_match
                else max(persons, key=lambda p: p.confidence)
            )

        return EntityResolutionResult(
            entities=resolved,
            primary_person=primary,
            primary_chat=None,
        )
