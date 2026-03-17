from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from typing import Any, AsyncGenerator, Sequence

from etl.models import (
    DownloadedRange,
    GenericDocument,
    RawDocumentRow,
    SaveMessageResult,
)
from .core import get_db, row_to_raw_document

RAW_DOCUMENTS_SELECT = """
    SELECT content, timestamp, source_id, metadata, doc_id
    FROM raw_documents
"""

NOT_UI_SESSION_SQL = "(source_id IS NULL OR source_id != 'ui_session')"
NOT_FROM_ME_SQL = "LOWER(COALESCE(metadata->>'is_from_me', 'false')) IN ('0', 'false')"


def _add_param(params: list[Any], value: Any) -> str:
    """Append *value* to the params list and return a ``$N`` placeholder."""
    params.append(value)
    return f"${len(params)}"


def _where_clause(conditions: Sequence[str]) -> str:
    cleaned = [c.strip() for c in conditions if c and c.strip()]
    return " AND ".join(cleaned) if cleaned else "TRUE"


def _escape_like(s: str, escape_char: str = "\\") -> str:
    """Escape ``%`` and ``_`` for use in a LIKE pattern."""
    return (
        s.replace(escape_char, escape_char + escape_char)
        .replace("%", escape_char + "%")
        .replace("_", escape_char + "_")
    )


def _contains_pattern(query: str) -> str:
    return f"%{_escape_like(query)}%"


async def _fetch_raw_documents(
    *,
    conditions: Sequence[str] = (),
    params: Sequence[Any] = (),
    limit: int = 50,
    offset: int = 0,
    newest_first: bool = True,
    reverse_result: bool = True,
) -> list[RawDocumentRow]:
    """Shared fetch helper with parameterised ``$N`` placeholders."""
    bind_params = list(params)
    limit_ph = _add_param(bind_params, limit)
    offset_ph = _add_param(bind_params, offset)

    sql = f"""
        {RAW_DOCUMENTS_SELECT}
        WHERE {_where_clause(conditions)}
        ORDER BY timestamp {"DESC" if newest_first else "ASC"}
        LIMIT {limit_ph} OFFSET {offset_ph}
    """

    async with get_db() as conn:
        rows = await conn.fetch(sql, *bind_params)

    result = [row_to_raw_document(row) for row in rows]
    if newest_first and reverse_result:
        result.reverse()
    return result


# ---------------------------------------------------------------------------
# CRUD
# ---------------------------------------------------------------------------


async def save_raw_documents(docs: list[GenericDocument]) -> None:
    if not docs:
        return

    sql = """
        INSERT INTO raw_documents (source_id, doc_id, content, timestamp, metadata)
        VALUES ($1, $2, $3, $4, $5::jsonb)
        ON CONFLICT (source_id, doc_id) DO NOTHING
    """
    args = [
        (
            doc.source_id,
            doc.doc_id,
            doc.content,
            doc.timestamp.isoformat(),
            json.dumps(doc.metadata, ensure_ascii=False),
        )
        for doc in docs
    ]

    async with get_db() as conn:
        await conn.executemany(sql, args)


async def update_raw_document(
    source_id: str,
    doc_id: str,
    content: str,
    metadata: dict[str, Any],
) -> None:
    sql = """
        UPDATE raw_documents
        SET content = $1,
            metadata = $2::jsonb
        WHERE source_id = $3
          AND doc_id = $4
    """
    async with get_db() as conn:
        await conn.execute(
            sql,
            content,
            json.dumps(metadata, ensure_ascii=False),
            source_id,
            doc_id,
        )


async def get_recent_raw_messages(limit: int = 30) -> list[RawDocumentRow]:
    return await _fetch_raw_documents(limit=limit)


# ---------------------------------------------------------------------------
# Download ranges / indexed status
# ---------------------------------------------------------------------------


