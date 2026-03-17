from __future__ import annotations

import re
from typing import Any

from etl.models import (
    Chat,
    ChatMessageStats,
    ChatSearchResult,
    Contact,
    GraphCacheRow,
)
from .core import get_db

# ---------------------------------------------------------------------------
# Transliteration tables for cross-script name matching
# ---------------------------------------------------------------------------

_LATIN_TO_CYRILLIC = {
    "a": "а",
    "b": "б",
    "v": "в",
    "g": "г",
    "d": "д",
    "e": "е",
    "zh": "ж",
    "z": "з",
    "i": "и",
    "j": "й",
    "k": "к",
    "l": "л",
    "m": "м",
    "n": "н",
    "o": "о",
    "p": "п",
    "r": "р",
    "s": "с",
    "t": "т",
    "u": "у",
    "f": "ф",
    "h": "х",
    "ts": "ц",
    "ch": "ч",
    "sh": "ш",
    "sch": "щ",
    "y": "ы",
    "yu": "ю",
    "ya": "я",
}

_CYRILLIC_TO_LATIN = {
    "а": "a",
    "б": "b",
    "в": "v",
    "г": "g",
    "д": "d",
    "е": "e",
    "ё": "e",
    "ж": "zh",
    "з": "z",
    "и": "i",
    "й": "j",
    "і": "i",
    "ї": "yi",
    "є": "ye",
    "к": "k",
    "л": "l",
    "м": "m",
    "н": "n",
    "о": "o",
    "п": "p",
    "р": "r",
    "с": "s",
    "т": "t",
    "у": "u",
    "ф": "f",
    "х": "h",
    "ц": "ts",
    "ч": "ch",
    "ш": "sh",
    "щ": "sch",
    "ъ": "",
    "ы": "y",
    "ь": "",
    "э": "e",
    "ю": "yu",
    "я": "ya",
}


def _latin_to_cyrillic(s: str) -> str:
    s = s.lower()
    res: list[str] = []
    i = 0
    while i < len(s):
        for length in (3, 2, 1):
            if i + length <= len(s):
                chunk = s[i : i + length]
                if chunk in _LATIN_TO_CYRILLIC:
                    res.append(_LATIN_TO_CYRILLIC[chunk])
                    i += length
                    break
        else:
            res.append(s[i])
            i += 1
    return "".join(res)


def _cyrillic_to_latin(s: str) -> str:
    s = s.lower()
    return "".join(_CYRILLIC_TO_LATIN.get(c, c) for c in s)


def _has_cyrillic(s: str) -> bool:
    return bool(re.search(r"[\u0400-\u04FF]", s))


def _normalize_cyrillic_russian(s: str) -> str:
    t = s.lower()
    for ua, ru in (("і", "и"), ("є", "е"), ("ї", "й")):
        t = t.replace(ua, ru)
    return t


def _normalize_cyrillic_ukrainian(s: str) -> str:
    t = s.lower()
    for ru, ua in (("и", "і"), ("е", "є"), ("й", "ї")):
        t = t.replace(ru, ua)
    return t


def _get_name_prefix(s: str) -> str:
    s = s.strip()
    return s if len(s) <= 4 else s[:4]


def _escape_like(s: str, escape_char: str = "\\") -> str:
    return (
        s.replace(escape_char, escape_char + escape_char)
        .replace("%", escape_char + "%")
        .replace("_", escape_char + "_")
    )


def build_multilingual_prefix_patterns(query: str) -> list[str]:
    """Build LIKE prefix patterns for cross-script name matching."""
    if not query or not query.strip():
        return []

    q = query.strip().lower()
    variants: set[str] = {q}

    if _has_cyrillic(q):
        variants.add(_cyrillic_to_latin(q))
        variants.add(_normalize_cyrillic_russian(q))
        variants.add(_normalize_cyrillic_ukrainian(q))
    else:
        cyr = _latin_to_cyrillic(q)
        variants.add(cyr)
        variants.add(_normalize_cyrillic_russian(cyr))
        variants.add(_normalize_cyrillic_ukrainian(cyr))

    prefixes = {_get_name_prefix(v) for v in variants if v}
    return [f"{_escape_like(prefix)}%" for prefix in prefixes]


# ---------------------------------------------------------------------------
# Upsert helper
# ---------------------------------------------------------------------------


async def _upsert_by_source_id(table: str, data: dict[str, Any]) -> None:
    if not data:
        raise ValueError(f"Cannot upsert empty payload into {table}")

    keys = list(data.keys())
    columns = ", ".join(keys)
    placeholders = ", ".join(f"${i}" for i in range(1, len(keys) + 1))
    values = [data[key] for key in keys]
    update_clause = ", ".join(
        f"{key} = EXCLUDED.{key}" for key in keys if key != "source_id"
    )

    sql = f"""
        INSERT INTO {table} ({columns})
        VALUES ({placeholders})
        ON CONFLICT (source_id) DO UPDATE
        SET {update_clause}
    """

    async with get_db() as conn:
        await conn.execute(sql, *values)


# ---------------------------------------------------------------------------
# Chat / Contact CRUD
# ---------------------------------------------------------------------------


async def save_chat(chat_data: dict | Chat) -> None:
    data = (
        chat_data.model_dump(exclude_none=True)
        if isinstance(chat_data, Chat)
        else chat_data
    )
    await _upsert_by_source_id("chats", data)


async def save_contact(contact_data: dict | Contact) -> None:
    data = (
        contact_data.model_dump(exclude_none=True)
        if isinstance(contact_data, Contact)
        else contact_data
    )
    await _upsert_by_source_id("contacts", data)


