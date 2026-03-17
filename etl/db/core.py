from __future__ import annotations

import os
import json
import asyncio
from contextlib import asynccontextmanager
from typing import Any, AsyncIterator

import asyncpg
from loguru import logger

from shared.config import Config
from utils import monitor_perf_async
from etl.models import RawDocumentRow, Session


def _parse_jsonish(val: object) -> dict[str, Any]:
    """Parse a value that might be str, dict, or None into a dict."""
    if val is None:
        return {}
    if isinstance(val, dict):
        return val
    if isinstance(val, str):
        try:
            return json.loads(val) if val else {}
        except Exception:
            return {}
    return {}


def row_to_raw_document(row: asyncpg.Record) -> RawDocumentRow:
    """Convert asyncpg.Record to RawDocumentRow with metadata parsing."""
    item = dict(row)
    item["metadata"] = _parse_jsonish(item.get("metadata"))
    return RawDocumentRow(**item)


def row_to_session(row: asyncpg.Record) -> Session:
    """Convert asyncpg.Record (or dict) to Session with meta JSONB parsing."""
    item = dict(row)
    item["meta"] = _parse_jsonish(item.get("meta")) or None
    return Session(**item)


class DatabasePoolManager:
    def __init__(self) -> None:
        self._pool: asyncpg.Pool | None = None
        self._pool_loop: asyncio.AbstractEventLoop | None = None

    def get_dsn(self) -> str:
        """Retrieve Postgres DSN with fail-fast validation."""
        dsn = getattr(Config, "POSTGRES_DSN", None) or os.getenv("POSTGRES_DSN")
        if not dsn:
            raise ValueError("POSTGRES_DSN is required to connect to PostgreSQL")
        return str(dsn)

    async def get_or_create_pool(self) -> asyncpg.Pool:
        current_loop = asyncio.get_running_loop()

        if self._pool is None or self._pool_loop != current_loop:
            # If the loop changed, we cannot safely close the old pool from the new loop
            # as it will raise RuntimeError(Future attached to different loop).
            if self._pool is not None:
                self._pool = None

            self._pool = await asyncpg.create_pool(
                dsn=self.get_dsn(),
                min_size=1,
                max_size=10,
                command_timeout=60,
            )
            self._pool_loop = current_loop

        return self._pool

    async def close(self) -> None:
        if self._pool is not None:
            await self._pool.close()
            self._pool = None
            self._pool_loop = None


db_manager = DatabasePoolManager()


@asynccontextmanager
async def get_db() -> AsyncIterator[asyncpg.Connection]:
    """Acquire a connection from the pool."""
    pool = await db_manager.get_or_create_pool()
    async with pool.acquire() as conn:
        yield conn


@asynccontextmanager
async def transaction() -> AsyncIterator[asyncpg.Connection]:
    """Acquire a connection and open a transaction."""
    pool = await db_manager.get_or_create_pool()
    async with pool.acquire() as conn:
        async with conn.transaction():
            yield conn


@monitor_perf_async
async def init_db() -> None:
    """Initialise the connection pool. (Migrations are run separately)."""
    await db_manager.get_or_create_pool()