async def get_downloaded_ranges(chat_id: int) -> list[DownloadedRange]:
    sql = """
        SELECT start_date, end_date
        FROM download_ranges
        WHERE chat_id = $1
        ORDER BY start_date
    """
    async with get_db() as conn:
        rows = await conn.fetch(sql, str(chat_id))

    return [
        DownloadedRange(start_date=row["start_date"], end_date=row["end_date"])
        for row in rows
    ]


async def add_downloaded_range(chat_id: int, start: datetime, end: datetime) -> None:
    sql = """
        INSERT INTO download_ranges (chat_id, start_date, end_date)
        VALUES ($1, $2, $3)
    """
    async with get_db() as conn:
        await conn.execute(sql, str(chat_id), start.isoformat(), end.isoformat())


async def get_indexed_status(doc_ids: list[str]) -> set[str]:
    if not doc_ids:
        return set()

    sql = """
        SELECT doc_id
        FROM indexed_documents
        WHERE doc_id = ANY($1::text[])
    """
    async with get_db() as conn:
        rows = await conn.fetch(sql, doc_ids)

    return {row["doc_id"] for row in rows}


async def mark_as_indexed(docs: list[GenericDocument]) -> None:
    if not docs:
        return

    sql = """
        INSERT INTO indexed_documents (source_id, doc_id)
        VALUES ($1, $2)
        ON CONFLICT DO NOTHING
    """
    args = [(doc.source_id, doc.doc_id) for doc in docs]

    async with get_db() as conn:
        await conn.executemany(sql, args)


# ---------------------------------------------------------------------------
# Chat history queries
# ---------------------------------------------------------------------------


async def get_chat_history(
    chat_id: int,
    limit: int = 50,
    offset: int = 0,
    since_timestamp: str | None = None,
) -> list[RawDocumentRow]:
    params: list[Any] = []
    conditions: list[str] = [
        f"(metadata->>'chat_id') = {_add_param(params, str(chat_id))}"
    ]

    if since_timestamp:
        conditions.append(f"timestamp >= {_add_param(params, since_timestamp)}")

    return await _fetch_raw_documents(
        conditions=conditions,
        params=params,
        limit=limit,
        offset=offset,
    )


async def get_last_messages_any_chat(
    limit: int = 1,
    since_timestamp: str | None = None,
) -> list[RawDocumentRow]:
    params: list[Any] = []
    conditions = [
        "(metadata->>'chat_id') IS NOT NULL",
        NOT_UI_SESSION_SQL,
    ]

    if since_timestamp:
        conditions.append(f"timestamp >= {_add_param(params, since_timestamp)}")

    return await _fetch_raw_documents(
        conditions=conditions,
        params=params,
        limit=limit,
        offset=0,
    )


async def get_last_message_any_chat() -> RawDocumentRow | None:
    rows = await get_last_messages_any_chat(limit=1)
    return rows[0] if rows else None


async def save_message(
    chat_id: int,
    role: str,
    content: str,
    sender_name: str = "Assistant",
) -> SaveMessageResult:
    timestamp = datetime.now(timezone.utc).isoformat()
    doc_id = f"msg_{uuid.uuid4().hex}"
    metadata = {
        "chat_id": chat_id,
        "sender_id": "me" if role == "user" else "assistant",
        "sender_name": sender_name,
        "is_from_me": role == "user",
    }

    sql = """
        INSERT INTO raw_documents (source_id, doc_id, content, timestamp, metadata)
        VALUES ($1, $2, $3, $4, $5::jsonb)
        ON CONFLICT (source_id, doc_id) DO NOTHING
    """
    async with get_db() as conn:
        await conn.execute(
            sql,
            "ui_chat",
            doc_id,
            content,
            timestamp,
            json.dumps(metadata, ensure_ascii=False),
        )

    return SaveMessageResult(doc_id=doc_id, timestamp=timestamp)


# ---------------------------------------------------------------------------
# Media type helpers
# ---------------------------------------------------------------------------


