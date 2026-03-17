import os
from typing import AsyncGenerator, Any, Callable

import httpx
from loguru import logger

from etl.db.raw_documents import fetch_documents_for_reindex
from etl.models import (
    GenericDocument,
    ReindexParams,
    TelegramMetadata,
)
from etl.sources.base import BaseSource
from etl.sources.telegram import get_backend_url
from etl.utils import parse_timestamp

_MEDIA_TYPE_TO_TASK: dict[str, tuple[str, str]] = {
    "photo": ("analyze_image", "vision"),
    "audio": ("transcribe_audio", "audio"),
    "voice": ("transcribe_audio", "audio"),
    "document": ("analyze_pdf", "document"),
}


class MediaReindexSource(BaseSource):
    """
    Source for reindexing media files from the database.
    Enqueues processing tasks to the backend model scheduler
    instead of calling inference endpoints directly.
    """

    def __init__(self):
        self._current_job_id: str | None = None
        self._task_buffer: list[dict] = []

    def set_job_id(self, job_id: str) -> None:
        self._current_job_id = job_id

    @property
    def source_name(self) -> str:
        return "reindex_media"

    async def connect(self):
        pass

    async def disconnect(self):
        pass

    async def get_dialogs(self, limit: int = 100) -> list[dict[str, Any]]:
        return []

    async def _enqueue_task(
        self, media_type: str, source_id: str, doc_id: str, path: str
    ) -> None:
        """Buffer a processing task for the backend queue."""
        mapping = _MEDIA_TYPE_TO_TASK.get(media_type)
        if not mapping or not self._current_job_id:
            return
        task_subtype, model_type = mapping
        
        self._task_buffer.append(
            {
                "job_id": self._current_job_id,
                "model_type": model_type,
                "task_subtype": task_subtype,
                "source_id": source_id,
                "doc_id": doc_id,
                "input_path": path,
                "input_params": {},
            }
        )
        if len(self._task_buffer) >= 50:
            await self._flush_tasks()

    async def _flush_tasks(self) -> None:
        if not self._task_buffer:
            return
            
        tasks_to_send = self._task_buffer[:]
        self._task_buffer.clear()
        
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                await client.post(
                    get_backend_url("tasks/enqueue/bulk"),
                    json={"tasks": tasks_to_send},
                )
            logger.debug(f"Bulk enqueued {len(tasks_to_send)} tasks")
        except Exception as exc:
            logger.error(f"Failed to bulk enqueue tasks for reindex: {exc}")

    def _validate_metadata(
        self, metadata_dict: Any, doc_id: str
    ) -> TelegramMetadata | None:
        if not metadata_dict:
            return None

        try:
            return TelegramMetadata.model_validate(metadata_dict)
        except Exception as exc:
            logger.warning(f"Invalid metadata for doc {doc_id}: {exc}")
            return None

    async def _enqueue_media_if_exists(
        self,
        metadata: TelegramMetadata | None,
        source_id: str,
        doc_id: str,
    ) -> None:
        if not metadata or not metadata.media:
            return

        media = metadata.media
        if not media.type or not media.path:
            return

        if not os.path.exists(media.path):
            return

        await self._enqueue_task(media.type, source_id, doc_id, media.path)

    async def fetch(
        self,
        params: dict[str, Any],
        progress_callback: Callable[[str, float], None],
    ) -> AsyncGenerator[GenericDocument, None]:
        """
        Fetches media documents from database for reindexing.
        Instead of calling inference inline, enqueues tasks to the backend
        model scheduler. The manager._run_job three-phase pipeline
        will wait for tasks to complete and enrich documents.
        """
        try:
            reindex_params = ReindexParams(**params)
        except Exception as e:
            logger.error(f"Invalid parameters for reindex: {e}")
            progress_callback(f"Error: Invalid parameters: {e}", 0.0)
            return

        media_types = reindex_params.media_types
        force_reindex = reindex_params.force_reindex

        logger.info(
            f"Starting media reindexing for types: {media_types}, force={force_reindex}"
        )

        processed_count = 0

        async for row in fetch_documents_for_reindex(
            media_types, force_reindex
        ):
            processed_count += 1
            if processed_count % 10 == 0:
                progress_callback(f"Processed {processed_count} documents...", 0.5)

            metadata_dict = row.metadata
            doc_id = row.doc_id
            source_id = row.source_id or ""

            metadata = self._validate_metadata(metadata_dict, doc_id)
            if metadata_dict and metadata is None:
                continue

            await self._enqueue_media_if_exists(metadata, source_id, doc_id)

            timestamp = parse_timestamp(row.timestamp)

            doc = GenericDocument(
                source_id=source_id,
                doc_id=doc_id,
                content=row.content,
                timestamp=timestamp,
                metadata=metadata_dict,
            )
            yield doc

        await self._flush_tasks()

        progress_callback("Reindexing tasks enqueued", 1.0)
        logger.info(f"Enqueued reindex tasks for {processed_count} documents.")