async def save_chat_member(chat_id: int, user_id: int) -> None:
    sql = """
        INSERT INTO chat_members (chat_id, user_id)
        VALUES ($1, $2)
        ON CONFLICT DO NOTHING
    """
    async with get_db() as conn:
        await conn.execute(sql, chat_id, user_id)


async def get_chat(source_id: int) -> Chat | None:
    sql = "SELECT * FROM chats WHERE source_id = $1"
    async with get_db() as conn:
        row = await conn.fetchrow(sql, source_id)
    return Chat(**dict(row)) if row else None


async def get_contact(source_id: int) -> Contact | None:
    sql = "SELECT * FROM contacts WHERE source_id = $1"
    async with get_db() as conn:
        row = await conn.fetchrow(sql, source_id)
    return Contact(**dict(row)) if row else None


async def get_chat_message_stats(chat_id: int, my_id: int) -> ChatMessageStats:
    sql = """
        SELECT
            COUNT(*) AS total,
            COUNT(*) FILTER (WHERE metadata->>'sender_id' = $2) AS me
        FROM raw_documents
        WHERE metadata->>'chat_id' = $1
    """
    async with get_db() as conn:
        row = await conn.fetchrow(sql, str(chat_id), str(my_id))

    return ChatMessageStats(
        total=row["total"] if row else 0,
        me=row["me"] if row else 0,
    )


async def get_chats(
    limit: int = 50,
    offset: int = 0,
    min_importance: float = 0.0,
) -> list[Chat]:
    sql = """
        SELECT *
        FROM chats
        WHERE importance_score >= $1
        ORDER BY importance_score DESC, message_count_me DESC
        LIMIT $2 OFFSET $3
    """
    async with get_db() as conn:
        rows = await conn.fetch(sql, min_importance, limit, offset)
    return [Chat(**dict(row)) for row in rows]


async def get_contacts(limit: int = 50, offset: int = 0) -> list[Contact]:
    sql = """
        SELECT *
        FROM contacts
        ORDER BY name ASC
        LIMIT $1 OFFSET $2
    """
    async with get_db() as conn:
        rows = await conn.fetch(sql, limit, offset)
    return [Contact(**dict(row)) for row in rows]


async def find_chats_by_contact_name(
    query: str,
    limit: int = 10,
) -> list[ChatSearchResult]:
    patterns = build_multilingual_prefix_patterns(query)
    if not patterns:
        return []

    sql = """
        SELECT
            ch.source_id AS chat_id,
            COALESCE(MAX(COALESCE(c.name, c.username)), ch.title, '') AS contact_name,
            COALESCE(ch.title, '') AS chat_title,
            COALESCE(ch.is_private, false) AS is_private
        FROM chats ch
        LEFT JOIN chat_members cm ON ch.source_id = cm.chat_id
        LEFT JOIN contacts c ON cm.user_id = c.source_id
        WHERE
            COALESCE(c.name, '') ILIKE ANY($1::text[])
            OR COALESCE(c.username, '') ILIKE ANY($1::text[])
            OR COALESCE(ch.title, '') ILIKE ANY($1::text[])
        GROUP BY ch.source_id, ch.title, ch.is_private
        ORDER BY ch.is_private DESC, ch.title ASC
        LIMIT $2
    """

    async with get_db() as conn:
        rows = await conn.fetch(sql, patterns, limit)

    return [ChatSearchResult(**dict(row)) for row in rows]


# ---------------------------------------------------------------------------
# Social graph
# ---------------------------------------------------------------------------


async def get_reply_interaction_freq() -> list[tuple[int, int, int]]:
    sql = """
        SELECT
            LEAST((r.metadata->>'sender_id')::bigint, (t.metadata->>'sender_id')::bigint) AS u1,
            GREATEST((r.metadata->>'sender_id')::bigint, (t.metadata->>'sender_id')::bigint) AS u2,
            COUNT(*) AS cnt
        FROM raw_documents r
        JOIN raw_documents t
            ON t.source_id = r.source_id
           AND t.doc_id = (r.metadata->>'reply_to_msg_id')
        WHERE r.metadata->>'reply_to_msg_id' IS NOT NULL
          AND r.metadata->>'sender_id' IS NOT NULL
          AND t.metadata->>'sender_id' IS NOT NULL
          AND r.metadata->>'sender_id' NOT IN ('me', 'assistant')
          AND t.metadata->>'sender_id' NOT IN ('me', 'assistant')
          AND (r.metadata->>'sender_id') ~ '^[0-9]+$'
          AND (t.metadata->>'sender_id') ~ '^[0-9]+$'
          AND (r.metadata->>'sender_id')::bigint != (t.metadata->>'sender_id')::bigint
        GROUP BY 1, 2
    """
    async with get_db() as conn:
        rows = await conn.fetch(sql)

    return [(int(row["u1"]), int(row["u2"]), int(row["cnt"])) for row in rows]


async def save_graph_cache(graph_json: str, node_count: int, edge_count: int) -> None:
    sql = """
        INSERT INTO social_graph_cache (graph_json, node_count, edge_count)
        VALUES ($1, $2, $3)
    """
    async with get_db() as conn:
        await conn.execute(sql, graph_json, node_count, edge_count)


async def get_latest_graph_cache() -> GraphCacheRow | None:
    sql = """
        SELECT *
        FROM social_graph_cache
        ORDER BY created_at DESC
        LIMIT 1
    """
    async with get_db() as conn:
        row = await conn.fetchrow(sql)
    return GraphCacheRow(**dict(row)) if row else None