def _media_type_condition(media_type: str | None) -> str | None:
    if media_type == "text":
        return "metadata->'media' IS NULL"
    if media_type == "photo":
        return "(metadata->'media'->>'type') = 'photo'"
    if media_type == "audio":
        return "(metadata->'media'->>'type') IN ('audio', 'voice')"
    if media_type == "video":
        return "(metadata->'media'->>'type') = 'video'"
    if media_type == "document":
        return "(metadata->'media'->>'type') = 'document'"
    return None


async def get_all_documents(
    limit: int = 50,
    offset: int = 0,
    media_type: str | None = None,
) -> list[RawDocumentRow]:
    conditions: list[str] = []
    media_condition = _media_type_condition(media_type)
    if media_condition:
        conditions.append(media_condition)

    return await _fetch_raw_documents(
        conditions=conditions,
        limit=limit,
        offset=offset,
    )


async def get_document_counts_by_type() -> dict[str, int]:
    sql = """
        SELECT
            COUNT(*) AS all_count,
            COUNT(*) FILTER (WHERE metadata->'media' IS NULL) AS text_count,
            COUNT(*) FILTER (WHERE metadata->'media'->>'type' = 'photo') AS photo_count,
            COUNT(*) FILTER (WHERE metadata->'media'->>'type' IN ('audio', 'voice')) AS audio_count,
            COUNT(*) FILTER (WHERE metadata->'media'->>'type' = 'video') AS video_count,
            COUNT(*) FILTER (WHERE metadata->'media'->>'type' = 'document') AS document_count
        FROM raw_documents
    """
    async with get_db() as conn:
        row = await conn.fetchrow(sql)

    return {
        "all": row["all_count"] if row else 0,
        "text": row["text_count"] if row else 0,
        "photo": row["photo_count"] if row else 0,
        "audio": row["audio_count"] if row else 0,
        "video": row["video_count"] if row else 0,
        "document": row["document_count"] if row else 0,
    }


async def get_raw_documents_by_ids(
    specs: list[tuple[str, str]],
) -> list[RawDocumentRow]:
    if not specs:
        return []

    params: list[Any] = []
    tuple_placeholders: list[str] = []

    for source_id, doc_id in specs:
        src_ph = _add_param(params, source_id)
        doc_ph = _add_param(params, doc_id)
        tuple_placeholders.append(f"({src_ph}, {doc_ph})")

    sql = f"""
        {RAW_DOCUMENTS_SELECT}
        WHERE (source_id, doc_id) IN ({", ".join(tuple_placeholders)})
        ORDER BY timestamp ASC
    """

    async with get_db() as conn:
        rows = await conn.fetch(sql, *params)

    return [row_to_raw_document(row) for row in rows]


# ---------------------------------------------------------------------------
# Search
# ---------------------------------------------------------------------------


async def search_documents_by_media(
    query: str,
    chat_id: int | None = None,
    limit: int = 50,
) -> list[RawDocumentRow]:
    params: list[Any] = []
    pattern = _contains_pattern(query)

    conditions = [
        "metadata->'media' IS NOT NULL",
        (
            "("
            f"COALESCE(metadata->'media'->>'description', '') ILIKE {_add_param(params, pattern)} "
            f"OR COALESCE(metadata->'media'->>'type', '') ILIKE {_add_param(params, pattern)}"
            ")"
        ),
    ]

    if chat_id is not None:
        conditions.append(
            f"(metadata->>'chat_id') = {_add_param(params, str(chat_id))}"
        )

    return await _fetch_raw_documents(
        conditions=conditions,
        params=params,
        limit=limit,
        offset=0,
    )


async def get_recent_messages_from_others(
    chat_id: int | None = None,
    limit: int = 50,
    since_timestamp: str | None = None,
) -> list[RawDocumentRow]:
    params: list[Any] = []
    conditions = [
        NOT_FROM_ME_SQL,
        NOT_UI_SESSION_SQL,
    ]

    if chat_id is not None:
        conditions.append(
            f"(metadata->>'chat_id') = {_add_param(params, str(chat_id))}"
        )

    if since_timestamp:
        conditions.append(f"timestamp >= {_add_param(params, since_timestamp)}")

    return await _fetch_raw_documents(
        conditions=conditions,
        params=params,
        limit=limit,
        offset=0,
    )


