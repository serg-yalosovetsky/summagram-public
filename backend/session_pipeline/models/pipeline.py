"""Pipeline-level request/response and trace models."""

from __future__ import annotations

from pydantic import Field

from .common import BaseStageModel
from .stage0_normalize import NormalizedText
from .stage1_candidates import CandidateExtractionResult
from .stage2_entities import EntityResolutionResult
from .stage3_time import TimeParseResult
from .stage4_intent import QueryIntent


class SessionPipelineRequest(BaseStageModel):
    session_id: str
    user_text: str
    linked_chat_id: int | None = None
    max_limit: int = Field(default=100, ge=1, le=500)
    chat_history: list[dict] = Field(default_factory=list)


class SessionPipelineTrace(BaseStageModel):
    """Full trace of all pipeline stages for debugging / observability."""

    normalized: NormalizedText
    candidates: CandidateExtractionResult
    entities: EntityResolutionResult
    time_range: TimeParseResult
    intent: QueryIntent


class SessionPipelineResult(BaseStageModel):
    """Resolved entities + intent, ready for the fetch stage."""

    entities: EntityResolutionResult
    time_range: TimeParseResult
    intent: QueryIntent
    trace: SessionPipelineTrace | None = None
