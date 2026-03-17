"""Pydantic models for segment-based chat analysis pipeline."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Segment-level extraction models
# ---------------------------------------------------------------------------


class TopicRef(BaseModel):
    label: str
    kind: Literal["topic", "interest", "activity"] = "topic"
    confidence: float = Field(ge=0.0, le=1.0)
    evidence_quotes: list[str] = Field(default_factory=list)


class PersonRef(BaseModel):
    source_id: int | None = None
    display_name: str
    role: Literal[
        "self",
        "contact",
        "friend",
        "teacher",
        "colleague",
        "family",
        "client",
        "unknown",
    ] = "unknown"
    confidence: float = Field(ge=0.0, le=1.0)


class EventCandidate(BaseModel):
    title: str
    event_type: Literal[
        "meeting",
        "interview",
        "lesson",
        "trip",
        "debt",
        "payment",
        "reminder",
        "other",
    ]
    start_time: datetime | None = None
    end_time: datetime | None = None
    location_text: str | None = None
    participants: list[str] = Field(default_factory=list)
    confidence: float = Field(ge=0.0, le=1.0)


class RelationshipSignal(BaseModel):
    from_person: str
    to_person: str
    relation_type: Literal[
        "friend",
        "colleague",
        "teacher",
        "client",
        "family",
        "romantic",
        "unknown",
    ]
    signal: str
    weight: float = Field(ge=0.0, le=1.0)


class ChatSegmentAnalysis(BaseModel):
    segment_id: str
    summary: str
    topics: list[TopicRef] = Field(default_factory=list)
    people: list[PersonRef] = Field(default_factory=list)
    interests: list[TopicRef] = Field(default_factory=list)
    events: list[EventCandidate] = Field(default_factory=list)
    places: list[str] = Field(default_factory=list)
    relationship_signals: list[RelationshipSignal] = Field(default_factory=list)
    emotional_tone: list[str] = Field(default_factory=list)
    importance_score: float = Field(default=0.0, ge=0.0, le=1.0)
    confidence: float = Field(default=0.5, ge=0.0, le=1.0)


# ---------------------------------------------------------------------------
# Chat / Contact aggregate models
# ---------------------------------------------------------------------------


class ChatAggregateAnalysis(BaseModel):
    chat_id: int
    title: str
    description: str
    tags: list[str] = Field(default_factory=list)
    dominant_topics: list[str] = Field(default_factory=list)
    recurring_interests: list[str] = Field(default_factory=list)
    key_people: list[str] = Field(default_factory=list)
    detected_event_count: int = 0
    relationship_type: Literal[
        "private_friend",
        "private_teacher",
        "private_colleague",
        "private_client",
        "group_interest",
        "group_work",
        "unknown",
    ] = "unknown"
    importance_score: float = Field(default=0.0, ge=0.0, le=1.0)
    confidence: float = Field(default=0.5, ge=0.0, le=1.0)


class ContactAggregateAnalysis(BaseModel):
    contact_id: int
    display_name: str
    description: str
    interests: list[str] = Field(default_factory=list)
    relation_to_me: Literal[
        "friend",
        "colleague",
        "teacher",
        "client",
        "family",
        "romantic",
        "unknown",
    ] = "unknown"
    recurring_topics: list[str] = Field(default_factory=list)
    confidence: float = Field(default=0.5, ge=0.0, le=1.0)


# ---------------------------------------------------------------------------
# Data transfer objects (no Pydantic overhead, just dataclasses)
# ---------------------------------------------------------------------------


@dataclass(slots=True)
class ChatParticipant:
    source_id: int
    display_name: str
    username: str | None = None
    is_self: bool = False


@dataclass(slots=True)
class RawMessage:
    doc_id: str
    chat_id: int
    source_id: str
    sender_id: int | None
    sender_name: str
    timestamp: datetime
    content: str
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class ChatSegment:
    segment_id: str          # "{chat_id}:{segment_no}"
    chat_id: int
    segment_no: int
    start_doc_id: str
    end_doc_id: str
    start_ts: datetime
    end_ts: datetime
    message_count: int
    token_count_estimate: int
    strategy: str            # 'time_gap' | 'max_msgs' | 'token_budget' | 'final'
    messages: list[RawMessage]
    text_for_llm: str
