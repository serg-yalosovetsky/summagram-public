from __future__ import annotations

import json
from typing import Any

from etl.models import CreateSessionResult, RawDocumentRow, Session
from .core import get_db, row_to_session
from .raw_documents import _fetch_raw_documents


async def create_session(
    session_id: str,
    title: str,
    context_chat_id: int | None = None,
    meta: dict[str, Any] | None = None,
) -> CreateSessionResult:
    sql = """
        INSERT INTO sessions (id, title, context_chat_id, meta)
        VALUES ($1, $2, $3, $4::jsonb)
    """
    async with get_db() as conn:
        await conn.execute(
            sql,
            session_id,
            title,
            context_chat_id,
            json.dumps(meta, ensure_ascii=False) if meta else None,
        )

    return CreateSessionResult(id=session_id, title=title)


async def get_sessions(limit: int = 50, offset: int = 0) -> list[Session]:
    sql = """
        SELECT *
        FROM sessions
        ORDER BY updated_at DESC
        LIMIT $1 OFFSET $2
    """
    async with get_db() as conn:
        rows = await conn.fetch(sql, limit, offset)

    return [row_to_session(row) for row in rows]


async def get_session(session_id: str) -> Session | None:
    sql = "SELECT * FROM sessions WHERE id = $1"
    async with get_db() as conn:
        row = await conn.fetchrow(sql, session_id)

    return row_to_session(row) if row else None


async def update_session_title(session_id: str, title: str) -> None:
    sql = """
        UPDATE sessions
        SET title = $1,
            updated_at = CURRENT_TIMESTAMP
        WHERE id = $2
    """
    async with get_db() as conn:
        await conn.execute(sql, title, session_id)


async def get_session_messages(
    session_id: str,
    limit: int = 50,
    offset: int = 0,
) -> list[RawDocumentRow]:
    return await _fetch_raw_documents(
        conditions=["(metadata->>'session_id') = $1"],
        params=[session_id],
        limit=limit,
        offset=offset,
    )


async def insert_session_message(
    source_id: str,
    doc_id: str,
    content: str,
    timestamp: str,
    metadata: dict[str, Any],
) -> None:
    sql = """
        INSERT INTO raw_documents (source_id, doc_id, content, timestamp, metadata)
        VALUES ($1, $2, $3, $4, $5::jsonb)
    """
    async with get_db() as conn:
        await conn.execute(
            sql,
            source_id,
            doc_id,
            content,
            timestamp,
            json.dumps(metadata, ensure_ascii=False),
        )


async def update_session_updated_at(session_id: str) -> None:
    sql = """
        UPDATE sessions
        SET updated_at = CURRENT_TIMESTAMP
        WHERE id = $1
    """
    async with get_db() as conn:
        await conn.execute(sql, session_id)
