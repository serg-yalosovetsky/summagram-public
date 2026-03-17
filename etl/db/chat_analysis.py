"""
Repository for segment-based chat analysis DB operations.

All queries use the existing `get_db()` asyncpg connection pool — consistent
with the rest of etl/db/. No Piccolo ORM Table API is used here; we write
the tables via raw parameterised SQL, which is faster and more explicit.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

from loguru import logger

from etl.chat_analysis.models import (
    ChatParticipant,
    ChatSegment,
    ChatSegmentAnalysis,
    RawMessage,
)
from etl.db.core import get_db


# ---------------------------------------------------------------------------
# Chat messages (read-only from raw_documents)
# ---------------------------------------------------------------------------


async def get_raw_docs_for_chat(chat_id: int) -> list[RawMessage]:
    """
    Return all raw_documents for *chat_id* sorted ascending by timestamp.

    Matches on ``metadata->>'chat_id'`` (stored as string in JSONB), consistent
    with the existing convention in raw_documents.py.
    """
    sql = """
        SELECT doc_id, source_id, timestamp, content, metadata
        FROM raw_documents
        WHERE metadata->>'chat_id' = $1
        ORDER BY timestamp ASC
    """
    async with get_db() as conn:
        rows = await conn.fetch(sql, str(chat_id))

    messages: list[RawMessage] = []
    for row in rows:
        meta: dict[str, Any] = row["metadata"] or {}
        if isinstance(meta, str):
            try:
                meta = json.loads(meta)
            except Exception:
                meta = {}

        ts_raw = row["timestamp"]
        if isinstance(ts_raw, str):
            try:
                ts = datetime.fromisoformat(ts_raw)
            except ValueError:
                ts = datetime.now(timezone.utc)
        elif isinstance(ts_raw, datetime):
            ts = ts_raw
        else:
            ts = datetime.now(timezone.utc)

        sender_id_raw = meta.get("sender_id")
        sender_id: int | None = None
        if isinstance(sender_id_raw, int):
            sender_id = sender_id_raw
        elif isinstance(sender_id_raw, str):
            try:
                sender_id = int(sender_id_raw)
            except (ValueError, TypeError):
                sender_id = None

        messages.append(
            RawMessage(
                doc_id=row["doc_id"] or "",
                chat_id=chat_id,
                source_id=row["source_id"] or "",
                sender_id=sender_id,
                sender_name=meta.get("sender_name") or "Unknown",
                timestamp=ts,
                content=row["content"] or "",
                metadata=meta,
            )
        )

    return messages


async def get_chat_members_with_contacts(chat_id: int) -> list[ChatParticipant]:
    """
    Return all contacts that are members of *chat_id*.

    Joins chat_members → contacts to get display name and username.
    """
    sql = """
        SELECT
            c.source_id,
            COALESCE(c.name, c.username, 'Unknown') AS display_name,
            c.username
        FROM chat_members cm
        JOIN contacts c ON c.source_id = cm.user_id
        WHERE cm.chat_id = $1
        ORDER BY c.name ASC
    """
    async with get_db() as conn:
        rows = await conn.fetch(sql, chat_id)

    return [
        ChatParticipant(
            source_id=row["source_id"],
            display_name=row["display_name"],
            username=row["username"],
        )
        for row in rows
    ]


# ---------------------------------------------------------------------------
# chat_segments CRUD
# ---------------------------------------------------------------------------


async def replace_chat_segments(
    chat_id: int,
    segments: list[ChatSegment],
) -> dict[str, int]:
    """
    Atomically replace all segments for *chat_id*: delete old, insert new.

    Returns:
        Mapping of {segment_id: db_integer_id} for later use in
        save_segment_analysis.
    """
    upsert_sql = """
        INSERT INTO chat_segments (
            chat_id, segment_no,
            start_message_doc_id, end_message_doc_id,
            start_ts, end_ts,
            message_count, token_count_estimate,
            strategy, text_for_llm,
            created_at
        )
        VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11)
        ON CONFLICT (chat_id, segment_no) DO UPDATE SET
            start_message_doc_id = EXCLUDED.start_message_doc_id,
            end_message_doc_id = EXCLUDED.end_message_doc_id,
            start_ts = EXCLUDED.start_ts,
            end_ts = EXCLUDED.end_ts,
            message_count = EXCLUDED.message_count,
            token_count_estimate = EXCLUDED.token_count_estimate,
            strategy = EXCLUDED.strategy,
            text_for_llm = EXCLUDED.text_for_llm
        RETURNING id
    """

    segment_id_to_db_id: dict[str, int] = {}
    now_iso = datetime.now(timezone.utc).isoformat()
    seen_ids = []

    async with get_db() as conn:
        async with conn.transaction():
            for seg in segments:
                row = await conn.fetchrow(
                    upsert_sql,
                    seg.chat_id,
                    seg.segment_no,
                    seg.start_doc_id,
                    seg.end_doc_id,
                    seg.start_ts.isoformat(),
                    seg.end_ts.isoformat(),
                    seg.message_count,
                    seg.token_count_estimate,
                    seg.strategy,
                    seg.text_for_llm,
                    now_iso,
                )
                if row:
                    db_id = row["id"]
                    segment_id_to_db_id[seg.segment_id] = db_id
                    seen_ids.append(db_id)
            
            if seen_ids:
                # Clean up any leftover segments that aren't in the newly inserted payload
                # e.g. if the segmentation changed from 10 segments to 8 segments
                await conn.execute(
                    "DELETE FROM chat_segments WHERE chat_id = $1 AND id != ALL($2::int[])", 
                    chat_id, 
                    seen_ids
                )
            else:
                # If there are no segments, delete everything for the chat_id.
                await conn.execute("DELETE FROM chat_segments WHERE chat_id = $1", chat_id)


    logger.debug(
        "replace_chat_segments: chat={} inserted {} segments",
        chat_id,
        len(segment_id_to_db_id),
    )
    return segment_id_to_db_id


# ---------------------------------------------------------------------------
# chat_segment_analysis CRUD
# ---------------------------------------------------------------------------


async def save_segment_analysis(
    *,
    segment_db_id: int,
    model_name: str,
    model_version: str | None,
    analysis: ChatSegmentAnalysis,
) -> None:
    """Upsert the LLM analysis result for a single segment."""
    sql = """
        INSERT INTO chat_segment_analysis (
            segment_id, model_name, model_version,
            summary, topics, people, events, interests,
            places, relationship_signals, tone,
            importance_score, confidence, raw_json,
            created_at
        )
        VALUES (
            $1, $2, $3,
            $4, $5::jsonb, $6::jsonb, $7::jsonb, $8::jsonb,
            $9::jsonb, $10::jsonb, $11::jsonb,
            $12, $13, $14::jsonb,
            $15
        )
        ON CONFLICT (segment_id) DO UPDATE SET
            model_name         = EXCLUDED.model_name,
            model_version      = EXCLUDED.model_version,
            summary            = EXCLUDED.summary,
            topics             = EXCLUDED.topics,
            people             = EXCLUDED.people,
            events             = EXCLUDED.events,
            interests          = EXCLUDED.interests,
            places             = EXCLUDED.places,
            relationship_signals = EXCLUDED.relationship_signals,
            tone               = EXCLUDED.tone,
            importance_score   = EXCLUDED.importance_score,
            confidence         = EXCLUDED.confidence,
            raw_json           = EXCLUDED.raw_json
    """
    now_iso = datetime.now(timezone.utc).isoformat()

    def _j(obj: Any) -> str:
        return json.dumps(obj, ensure_ascii=False)

    async with get_db() as conn:
        await conn.execute(
            sql,
            segment_db_id,
            model_name,
            model_version,
            analysis.summary,
            _j([t.model_dump(mode="json") for t in analysis.topics]),
            _j([p.model_dump(mode="json") for p in analysis.people]),
            _j([e.model_dump(mode="json") for e in analysis.events]),
            _j([i.model_dump(mode="json") for i in analysis.interests]),
            _j(analysis.places),
            _j([r.model_dump(mode="json") for r in analysis.relationship_signals]),
            _j(analysis.emotional_tone),
            analysis.importance_score,
            analysis.confidence,
            _j(analysis.model_dump(mode="json")),
            now_iso,
        )


# ---------------------------------------------------------------------------
# unified_events upsert
# ---------------------------------------------------------------------------


async def upsert_unified_events(
    chat_id: int,
    events: list[dict[str, Any]],
) -> None:
    """
    Upsert extracted event candidates into unified_events.

    Deduplication key: (title, event_type, chat_id stored in payload).
    Simple ON CONFLICT DO NOTHING — no complex merge.
    """
    if not events:
        return

    sql = """
        INSERT INTO unified_events (event_type, start_time, end_time, title, payload, source_id)
        VALUES ($1, $2, $3, $4, $5::jsonb, $6)
        ON CONFLICT DO NOTHING
    """
    now_iso = datetime.now(timezone.utc).isoformat()

    async with get_db() as conn:
        async with conn.transaction():
            for event in events:
                payload = {
                    "chat_id": chat_id,
                    "participants": event.get("participants", []),
                    "location_text": event.get("location_text"),
                    "confidence": event.get("confidence"),
                }
                await conn.execute(
                    sql,
                    event.get("event_type", "other"),
                    event.get("start_time") or now_iso,
                    event.get("end_time") or now_iso,
                    event.get("title", "Untitled event"),
                    json.dumps(payload, ensure_ascii=False),
                    str(chat_id),
                )
