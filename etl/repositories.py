import json
from abc import ABC, abstractmethod
from typing import AsyncGenerator, Dict, Any, List, Optional
import aiosqlite
from loguru import logger

from etl.utils import format_sql


class DatabaseRepository(ABC):
    """
    Abstract base class for database operations.
    Decouples business logic from specific database implementations.
    """

    @abstractmethod
    async def connect(self):
        """Establish connection to the database."""
        pass

    @abstractmethod
    async def disconnect(self):
        """Close connection to the database."""
        pass

    @abstractmethod
    async def fetch_documents_for_reindex(
        self, media_types: List[str], force_reindex: bool
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """
        Fetch documents that need media reindexing.
        Yields dictionaries with document data.
        """
        pass

    @abstractmethod
    async def update_document_metadata(
        self, row_id: int, metadata: Dict[str, Any]
    ) -> None:
        """
        Update the metadata for a specific document by its internal row ID.
        """
        pass


class SQLiteRepository(DatabaseRepository):
    """
    SQLite implementation of the DatabaseRepository.
    """

    def __init__(self, db_path: str):
        self.db_path = db_path
        self.conn: Optional[aiosqlite.Connection] = None

    async def connect(self):
        if not self.conn:
            self.conn = await aiosqlite.connect(self.db_path)
            self.conn.row_factory = aiosqlite.Row
            logger.info(f"Connected to SQLite database: {self.db_path}")

    async def disconnect(self):
        if self.conn:
            await self.conn.close()
            self.conn = None
            logger.info("Disconnected from SQLite database")

    async def fetch_documents_for_reindex(
        self, media_types: List[str], force_reindex: bool
    ) -> AsyncGenerator[Dict[str, Any], None]:
        if not self.conn:
            raise RuntimeError("Database not connected")

        # Build the dynamic query based on input params
        # We use json_extract for efficient filtering on the database side

        # Prepare placeholders for IN clause
        placeholders = ",".join(["?"] * len(media_types))

        query = f"""
            SELECT id, source_id, doc_id, content, timestamp, metadata
            FROM raw_documents
            WHERE json_extract(metadata, '$.media.type') IN ({placeholders})
        """

        params: List[Any] = list(media_types)

        # Only consider documents that have a file on disk
        query += " AND json_extract(metadata, '$.media.path') IS NOT NULL AND json_extract(metadata, '$.media.path') != ''"

        # If not forcing reindex, filter out items that already have a description
        if not force_reindex:
            query += " AND (json_extract(metadata, '$.media.description') IS NULL OR json_extract(metadata, '$.media.description') = '')"

        logger.info(f"Executing reindex fetch query:\n{format_sql(query, params)}")

        async with self.conn.execute(query, params) as cursor:
            async for row in cursor:
                # Retrieve row data
                # SQLite returns rows as Row objects, accessible by key
                yield dict(row)

    async def update_document_metadata(
        self, row_id: int, metadata: Dict[str, Any]
    ) -> None:
        if not self.conn:
            raise RuntimeError("Database not connected")

        new_metadata_json = json.dumps(metadata)

        await self.conn.execute(
            "UPDATE raw_documents SET metadata = ? WHERE id = ?",
            (new_metadata_json, row_id),
        )
        await self.conn.commit()
