"""
Stage 1: lang-uk Transformer NER extractor for Ukrainian text.
Uses lang-uk/roberta-large-ner-uk from HuggingFace.

Feature-flagged via NLP_LANGUK_NER_ENABLED (default False) because:
- Large model (~1.3GB) needs initial download
- Cold-start is slow the first time (subsequent runs are fast with cache)
- Ukrainian coverage from rules + pymorphy3-dicts-uk is good fallback

Local imports are intentional: transformers + torch are heavy dependencies
loaded only when the flag is on.
"""

from __future__ import annotations

import asyncio

from loguru import logger

from backend.session_pipeline.models.common import EntityKind
from backend.session_pipeline.models.stage0_normalize import NormalizedText
from backend.session_pipeline.models.stage1_candidates import (
    CandidateMention,
    CandidateExtractionResult,
)

_MODEL_NAME = "lang-uk/roberta-large-ner-uk"
_languk_pipeline = None
_languk_initialized = False

# HuggingFace NER label -> EntityKind
_LABEL_MAP: dict[str, EntityKind] = {
    "B-PER": EntityKind.PERSON,
    "I-PER": EntityKind.PERSON,
    "B-LOC": EntityKind.PLACE,
    "I-LOC": EntityKind.PLACE,
    "B-ORG": EntityKind.ORG,
    "I-ORG": EntityKind.ORG,
}


def _init_languk() -> None:
    """Lazy initialisation of the HuggingFace pipeline."""
    global _languk_initialized, _languk_pipeline
    if _languk_initialized:
        return
    # Local imports: heavy model, loaded once
    from transformers import pipeline as hf_pipeline  # noqa: PLC0415

    _languk_pipeline = hf_pipeline(
        "ner",
        model=_MODEL_NAME,
        aggregation_strategy="first",
        device=-1,  # CPU; change to 0 for GPU
    )
    _languk_initialized = True
    logger.info(f"lang-uk NER model loaded: {_MODEL_NAME}")


def _run_languk_sync(text: str) -> list[CandidateMention]:
    """Run lang-uk NER synchronously (called via to_thread)."""
    _init_languk()
    assert _languk_pipeline is not None

    results = _languk_pipeline(text)
    candidates: list[CandidateMention] = []
    for ent in results:
        entity_group: str = ent.get("entity_group", "") or ent.get("entity", "")
        kind = _LABEL_MAP.get(entity_group, EntityKind.PERSON)
        word: str = ent.get("word", "")
        start: int = ent.get("start", 0)
        end: int = ent.get("end", start + len(word))
        score: float = float(ent.get("score", 0.8))
        ctx_start = max(0, start - 20)
        ctx_end = min(len(text), end + 20)
        candidates.append(
            CandidateMention(
                kind=kind,
                raw_text=word,
                start_char=start,
                end_char=end,
                source="languk",
                label=entity_group,
                confidence=score,
                context_window=text[ctx_start:ctx_end],
            )
        )
    return candidates


class LangUkCandidateExtractor:
    """
    Ukrainian Transformer NER using lang-uk/roberta-large-ner-uk.
    Only invoked when language is UK or MIXED and NLP_LANGUK_NER_ENABLED=true.
    """

    async def extract(self, text: NormalizedText) -> CandidateExtractionResult:
        try:
            candidates = await asyncio.to_thread(_run_languk_sync, text.normalized_text)
        except Exception as exc:
            logger.warning(f"lang-uk NER failed: {exc}")
            return CandidateExtractionResult(
                candidates=[],
                debug={"languk": [f"ERROR: {exc}"]},
            )

        return CandidateExtractionResult(
            candidates=candidates,
            debug={"languk": [f"found {len(candidates)} entities"]},
        )
