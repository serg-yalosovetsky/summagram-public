"""Stage 4: intent classification output model.

NOTE: person_name is intentionally absent here.
Entity resolution happens before this stage; the intent classifier
gets pre-resolved entities as context and only classifies the *type* of request.
"""

from __future__ import annotations

from pydantic import Field

from .common import BaseStageModel, QueryType


class QueryIntent(BaseStageModel):
    """LLM-classified intent with no entity extraction burden."""

    query_type: QueryType
    limit: int = Field(default=50, ge=1, le=500)
    # Keywords only — must NOT contain person/place names
    search_query: str | None = None
    wants_only_from_person: bool = False
    wants_summary: bool = False
    wants_media_links: bool = False
    reasoning_notes: list[str] = Field(default_factory=list)
