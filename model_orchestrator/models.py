"""Shared models for the model orchestrator."""

import asyncio
from typing import Dict, List, Optional

from pydantic import BaseModel


# ---------------------------------------------------------------------------
# Application state
# ---------------------------------------------------------------------------


class OrchestratorState:
    """Mutable application state shared across the orchestrator.

    ``warm_task``        — singleflight: all concurrent callers await the
                           same ``asyncio.Task`` instead of each starting
                           their own switch.
    ``engine_states``    — last known EngineState string per mode.
    ``last_used_at``     — monotonic timestamp of last touch per mode.
    ``vision_idle_task`` — background task that auto-sleeps vision after idle.
    """

    def __init__(self) -> None:
        self.lock: asyncio.Lock = asyncio.Lock()
        self.current_mode: Optional[str] = None
        # Singleflight: shared task for in-progress mode switch
        self.warm_task: Optional[asyncio.Task] = None  # type: ignore[type-arg]
        # Per-mode engine state (EngineState.value strings, set by services.py)
        self.engine_states: Dict[str, str] = {}
        # Per-mode last-use monotonic timestamp
        self.last_used_at: Dict[str, float] = {}
        # Background task for vision idle auto-sleep
        self.vision_idle_task: Optional[asyncio.Task] = None  # type: ignore[type-arg]
        # Background task for audio idle auto-sleep
        self.audio_idle_task: Optional[asyncio.Task] = None  # type: ignore[type-arg]


# Singleton instance used across modules
state = OrchestratorState()


# ---------------------------------------------------------------------------
# API response schemas
# ---------------------------------------------------------------------------


class ModelObject(BaseModel):
    """Single model entry in the OpenAI-compatible model list."""

    id: str
    object: str = "model"
    created: int = 1


class ModelListResponse(BaseModel):
    """OpenAI-compatible ``/v1/models`` response."""

    object: str = "list"
    data: List[ModelObject]


class HealthResponse(BaseModel):
    """Lightweight health check — used by Docker healthcheck."""

    status: str


class StatusResponse(BaseModel):
    """Detailed orchestrator status."""

    status: str
    current_mode: Optional[str]
    switching: bool
    available_modes: List[str]
    engine_states: Dict[str, str] = {}
