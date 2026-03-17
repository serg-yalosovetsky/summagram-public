"""
Prompt builders for segment-based chat analysis.

All prompts enforce JSON-only output to keep parsing reliable and token usage
predictable. No "assistant wisdom" soft prose requested from the model.
"""
from __future__ import annotations

from collections import Counter
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict

from etl.chat_analysis.models import (
    ChatAggregateAnalysis,
    ChatParticipant,
    ChatSegment,
    ChatSegmentAnalysis,
    ContactAggregateAnalysis,
)


# ---------------------------------------------------------------------------
# System prompts
# ---------------------------------------------------------------------------

SEGMENT_SYSTEM_PROMPT = """
You analyze one segment of a Telegram chat.

Goal:
Extract structured information for search, tagging, event detection, and graph building.

Rules:
1. Return ONLY valid JSON matching the schema. No prose, no markdown, no explanation.
2. Do not invent facts not present in the messages.
3. Prefer explicit evidence over guesses.
4. If uncertain, lower confidence instead of hallucinating.
5. "topics" are conversation themes.
6. "interests" are stable preferences, hobbies, or recurring affinities.
7. "events" are concrete planned or discussed meetings/actions tied to time or place.
8. "relationship_signals" only if the segment contains direct evidence.
9. Ignore trivial filler like "+", "ok", single emoji unless it changes meaning.
10. Media descriptions in text (e.g. [PHOTO] ..., [AUDIO TRANSCRIPT] ...) are evidence.
""".strip()

AGGREGATE_CHAT_SYSTEM_PROMPT = """
You aggregate multiple structured segment analyses from the same Telegram chat.

Goal:
Produce a stable chat-level description and tags for:
- chat list UI display
- graph building
- contact understanding
- later retrieval

Rules:
1. Return ONLY valid JSON matching the schema.
2. Base conclusions on repeated or strong signals across segments.
3. Prefer stable themes over one-off mentions.
4. Tags must be concrete and retrieval-friendly (e.g. "english-lessons" not "communication").
5. Do NOT include vague tags like "communication", "messages", "chatting", "friendship".
6. For private chats, infer relationship_type only when evidence is sufficient.
7. detected_event_count must equal the total from segment data, not invented.
""".strip()

CONTACT_SYSTEM_PROMPT = """
You aggregate all signals related to one contact across multiple chat segments.

Goal:
Produce a compact profile useful for social graph and retrieval.

Rules:
1. Return ONLY valid JSON matching the schema.
2. Interests must be stable and recurring across multiple segments.
3. Relationship label must be conservative (prefer "unknown" over speculation).
4. Do not infer sensitive personal attributes unless explicitly discussed.
5. Prefer descriptive, neutral wording for the description.
""".strip()


# ---------------------------------------------------------------------------
# Prompt Payload Models
# ---------------------------------------------------------------------------


class ParticipantPayload(BaseModel):
    source_id: int
    display_name: str
    username: str | None = None
    is_self: bool


class SegmentMetadataPayload(BaseModel):
    segment_id: str
    segment_no: int
    start_ts: str
    end_ts: str
    message_count: int
    strategy: str


class SegmentPromptPayload(BaseModel):
    chat_title: str
    chat_type: Literal["private", "group"]
    participants: list[ParticipantPayload]
    segment_metadata: SegmentMetadataPayload
    messages: str
    return_schema: dict[str, Any]


class SegmentSummaryPayload(BaseModel):
    segment_id: str
    summary: str
    topics: list[str]
    interests: list[str]
    events: list[str]
    emotional_tone: list[str]
    importance_score: float


class ChatAggregatePromptPayload(BaseModel):
    chat_id: int
    title: str
    chat_type: Literal["private", "group"]
    segment_count: int
    topic_frequencies: list[tuple[str, int]]
    interest_frequencies: list[tuple[str, int]]
    people_frequencies: list[tuple[str, int]]
    detected_event_count: int
    segment_summaries: list[SegmentSummaryPayload]
    return_schema: dict[str, Any]


class RelationshipSignalPayload(BaseModel):
    model_config = ConfigDict(
        populate_by_name=True,
        alias_generator=lambda x: (
            "from" if x == "from_person"
            else "to" if x == "to_person"
            else "type" if x == "relation_type"
            else x
        ),
    )

    from_person: str
    to_person: str
    relation_type: str
    signal: str


class ContactSegmentPayload(BaseModel):
    summary: str
    topics: list[str]
    interests: list[str]
    relationship_signals: list[RelationshipSignalPayload]


