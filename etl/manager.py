import asyncio
import json
import re
import uuid
from datetime import datetime
from typing import Dict, Any, Optional, List

import httpx

from etl.db.raw_documents import (
    get_indexed_status,
    mark_as_indexed,
    save_raw_documents,
    update_raw_document,
    get_raw_documents_by_ids,
)
from etl.processing.extractor import extract_and_save
from etl.processing.indexer import update_index
from etl.schemas import JobStatusResponse
from etl.sources.base import BaseSource
from etl.sources.media_reindex_source import MediaReindexSource
from etl.sources.telegram import TelegramSource, get_backend_url

from etl.models import (
    GenericDocument,
    TelegramMediaMetadata,
    ImageAnalysisResponse,
    AudioTranscriptionResponse,
    PDFAnalysisResponse,
)

from loguru import logger

BATCH_SAVE_SIZE = 20
TASK_POLL_INTERVAL = 2.0


class JobState:
    def __init__(self, job_id: str, source: str):
        self.job_id = job_id
        self.source = source
        self.status = "queued"
        self.progress = 0.0
        self.message = "Queued"
        self.error = None
        self.result = None


class JobManager:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(JobManager, cls).__new__(cls)
            cls._instance.jobs = {}  # type: Dict[str, JobState]
            cls._instance._tasks = {}  # type: Dict[str, asyncio.Task]
            cls._instance._init_sources()
        return cls._instance

    def _init_sources(self):
        self.sources = {"telegram": TelegramSource, "reindex_media": MediaReindexSource}

    def get_job(self, job_id: str) -> Optional[JobStatusResponse]:
        if job_id not in self.jobs:
            return None

        state = self.jobs[job_id]
        return JobStatusResponse(
            job_id=state.job_id,
            status=state.status,
            progress=state.progress,
            message=state.message,
            result=state.result,
            error=state.error,
        )

    async def submit_job(self, source_type: str, params: Dict[str, Any]) -> str:
        job_id = str(uuid.uuid4())
        state = JobState(job_id, source_type)
        self.jobs[job_id] = state

        task = asyncio.create_task(self._run_job(job_id, source_type, params))
        self._tasks[job_id] = task
        task.add_done_callback(lambda _task, jid=job_id: self._tasks.pop(jid, None))
        return job_id

    async def submit_analyze_chats_job(self, chat_ids: List[int]) -> str:
        """Submit a job that only runs chat analysis (description + tags) for the given chat_ids."""
        job_id = str(uuid.uuid4())
        state = JobState(job_id, "analyze_chats")
        self.jobs[job_id] = state
        task = asyncio.create_task(self._run_analyze_chats(job_id, chat_ids))
        self._tasks[job_id] = task
        task.add_done_callback(lambda _task, jid=job_id: self._tasks.pop(jid, None))
        return job_id

    async def _run_analyze_chats(self, job_id: str, chat_ids: List[int]):
        state = self.jobs[job_id]
        state.status = "running"
        state.message = "Connecting to Telegram..."
        source = TelegramSource()
        try:
            await source.connect()
            total = len(chat_ids)
            for i, chat_id in enumerate(chat_ids):
                state.message = f"Analyzing chat {chat_id}..."
                state.progress = (i + 1) / total if total else 0.0
                try:
                    await source.analyze_chat(chat_id)
                except Exception as e:
                    logger.error(f"Failed to analyze chat {chat_id}: {e}")
            state.status = "completed"
            state.progress = 1.0
            state.message = "Analysis completed"
        except asyncio.CancelledError:
            state.status = "failed"
            state.error = "Job was cancelled"
            raise
        except Exception as e:
            logger.error(f"Analyze chats job {job_id} failed: {e}")
            state.status = "failed"
            state.error = str(e)
        finally:
            await source.disconnect()

    # ------------------------------------------------------------------
    # Three-phase pipeline
    # ------------------------------------------------------------------

    async def _run_job(self, job_id: str, source_type: str, params: Dict[str, Any]):
        state = self.jobs[job_id]
        state.status = "running"
        state.message = "Initializing source..."

        source_cls = self.sources.get(source_type)
        if not source_cls:
            state.status = "failed"
            state.error = f"Unknown source type: {source_type}"
            return

        source: BaseSource = source_cls()
        if hasattr(source, "set_job_id"):
            source.set_job_id(job_id)

        try:
            await source.connect()

            def update_progress(msg, prog):
                state.message = msg
                state.progress = prog

            # ---- Phase 1: Fetch & save raw docs (fast, no inference) ----
            state.message = "Phase 1: Downloading data..."
            all_doc_specs: list[tuple[str, str]] = []
            docs: list[GenericDocument] = []

            async for doc in source.fetch(params, update_progress):
                docs.append(doc)
                all_doc_specs.append((doc.source_id, doc.doc_id))

                if len(docs) >= BATCH_SAVE_SIZE:
                    await save_raw_documents(docs)
                    docs = []

            if docs:
                await save_raw_documents(docs)
                docs = []

            # ---- Phase 2: Wait for model scheduler to finish ----
            state.message = "Phase 2: Waiting for media analysis..."
            state.progress = 0.5
            await self._seal_and_wait(job_id, state)

            # ---- Phase 3: Enrich, Index, Extract ----
            state.message = "Phase 3: Enriching documents..."
            state.progress = 0.7
            enriched_specs = await self._enrich_from_results(job_id)

            # Re-read enriched + all docs for indexing
            specs_to_index = all_doc_specs if all_doc_specs else enriched_specs
            if specs_to_index:
                state.message = "Indexing documents..."
                state.progress = 0.8
                rows = await get_raw_documents_by_ids(specs_to_index)
                enriched_docs = []
                for r in rows:
                    try:
                        ts = (
                            datetime.fromisoformat(r.timestamp)
                            if r.timestamp
                            else datetime.now()
                        )
                    except (ValueError, TypeError):
                        ts = datetime.now()
                    enriched_docs.append(
                        GenericDocument(
                            source_id=r.source_id or "",
                            doc_id=r.doc_id,
                            content=r.content,
                            timestamp=ts,
                            metadata=r.metadata,
                        )
                    )

                doc_ids = [d.doc_id for d in enriched_docs]
                already_indexed = await get_indexed_status(doc_ids)
                new_docs = [d for d in enriched_docs if d.doc_id not in already_indexed]

                if new_docs:
                    state.message = f"Indexing {len(new_docs)} documents..."
                    await asyncio.to_thread(update_index, new_docs)
                    await mark_as_indexed(new_docs)

                state.message = "Analyzing chats..."
                state.progress = 0.9
                # Get unique chat_ids we just updated
                chat_ids_to_analyze = set()
                for d in enriched_docs:
                    if d.metadata and d.metadata.get("chat_id"):
                        try:
                            chat_ids_to_analyze.add(int(d.metadata["chat_id"]))
                        except ValueError:
                            pass
                
                total_chats = len(chat_ids_to_analyze)
                for i, cid in enumerate(chat_ids_to_analyze):
                    state.message = f"Analyzing chat {i+1}/{total_chats}..."
                    await source.analyze_chat(cid)

            state.status = "completed"
            state.progress = 1.0
            state.message = "Sync Completed"

        except asyncio.CancelledError:
            state.status = "failed"
            state.error = "Job was cancelled"
            raise
        except Exception as e:
            logger.error(f"Job {job_id} failed: {e}")
            state.status = "failed"
            state.error = str(e)
        finally:
            await source.disconnect()

    async def shutdown(self) -> None:
        """Cancel and await all in-flight job tasks."""
        pending = [task for task in self._tasks.values() if not task.done()]
        if not pending:
            return
        for task in pending:
            task.cancel()
        await asyncio.gather(*pending, return_exceptions=True)
        self._tasks.clear()

    # ------------------------------------------------------------------
    # Phase 2 helpers
    # ------------------------------------------------------------------

    async def _seal_and_wait(self, job_id: str, state: JobState) -> None:
        """Seal the job on backend and poll until all tasks are done."""
        backend_url = get_backend_url("")
        async with httpx.AsyncClient(timeout=10) as client:
            try:
                await client.post(f"{backend_url}tasks/seal/{job_id}")
            except Exception as exc:
                logger.warning(f"Failed to seal job {job_id}: {exc}")
                return

        async with httpx.AsyncClient(timeout=None) as client:
            completed = False
            while not completed:
                try:
                    async with client.stream("GET", f"{backend_url}tasks/status/stream/{job_id}") as response:
                        response.raise_for_status()
                        async for line in response.aiter_lines():
                            if not line.startswith("data: "):
                                continue
                            try:
                                data = json.loads(line[6:])
                                total = data.get("total", 0)
                                done_count = data.get("completed", 0) + data.get("failed", 0)
                                if total == 0:
                                    completed = True
                                    break
                                state.message = f"Media analysis: {done_count}/{total} tasks done"
                                if data.get("done"):
                                    completed = True
                                    break
                            except json.JSONDecodeError:
                                pass
                except Exception as exc:
                    logger.warning(f"Task status stream error: {exc}")
                    await asyncio.sleep(2.0)

    # ------------------------------------------------------------------
    # Phase 3 helpers
    # ------------------------------------------------------------------

    async def _enrich_from_results(self, job_id: str) -> list[tuple[str, str]]:
        """Fetch task results from backend and update raw_documents."""
        backend_url = get_backend_url("")
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                resp = await client.get(f"{backend_url}tasks/results/{job_id}")
                resp.raise_for_status()
                results = resp.json()
        except Exception as exc:
            logger.error(f"Failed to fetch task results: {exc}")
            return []

        enriched: list[tuple[str, str]] = []

        for item in results:
            if item.get("status") != "completed" or not item.get("result"):
                continue

            source_id = item["source_id"]
            doc_id = item["doc_id"]
            subtype = item["task_subtype"]
            result = item["result"]

            rows = await get_raw_documents_by_ids([(source_id, doc_id)])
            if not rows:
                continue

            row = rows[0]
            metadata = (
                row.metadata
                if isinstance(row.metadata, dict)
                else json.loads(row.metadata)
            )
            media_dict = metadata.get("media") or {}
            content = row.content

            try:
                if subtype == "analyze_image":
                    result_model = ImageAnalysisResponse.model_validate(result)
                    media_model = TelegramMediaMetadata.model_validate(media_dict)
                    media_model = self._apply_image_result(media_model, result_model)
                    media_dict = media_model.model_dump(exclude_none=True)
                elif subtype == "transcribe_audio":
                    result_model = AudioTranscriptionResponse.model_validate(result)
                    media_model = TelegramMediaMetadata.model_validate(media_dict)
                    media_model = self._apply_audio_result(media_model, result_model)
                    media_dict = media_model.model_dump(exclude_none=True)
                elif subtype == "analyze_pdf":
                    result_model = PDFAnalysisResponse.model_validate(result)
                    media_model = TelegramMediaMetadata.model_validate(media_dict)
                    media_model = self._apply_pdf_result(media_model, result_model)
                    media_dict = media_model.model_dump(exclude_none=True)

                metadata["media"] = media_dict
                content = self._rebuild_content(
                    content, media_model if "media_model" in locals() else media_dict
                )

                await update_raw_document(source_id, doc_id, content, metadata)
                enriched.append((source_id, doc_id))
            except Exception as exc:
                logger.error(f"Enrichment failed for {source_id}/{doc_id}: {exc}")

        logger.info(f"Enriched {len(enriched)} documents from task results")
        return enriched

    @staticmethod
    def _apply_image_result(
        media: TelegramMediaMetadata, result: ImageAnalysisResponse
    ) -> TelegramMediaMetadata:
        sa = result.structured_analysis
        if sa:
            media.description = sa.description
            media.is_meme = sa.is_meme
            media.is_portrait = sa.is_portrait
            tags = sa.context_tags or sa.detected_objects or []
            media.tags = tags if tags else None
        else:
            media.description = result.description
        return media

    @staticmethod
    def _apply_audio_result(
        media: TelegramMediaMetadata, result: AudioTranscriptionResponse
    ) -> TelegramMediaMetadata:
        transcript = result.transcript
        cleaned = result.cleaned_transcript
        media.description = cleaned if cleaned else transcript
        media.original_transcript = transcript
        if result.language:
            media.language = result.language
        if result.transcription_confidence is not None:
            media.confidence = result.transcription_confidence
        if result.language_probability is not None:
            media.language_probability = result.language_probability
        if not media.duration and result.duration:
            media.duration = result.duration
        if result.translation:
            media.translation = result.translation
        return media

    @staticmethod
    def _apply_pdf_result(
        media: TelegramMediaMetadata, result: PDFAnalysisResponse
    ) -> TelegramMediaMetadata:
        text = result.text
        page_count = result.page_count
        parts = []
        if text:
            parts.append(text[:500] + ("..." if len(text) > 500 else ""))
        if page_count:
            parts.append(f"Pages: {page_count}")
        media.description = " | ".join(parts)
        return media

    @staticmethod
    def _rebuild_content(content: str, media: TelegramMediaMetadata | dict) -> str:
        """Replace the placeholder media tag with the enriched one."""
        if isinstance(media, dict):
            desc = media.get("description", "")
            media_type = (media.get("type") or "media").upper()
        else:
            desc = media.description or ""
            media_type = (media.type or "media").upper()

        if media_type in ("AUDIO", "VOICE") and desc:
            new_prefix = f"[{media_type} TRANSCRIPT] {desc}"
        elif desc:
            new_prefix = f"[{media_type}] {desc}"
        else:
            return content

        pattern = rf"\[{re.escape(media_type)}(?:\s+TRANSCRIPT)?\](?:\s*)"
        return re.sub(pattern, new_prefix + "\n", content, count=1)
