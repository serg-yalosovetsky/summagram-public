"""
Stage 1: Composite candidate extractor.
Runs multiple extractors in priority order and deduplicates overlapping spans.
Order: rules (highest precision) → Natasha (RU) → lang-uk (UK) → fallback
"""

from __future__ import annotations

from loguru import logger

from backend.session_pipeline.models.common import LanguageCode
from backend.session_pipeline.models.stage0_normalize import NormalizedText
from backend.session_pipeline.models.stage1_candidates import (
    CandidateMention,
    CandidateExtractionResult,
)


def _overlaps(a: CandidateMention, b: CandidateMention) -> bool:
    """Check if two character spans overlap."""
    return a.start_char < b.end_char and b.start_char < a.end_char


def _dedupe_by_span(candidates: list[CandidateMention]) -> list[CandidateMention]:
    """
    Remove lower-confidence duplicates for overlapping spans.
    Stable sort: keep highest confidence for each overlapping group.
    """
    sorted_cands = sorted(candidates, key=lambda c: -c.confidence)
    kept: list[CandidateMention] = []
    for cand in sorted_cands:
        if not any(_overlaps(cand, k) for k in kept):
            kept.append(cand)
    # Restore chronological order
    kept.sort(key=lambda c: c.start_char)
    return kept


class CompositeCandidateExtractor:
    """
    Runs rules → Natasha → lang-uk in configured order.
    Language routing: Natasha for RU/MIXED, lang-uk for UK/MIXED.
    """

    def __init__(
        self,
        enable_natasha: bool = True,
        enable_languk: bool = False,
    ) -> None:
        self._enable_natasha = enable_natasha
        self._enable_languk = enable_languk

        # Local imports: lazy, to control startup cost
        from backend.session_pipeline.implementations.candidate_extractor_rules import (  # noqa: PLC0415
            RulesCandidateExtractor,
        )

        self._rules = RulesCandidateExtractor()

        if enable_natasha:
            from backend.session_pipeline.implementations.candidate_extractor_natasha import (  # noqa: PLC0415
                NatashaCandidateExtractor,
            )

            self._natasha = NatashaCandidateExtractor()
        else:
            self._natasha = None

        if enable_languk:
            from backend.session_pipeline.implementations.candidate_extractor_languk import (  # noqa: PLC0415
                LangUkCandidateExtractor,
            )

            self._languk = LangUkCandidateExtractor()
        else:
            self._languk = None

    async def extract(self, text: NormalizedText) -> CandidateExtractionResult:
        lang = text.detected_language
        all_candidates: list[CandidateMention] = []
        debug: dict[str, list[str]] = {}

        # 1. Rules — always run
        rules_result = await self._rules.extract(text)
        all_candidates.extend(rules_result.candidates)
        debug.update(rules_result.debug)

        # 2. Natasha — for Russian and mixed
        if self._natasha and lang in (
            LanguageCode.RU,
            LanguageCode.MIXED,
            LanguageCode.UNKNOWN,
        ):
            nat_result = await self._natasha.extract(text)
            all_candidates.extend(nat_result.candidates)
            debug.update(nat_result.debug)
            logger.debug(f"Natasha found {len(nat_result.candidates)} spans")

        # 3. lang-uk — for Ukrainian and mixed
        if self._languk and lang in (LanguageCode.UK, LanguageCode.MIXED):
            uk_result = await self._languk.extract(text)
            all_candidates.extend(uk_result.candidates)
            debug.update(uk_result.debug)
            logger.debug(f"lang-uk found {len(uk_result.candidates)} spans")

        deduped = _dedupe_by_span(all_candidates)
        return CandidateExtractionResult(candidates=deduped, debug=debug)
