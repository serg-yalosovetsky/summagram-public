"""
Model-aware processing task queue.

Tasks are grouped by model_type (vision, audio, document) so the ModelScheduler
can load one model at a time, drain its queue, unload, and proceed to the next.
"""

import asyncio
import uuid
from datetime import datetime
from enum import Enum
from typing import Any

from loguru import logger
from pydantic import BaseModel, Field


class ModelType(str, Enum):
    VISION = "vision"
    AUDIO = "audio"
    DOCUMENT = "document"


class TaskStatus(str, Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class ProcessingTask(BaseModel):
    task_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    job_id: str
    model_type: ModelType
    task_subtype: str
    source_id: str
    doc_id: str
    input_path: str
    input_params: dict[str, Any] = {}
    status: TaskStatus = TaskStatus.PENDING
    result: dict[str, Any] | None = None
    error: str | None = None
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)


class EnqueueRequest(BaseModel):
    job_id: str
    model_type: ModelType
    task_subtype: str
    source_id: str
    doc_id: str
    input_path: str
    input_params: dict[str, Any] = {}


class BulkEnqueueRequest(BaseModel):
    tasks: list[EnqueueRequest]


class TaskStatusResponse(BaseModel):
    job_id: str
    total: int
    pending: int
    processing: int
    completed: int
    failed: int
    sealed: bool
    done: bool


class TaskResultItem(BaseModel):
    task_id: str
    source_id: str
    doc_id: str
    task_subtype: str
    status: TaskStatus
    result: dict[str, Any] | None = None
    error: str | None = None


class ProcessingQueueManager:
    """In-memory task queues grouped by ModelType, tracked per job_id."""

    _instance: "ProcessingQueueManager | None" = None
    _instance_loop = None

    def __new__(cls) -> "ProcessingQueueManager":
        try:
            current_loop = asyncio.get_running_loop()
        except RuntimeError:
            current_loop = None

        if cls._instance is None or cls._instance_loop != current_loop:
            cls._instance = super().__new__(cls)
            cls._instance._init()
            cls._instance_loop = current_loop
        return cls._instance

    def _init(self) -> None:
        self._queues: dict[ModelType, asyncio.Queue[ProcessingTask]] = {
            mt: asyncio.Queue() for mt in ModelType
        }
        self._tasks: dict[str, ProcessingTask] = {}
        self._job_tasks: dict[str, list[str]] = {}
        self._sealed_jobs: set[str] = set()
        self._new_tasks_event = asyncio.Event()

    def enqueue(self, task: ProcessingTask) -> None:
        self._tasks[task.task_id] = task
        self._job_tasks.setdefault(task.job_id, []).append(task.task_id)
        self._queues[task.model_type].put_nowait(task)
        self._new_tasks_event.set()
        logger.debug(
            f"Enqueued task {task.task_id} ({task.task_subtype}) "
            f"for model {task.model_type.value}"
        )

    def enqueue_bulk(self, tasks: list[ProcessingTask]) -> None:
        if not tasks:
            return
        
        for task in tasks:
            self._tasks[task.task_id] = task
            self._job_tasks.setdefault(task.job_id, []).append(task.task_id)
            self._queues[task.model_type].put_nowait(task)
            
        self._new_tasks_event.set()
        logger.info(f"Enqueued {len(tasks)} tasks in bulk")


    def seal_job(self, job_id: str) -> None:
        """Mark a job as fully submitted (no more tasks will be added)."""
        self._sealed_jobs.add(job_id)
        logger.info(f"Job {job_id} sealed")

    def get_queue_sizes(self) -> dict[str, int]:
        return {mt.value: q.qsize() for mt, q in self._queues.items()}

    def has_pending_work(self) -> bool:
        return any(not q.empty() for q in self._queues.values())

    async def wait_for_tasks(self, timeout: float = 1.0) -> None:
        """Block until new tasks arrive or timeout."""
        self._new_tasks_event.clear()
        try:
            await asyncio.wait_for(self._new_tasks_event.wait(), timeout=timeout)
        except asyncio.TimeoutError:
            pass

    def drain_queue(self, model_type: ModelType) -> list[ProcessingTask]:
        q = self._queues[model_type]
        tasks: list[ProcessingTask] = []
        while not q.empty():
            try:
                tasks.append(q.get_nowait())
            except asyncio.QueueEmpty:
                break
        return tasks

    def get_job_status(self, job_id: str) -> TaskStatusResponse:
        task_ids = self._job_tasks.get(job_id, [])
        counters: dict[TaskStatus, int] = {s: 0 for s in TaskStatus}
        for tid in task_ids:
            t = self._tasks[tid]
            counters[t.status] += 1

        total = len(task_ids)
        sealed = job_id in self._sealed_jobs
        done = (
            sealed
            and total > 0
            and counters[TaskStatus.PENDING] == 0
            and counters[TaskStatus.PROCESSING] == 0
        )

        return TaskStatusResponse(
            job_id=job_id,
            total=total,
            pending=counters[TaskStatus.PENDING],
            processing=counters[TaskStatus.PROCESSING],
            completed=counters[TaskStatus.COMPLETED],
            failed=counters[TaskStatus.FAILED],
            sealed=sealed,
            done=done,
        )

    def get_job_results(self, job_id: str) -> list[TaskResultItem]:
        task_ids = self._job_tasks.get(job_id, [])
        return [
            TaskResultItem(
                task_id=t.task_id,
                source_id=t.source_id,
                doc_id=t.doc_id,
                task_subtype=t.task_subtype,
                status=t.status,
                result=t.result,
                error=t.error,
            )
            for tid in task_ids
            if (t := self._tasks.get(tid))
        ]

    def is_job_complete(self, job_id: str) -> bool:
        return self.get_job_status(job_id).done
