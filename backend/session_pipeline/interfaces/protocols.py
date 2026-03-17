"""Protocol interfaces for all NLP pipeline stages."""

from typing import Protocol

from backend.session_pipeline.models.stage0_normalize import NormalizedText
from backend.session_pipeline.models.stage1_candidates import CandidateExtractionResult
from backend.session_pipeline.models.stage2_entities import EntityResolutionResult
from backend.session_pipeline.models.stage3_time import TimeParseResult
from backend.session_pipeline.models.stage4_intent import QueryIntent


class TextNormalizer(Protocol):
    """Stage 0 — clean and tokenise raw user text."""

    async def normalize(self, text: str) -> NormalizedText: ...


class CandidateExtractor(Protocol):
    """Stage 1 — extract entity mention candidates from normalised text."""

    async def extract(self, text: NormalizedText) -> CandidateExtractionResult: ...


class EntityResolver(Protocol):
    """Stage 2 — resolve candidates to morphological lemmas and DB contacts."""

    async def resolve(
        self,
        text: NormalizedText,
        candidates: CandidateExtractionResult,
    ) -> EntityResolutionResult: ...


class TimeParser(Protocol):
    """Stage 3 — parse relative/absolute time expressions from text."""

    async def parse(self, text: NormalizedText) -> TimeParseResult: ...


class IntentClassifier(Protocol):
    """Stage 4 — classify query type given pre-resolved entities and time range."""

    async def classify(
        self,
        text: NormalizedText,
        entities: EntityResolutionResult,
        time_range: TimeParseResult,
    ) -> QueryIntent: ...
