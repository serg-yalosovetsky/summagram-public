import os
import aiosqlite
from pydantic import BaseModel

from shared.config import Config


class SourceStatItem(BaseModel):
    """Document count for a single source."""

    source_id: str
    count: int


class SourceStatsResponse(BaseModel):
    """Stats grouped by source."""

    items: list[SourceStatItem] = []


async def get_db_size() -> str:
    """Returns human-readable database size."""
    if not os.path.exists(Config.DB_PATH):
        return "0 MB"
    size_bytes = os.path.getsize(Config.DB_PATH)
    return f"{size_bytes / (1024 * 1024):.2f} MB"


async def get_total_messages() -> int:
    """Returns total count of ingested messages/documents."""
    async with aiosqlite.connect(Config.DB_PATH) as db:
        async with db.execute("SELECT COUNT(*) FROM raw_documents") as cursor:
            row = await cursor.fetchone()
            return row[0] if row else 0


async def get_total_events() -> int:
    """Returns total count of extracted events."""
    async with aiosqlite.connect(Config.DB_PATH) as db:
        async with db.execute("SELECT COUNT(*) FROM unified_events") as cursor:
            row = await cursor.fetchone()
            return row[0] if row else 0


async def get_source_stats() -> SourceStatsResponse:
    """Returns stats grouped by source."""
    async with aiosqlite.connect(Config.DB_PATH) as db:
        async with db.execute(
            "SELECT source_id, COUNT(*) FROM raw_documents GROUP BY source_id"
        ) as cursor:
            rows = await cursor.fetchall()
            items = [
                SourceStatItem(source_id=str(row[0]), count=row[1]) for row in rows
            ]
            return SourceStatsResponse(items=items)