async def get_surrounding_messages(
    chat_id: int,
    doc_id: str,
    window: int = 5,
) -> list[RawDocumentRow]:
    target_sql = """
        SELECT content, timestamp, source_id, metadata, doc_id
        FROM raw_documents
        WHERE metadata->>'chat_id' = $1
          AND doc_id = $2
    """

    async with get_db() as conn:
        target_row = await conn.fetchrow(target_sql, str(chat_id), doc_id)
        if not target_row:
            return []

        ts = target_row["timestamp"]

        before_sql = """
            SELECT content, timestamp, source_id, metadata, doc_id
            FROM raw_documents
            WHERE metadata->>'chat_id' = $1
              AND timestamp < $2
            ORDER BY timestamp DESC
            LIMIT $3
        """
        after_sql = """
            SELECT content, timestamp, source_id, metadata, doc_id
            FROM raw_documents
            WHERE metadata->>'chat_id' = $1
              AND timestamp > $2
            ORDER BY timestamp ASC
            LIMIT $3
        """

        before_rows = await conn.fetch(before_sql, str(chat_id), ts, window)
        after_rows = await conn.fetch(after_sql, str(chat_id), ts, window)

    all_rows = list(reversed(before_rows)) + [target_row] + list(after_rows)
    return [row_to_raw_document(row) for row in all_rows]


async def search_messages_from_others(
    chat_id: int | None,
    query: str,
    limit: int = 50,
    since: str | None = None,
) -> list[RawDocumentRow]:
    params: list[Any] = []
    pattern = _contains_pattern(query)

    conditions = [
        NOT_FROM_ME_SQL,
        NOT_UI_SESSION_SQL,
        f"content ILIKE {_add_param(params, pattern)}",
    ]

    if chat_id is not None:
        conditions.append(
            f"(metadata->>'chat_id') = {_add_param(params, str(chat_id))}"
        )

    if since is not None:
        conditions.append(f"timestamp >= {_add_param(params, since)}")

    return await _fetch_raw_documents(
        conditions=conditions,
        params=params,
        limit=limit,
        offset=0,
    )


async def get_recent_messages(
    chat_id: int | None = None,
    limit: int = 50,
) -> list[RawDocumentRow]:
    params: list[Any] = []
    conditions: list[str] = []

    if chat_id is not None:
        conditions.append(
            f"(metadata->>'chat_id') = {_add_param(params, str(chat_id))}"
        )

    return await _fetch_raw_documents(
        conditions=conditions,
        params=params,
        limit=limit,
        offset=0,
    )


async def fetch_documents_for_reindex(
    media_types: list[str], force_reindex: bool
) -> AsyncGenerator[RawDocumentRow, None]:
    if not media_types:
        return

    params: list[Any] = []
    
    placeholders = []
    for m in media_types:
        params.append(m)
        placeholders.append(f"${len(params)}")
    
    in_clause = ", ".join(placeholders)

    conditions = [
        f"metadata->'media'->>'type' IN ({in_clause})",
        "metadata->'media'->>'path' IS NOT NULL",
        "metadata->'media'->>'path' != ''"
    ]

    if not force_reindex:
        conditions.append(
            "(metadata->'media'->>'description' IS NULL OR metadata->'media'->>'description' = '')"
        )
        
    where_clause = " AND ".join(conditions)

    sql = f"""
        SELECT content, timestamp, source_id, metadata, doc_id
        FROM raw_documents
        WHERE {where_clause}
    """

    async with get_db() as conn:
        async with conn.transaction():
            async for row in conn.cursor(sql, *params):
                yield row_to_raw_document(row)
