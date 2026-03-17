"""Stage 1: candidate mention extraction output model."""

from __future__ import annotations

from pydantic import Field

from .common import BaseStageModel, ConfidenceMixin, EntityKind


class CandidateMention(BaseStageModel, ConfidenceMixin):
    """A single entity candidate as found in text (pre-resolution)."""

    kind: EntityKind
    raw_text: str
    start_char: int = 0
    end_char: int = 0
    # Which extractor produced this candidate: rules | natasha | languk | stanza
    source: str
    label: str | None = None
    context_window: str | None = None


class CandidateExtractionResult(BaseStageModel):
    """Aggregated output from all candidate extractors."""

    candidates: list[CandidateMention] = Field(default_factory=list)
    # debug: extractor_name -> list of debug strings
    debug: dict[str, list[str]] = Field(default_factory=dict)