class ContactInfoPayload(BaseModel):
    source_id: int
    display_name: str
    username: str | None = None


class ContactAggregatePromptPayload(BaseModel):
    contact: ContactInfoPayload
    relevant_segment_count: int
    segments: list[ContactSegmentPayload]
    return_schema: dict[str, Any]


# ---------------------------------------------------------------------------
# Prompt builders
# ---------------------------------------------------------------------------


def build_segment_prompt(
    *,
    title: str,
    is_private: bool,
    participants: list[ChatParticipant],
    segment: ChatSegment,
) -> list[dict]:
    """Build the ChatML message list for per-segment LLM extraction."""
    participants_payload = [
        ParticipantPayload(
            source_id=p.source_id,
            display_name=p.display_name,
            username=p.username,
            is_self=p.is_self,
        )
        for p in participants
    ]

    user_payload = SegmentPromptPayload(
        chat_title=title,
        chat_type="private" if is_private else "group",
        participants=participants_payload,
        segment_metadata=SegmentMetadataPayload(
            segment_id=segment.segment_id,
            segment_no=segment.segment_no,
            start_ts=segment.start_ts.isoformat(),
            end_ts=segment.end_ts.isoformat(),
            message_count=segment.message_count,
            strategy=segment.strategy,
        ),
        messages=segment.text_for_llm,
        return_schema=ChatSegmentAnalysis.model_json_schema(),
    )

    return [
        {"role": "system", "content": SEGMENT_SYSTEM_PROMPT},
        {"role": "user", "content": user_payload.model_dump_json(by_alias=True)},
    ]


def build_chat_aggregate_prompt(
    *,
    chat_id: int,
    title: str,
    is_private: bool,
    segment_results: list[ChatSegmentAnalysis],
) -> list[dict]:
    """Build the ChatML message list for chat-level aggregation."""
    topic_counter: Counter[str] = Counter()
    interest_counter: Counter[str] = Counter()
    people_counter: Counter[str] = Counter()
    event_count = 0

    for item in segment_results:
        for t in item.topics:
            topic_counter[t.label] += 1
        for i in item.interests:
            interest_counter[i.label] += 1
        for p in item.people:
            people_counter[p.display_name] += 1
        event_count += len(item.events)

    payload = ChatAggregatePromptPayload(
        chat_id=chat_id,
        title=title,
        chat_type="private" if is_private else "group",
        segment_count=len(segment_results),
        topic_frequencies=topic_counter.most_common(20),
        interest_frequencies=interest_counter.most_common(20),
        people_frequencies=people_counter.most_common(20),
        detected_event_count=event_count,
        segment_summaries=[
            SegmentSummaryPayload(
                segment_id=s.segment_id,
                summary=s.summary,
                topics=[t.label for t in s.topics],
                interests=[i.label for i in s.interests],
                events=[e.title for e in s.events],
                emotional_tone=s.emotional_tone,
                importance_score=s.importance_score,
            )
            for s in segment_results
        ],
        return_schema=ChatAggregateAnalysis.model_json_schema(),
    )

    return [
        {"role": "system", "content": AGGREGATE_CHAT_SYSTEM_PROMPT},
        {"role": "user", "content": payload.model_dump_json(by_alias=True)},
    ]


def build_contact_aggregate_prompt(
    *,
    contact: ChatParticipant,
    segment_results: list[ChatSegmentAnalysis],
) -> list[dict]:
    """Build the ChatML message list for per-contact profile aggregation."""
    relevant_segments = [
        ContactSegmentPayload(
            summary=s.summary,
            topics=[t.label for t in s.topics],
            interests=[i.label for i in s.interests],
            relationship_signals=[
                RelationshipSignalPayload(
                    from_person=r.from_person,
                    to_person=r.to_person,
                    relation_type=r.relation_type,
                    signal=r.signal,
                )
                for r in s.relationship_signals
                if contact.display_name in (r.from_person, r.to_person)
            ],
        )
        for s in segment_results
        if any(
            p.display_name == contact.display_name or p.source_id == contact.source_id
            for p in s.people
        )
    ]

    payload = ContactAggregatePromptPayload(
        contact=ContactInfoPayload(
            source_id=contact.source_id,
            display_name=contact.display_name,
            username=contact.username,
        ),
        relevant_segment_count=len(relevant_segments),
        segments=relevant_segments,
        return_schema=ContactAggregateAnalysis.model_json_schema(),
    )

    return [
        {"role": "system", "content": CONTACT_SYSTEM_PROMPT},
        {"role": "user", "content": payload.model_dump_json(by_alias=True)},
    ]
