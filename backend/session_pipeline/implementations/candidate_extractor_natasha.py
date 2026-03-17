"""
Stage 1: Natasha NER extractor for Russian text.
Uses Natasha + Slovnet under the hood (no GPU required, CPU-only).
Wrapped in asyncio.to_thread since Natasha pipeline is synchronous.

Local import of natasha is intentional: it's a heavy optional dependency
loaded only when NLP_PIPELINE_ENABLED=true.
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

_natasha_initialized = False
_segmenter = None
_ner_tagger = None

# Natasha NER label -> our EntityKind
_LABEL_MAP: dict[str, EntityKind] = {
    "PER": EntityKind.PERSON,
    "LOC": EntityKind.PLACE,
    "ORG": EntityKind.ORG,
}


def _init_natasha() -> None:
    """Lazy initialisation — imported on first use to avoid slow startup."""
    global _natasha_initialized, _segmenter, _ner_tagger
    if _natasha_initialized:
        return
    # Local imports: heavy model loading, done once
    from natasha import Segmenter, NewsNERTagger, NewsEmbedding  # noqa: PLC0415

    emb = NewsEmbedding()
    _segmenter = Segmenter()
    _ner_tagger = NewsNERTagger(emb)
    _natasha_initialized = True
    logger.info("Natasha NER model loaded.")


def _run_natasha_sync(text: str) -> list[CandidateMention]:
    """Run Natasha NER synchronously (called via to_thread)."""
    _init_natasha()

    from natasha import Doc  # noqa: PLC0415

    assert _segmenter is not None and _ner_tagger is not None  # set by _init_natasha

    doc = Doc(text)
    doc.segment(_segmenter)
    doc.tag_ner(_ner_tagger)

    candidates: list[CandidateMention] = []
    for span in doc.spans:
        kind = _LABEL_MAP.get(span.type, EntityKind.PERSON)
        ctx_start = max(0, span.start - 20)
        ctx_end = min(len(text), span.stop + 20)
        candidates.append(
            CandidateMention(
                kind=kind,
                raw_text=span.text,
                start_char=span.start,
                end_char=span.stop,
                source="natasha",
                label=span.type,
                confidence=0.85,
                context_window=text[ctx_start:ctx_end],
            )
        )
    return candidates


class NatashaCandidateExtractor:
    """
    Natasha-based NER for Russian text.
    Only invoked when language is RU or MIXED.
    """

    async def extract(self, text: NormalizedText) -> CandidateExtractionResult:
        try:
            candidates = await asyncio.to_thread(
                _run_natasha_sync, text.normalized_text
            )
        except Exception as exc:
            logger.warning(f"Natasha NER failed: {exc}")
            return CandidateExtractionResult(
                candidates=[],
                debug={"natasha": [f"ERROR: {exc}"]},
            )

        return CandidateExtractionResult(
            candidates=candidates,
            debug={"natasha": [f"found {len(candidates)} spans"]},
        )
