"""
Model Scheduler: background loop that loads one model at a time,
drains the corresponding task queue, then unloads and moves on.
"""

import asyncio
import os
from datetime import datetime

from loguru import logger

from backend.task_queue import (
    ModelType,
    ProcessingQueueManager,
    ProcessingTask,
    TaskStatus,
)

PRIORITY: list[ModelType] = [ModelType.VISION, ModelType.AUDIO, ModelType.DOCUMENT]


class ModelScheduler:
    """Watches ProcessingQueueManager and processes tasks model-by-model."""

    def __init__(self) -> None:
        self._queue = ProcessingQueueManager()
        self._running = False
        self._current_model: ModelType | None = None
        self._bg_task: asyncio.Task | None = None

    @property
    def current_model(self) -> str | None:
        return self._current_model.value if self._current_model else None

    async def start(self) -> None:
        if self._running:
            return
        self._running = True
        self._bg_task = asyncio.create_task(self._run(), name="model-scheduler")
        logger.info("ModelScheduler started")

    async def stop(self) -> None:
        self._running = False
        if self._bg_task:
            self._bg_task.cancel()
            try:
                await self._bg_task
            except asyncio.CancelledError:
                pass
        logger.info("ModelScheduler stopped")

    async def _run(self) -> None:
        while self._running:
            model_type = self._pick_next_model()
            if model_type is not None:
                await self._drain_and_process(model_type)
            else:
                await self._queue.wait_for_tasks(timeout=1.0)

    def _pick_next_model(self) -> ModelType | None:
        sizes = self._queue.get_queue_sizes()
        for mt in PRIORITY:
            if sizes.get(mt.value, 0) > 0:
                return mt
        return None

    async def _drain_and_process(self, model_type: ModelType) -> None:
        tasks = self._queue.drain_queue(model_type)
        if not tasks:
            return

        self._current_model = model_type
        logger.info(f"Scheduler: processing {len(tasks)} {model_type.value} tasks")

        for task in tasks:
            task.status = TaskStatus.PROCESSING
            task.updated_at = datetime.now()
            try:
                result = await self._execute(task)
                task.result = result
                task.status = TaskStatus.COMPLETED
            except Exception as exc:
                logger.error(
                    f"Scheduler: task {task.task_id} ({task.task_subtype}) failed: {exc}"
                )
                task.error = str(exc)
                task.status = TaskStatus.FAILED
            task.updated_at = datetime.now()

        self._current_model = None

    async def _execute(self, task: ProcessingTask) -> dict:
        from inference import LocalInferenceService

        service = LocalInferenceService()
        path = task.input_path

        if not os.path.exists(path):
            raise FileNotFoundError(f"File not found: {path}")

        if task.task_subtype == "analyze_image":
            resp = await service.analyze_image(path, task.input_params.get("prompt"))
            return resp.model_dump()

        if task.task_subtype == "transcribe_audio":
            resp = await service.transcribe_audio(path)
            return resp.model_dump()

        if task.task_subtype == "analyze_pdf":
            resp = await service.analyze_pdf_with_kreuzberg(path)
            return resp.model_dump()

        raise ValueError(f"Unknown task_subtype: {task.task_subtype}")
