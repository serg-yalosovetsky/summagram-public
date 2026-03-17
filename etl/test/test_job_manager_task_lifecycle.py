import asyncio
import sys
from pathlib import Path

import pytest

root_dir = str(Path(__file__).resolve().parent.parent.parent)
if root_dir not in sys.path:
    sys.path.insert(0, root_dir)
etl_dir = str(Path(__file__).resolve().parent.parent)
if etl_dir not in sys.path:
    sys.path.insert(0, etl_dir)

from etl.manager import JobManager


class _FakeTask:
    def __init__(self) -> None:
        self._callbacks = []
        self._done = False

    def add_done_callback(self, callback):
        self._callbacks.append(callback)

    def done(self) -> bool:
        return self._done

    def finish(self) -> None:
        self._done = True
        for callback in list(self._callbacks):
            callback(self)


@pytest.mark.asyncio
async def test_submit_job_tracks_background_task(monkeypatch):
    JobManager._instance = None

    def _init_sources(self):
        self.sources = {"telegram": object()}

    monkeypatch.setattr(JobManager, "_init_sources", _init_sources, raising=True)

    manager = JobManager()
    created = []

    def _fake_create_task(coro):
        coro.close()
        task = _FakeTask()
        created.append(task)
        return task

    monkeypatch.setattr(asyncio, "create_task", _fake_create_task)

    job_id = await manager.submit_job("telegram", {})

    assert job_id in manager._tasks
    assert manager._tasks[job_id] is created[0]


@pytest.mark.asyncio
async def test_submit_job_removes_task_from_registry_when_done(monkeypatch):
    JobManager._instance = None

    def _init_sources(self):
        self.sources = {"telegram": object()}

    monkeypatch.setattr(JobManager, "_init_sources", _init_sources, raising=True)

    manager = JobManager()
    created = []

    def _fake_create_task(coro):
        coro.close()
        task = _FakeTask()
        created.append(task)
        return task

    monkeypatch.setattr(asyncio, "create_task", _fake_create_task)

    job_id = await manager.submit_job("telegram", {})
    created[0].finish()

    assert job_id not in manager._tasks
