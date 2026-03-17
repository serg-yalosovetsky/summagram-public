"""Stage 2: entity resolution output model."""

from __future__ import annotations

from pydantic import Field

from .common import BaseStageModel, ConfidenceMixin, EntityKind


class ContactRef(BaseStageModel):
    """Reference to a matched contact or chat in the DB."""

    contact_id: int | None = None
    chat_id: int | None = None
    display_name: str | None = None
    username: str | None = None


class ResolvedEntity(BaseStageModel, ConfidenceMixin):
    """A candidate mention after morphological normalisation and DB matching."""

    kind: EntityKind
    raw_text: str
    normalized_text: str
    lemma: str | None = None
    translit_variants: list[str] = Field(default_factory=list)
    prefix_variants: list[str] = Field(default_factory=list)
    matched: ContactRef | None = None
    # Ordered list of processing steps, e.g. ["rules", "pymorphy3", "rapidfuzz"]
    source_chain: list[str] = Field(default_factory=list)
    resolution_notes: list[str] = Field(default_factory=list)


class EntityResolutionResult(BaseStageModel):
    """All resolved entities for a single user turn."""

    entities: list[ResolvedEntity] = Field(default_factory=list)
    primary_person: ResolvedEntity | None = None
    primary_chat: ResolvedEntity | None = None
