"""Orchestration services for vLLM sleep / wake based switching.

Goals:
- No docker stop/start in request path.
- Keep workers alive and switch via vLLM /sleep and /wake_up.
- Singleflight protection for concurrent switch attempts.
- Sticky text policy: text stays awake by default.
- Vision can be auto-slept after an idle timeout.

Assumptions:
- vLLM workers are already running in Docker and reachable by internal URLs.
- VLLM_SERVER_DEV_MODE=1 is enabled on workers, so /sleep, /wake_up,
  and /is_sleeping are available.
- These dev endpoints are NOT exposed publicly — orchestrator is the only caller.
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
import time
from enum import Enum
from typing import Dict, Optional

import httpx

from config import MODE_URLS, SLEEP_ENDPOINT_MODES, VLLM_API_KEY
from exceptions import (
    UnknownModeError,
    WorkerReadyTimeoutError,
    WorkerSleepError,
)
from models import state

logger = logging.getLogger("orchestrator")


# =========================
# Config knobs
# =========================

# Only sleep non-primary modes aggressively.
PRIMARY_MODE: str = "text"

# How long to keep vision awake after last use before auto-sleeping.
VISION_IDLE_TTL_SEC: int = 30

# Polling / timeout knobs
WAKE_TIMEOUT_SEC: int = 180
READY_TIMEOUT_SEC: int = 180
SLEEP_TIMEOUT_SEC: int = 30
POLL_INTERVAL_SEC: float = 0.5

# vLLM docs: level=1 keeps weights in CPU RAM; level=2 releases more memory.
# Use level=2 for bootstrap (guaranteed clean start); level=1 for idle-sleep
# so the same model can wake faster on repeat use.
DEFAULT_IDLE_SLEEP_LEVEL: int = 1   # orchestrator runtime idle-sleep
DEFAULT_BOOTSTRAP_SLEEP_LEVEL: int = 2  # (informational; used by Compose sleepers)


# =========================
# EngineState
# =========================


class EngineState(str, Enum):
    DOWN = "down"
    SLEEPING = "sleeping"
    WAKING = "waking"
    READY = "ready"
    UNKNOWN = "unknown"


# =========================
# Shared HTTP client
# =========================

_http_client: Optional[httpx.AsyncClient] = None


async def get_http_client() -> httpx.AsyncClient:
    """Return (or lazily create) the shared httpx client."""
    global _http_client
    if _http_client is None or _http_client.is_closed:
        _http_client = httpx.AsyncClient(
            timeout=httpx.Timeout(10.0, connect=2.0),
            headers={"Authorization": f"Bearer {VLLM_API_KEY}"},
        )
    return _http_client


async def close_http_client() -> None:
    global _http_client
    if _http_client is not None:
        await _http_client.aclose()
        _http_client = None


# =========================
# Low-level vLLM control plane
# =========================


def _require_mode(mode: str) -> str:
    """Validate mode and return its base URL."""
    if mode not in MODE_URLS:
        raise UnknownModeError(f"Unsupported mode: {mode!r}")
    return MODE_URLS[mode]


def _supports_sleep_endpoints(mode: str) -> bool:
    _require_mode(mode)
    return mode in SLEEP_ENDPOINT_MODES


async def is_sleeping(mode: str) -> bool:
    """Return True if the worker reports sleeping."""
    if not _supports_sleep_endpoints(mode):
        return False
    base_url = _require_mode(mode)
    client = await get_http_client()
    resp = await client.get(f"{base_url}/is_sleeping")
    resp.raise_for_status()
    return bool(resp.json().get("is_sleeping"))


async def sleep_engine(mode: str, level: int = DEFAULT_IDLE_SLEEP_LEVEL) -> None:
    """Put a worker to sleep at the given level and verify it happened."""
    if not _supports_sleep_endpoints(mode):
        logger.info("Skipping sleep for mode=%s (sleep endpoints unsupported)", mode)
        return
    base_url = _require_mode(mode)
    client = await get_http_client()

    logger.info("Sleeping mode=%s level=%s", mode, level)
    resp = await client.post(
        f"{base_url}/sleep",
        params={"level": level},
        timeout=SLEEP_TIMEOUT_SEC,
    )
    resp.raise_for_status()

    # Verify sleep took effect
    try:
        sleeping = await is_sleeping(mode)
    except Exception as exc:
        raise WorkerSleepError(
            f"Sleep verification failed for mode={mode}: {exc}"
        ) from exc

    if not sleeping:
        raise WorkerSleepError(f"Mode={mode} did not enter sleep state")

    state.engine_states[mode] = EngineState.SLEEPING.value
    logger.info("Mode=%s is now sleeping", mode)


async def wake_engine(mode: str) -> None:
    """Send wake_up to a sleeping worker."""
    if not _supports_sleep_endpoints(mode):
        logger.info("Skipping wake for mode=%s (sleep endpoints unsupported)", mode)
        return
    base_url = _require_mode(mode)
    client = await get_http_client()

    logger.info("Waking mode=%s", mode)
    state.engine_states[mode] = EngineState.WAKING.value
    resp = await client.post(f"{base_url}/wake_up", timeout=WAKE_TIMEOUT_SEC)
    resp.raise_for_status()


async def wait_openai_ready(mode: str, timeout: int = READY_TIMEOUT_SEC) -> None:
    """Poll /v1/models until it responds 200 or timeout expires."""
    base_url = _require_mode(mode)
    client = await get_http_client()

    start = asyncio.get_running_loop().time()
    last_exc: Optional[Exception] = None

    while asyncio.get_running_loop().time() - start < timeout:
        try:
            resp = await client.get(f"{base_url}/v1/models", timeout=5.0)
            if resp.status_code == 200:
                elapsed = asyncio.get_running_loop().time() - start
                state.engine_states[mode] = EngineState.READY.value
                logger.info("Mode=%s is ready after %.1fs", mode, elapsed)
                return
        except Exception as exc:
            last_exc = exc

        await asyncio.sleep(POLL_INTERVAL_SEC)

    raise WorkerReadyTimeoutError(
        f"Timeout ({timeout}s) waiting for mode={mode} readiness at "
        f"{base_url}/v1/models; last_error={last_exc!r}"
    )


async def detect_engine_state(mode: str) -> EngineState:
    """Non-destructive best-effort state probe."""
    base_url = _require_mode(mode)
    client = await get_http_client()

    if _supports_sleep_endpoints(mode):
        try:
            sleeping = await is_sleeping(mode)
            if sleeping:
                return EngineState.SLEEPING
        except Exception:
            pass  # dev endpoint unreachable → fall through

    try:
        resp = await client.get(f"{base_url}/v1/models", timeout=3.0)
        if resp.status_code == 200:
            return EngineState.READY
    except Exception:
        pass

    return EngineState.UNKNOWN


# =========================
# Policy helpers
# =========================


def touch_mode(mode: str) -> None:
    """Update last-used timestamp for a mode."""
    state.last_used_at[mode] = time.monotonic()


async def maybe_cancel_vision_idle_task() -> None:
    task = state.vision_idle_task
    if task is None:
        return
    task.cancel()
    with contextlib.suppress(asyncio.CancelledError):
        await task
    state.vision_idle_task = None


async def schedule_vision_idle_sleep() -> None:
    """Schedule vision to auto-sleep after VISION_IDLE_TTL_SEC of inactivity."""
    await maybe_cancel_vision_idle_task()

    async def _job() -> None:
        try:
            await asyncio.sleep(VISION_IDLE_TTL_SEC)
            async with state.lock:
                age = time.monotonic() - state.last_used_at.get("vision", 0.0)
                if age < VISION_IDLE_TTL_SEC:
                    # A new vision request arrived while we were waiting.
                    return

                current = await detect_engine_state("vision")
                state.engine_states["vision"] = current.value

                if current != EngineState.SLEEPING:
                    try:
                        await sleep_engine("vision", level=DEFAULT_IDLE_SLEEP_LEVEL)
                    except Exception:
                        logger.exception("Failed to auto-sleep vision worker")
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("Vision idle sleep task crashed")

    state.vision_idle_task = asyncio.create_task(_job())


# ---- Audio idle task (mirrors vision) ----

AUDIO_IDLE_TTL_SEC: int = 30


async def maybe_cancel_audio_idle_task() -> None:
    task = state.audio_idle_task
    if task is None:
        return
    task.cancel()
    with contextlib.suppress(asyncio.CancelledError):
        await task
    state.audio_idle_task = None


async def schedule_audio_idle_sleep() -> None:
    """Schedule audio to auto-sleep after AUDIO_IDLE_TTL_SEC of inactivity."""
    await maybe_cancel_audio_idle_task()

    async def _job() -> None:
        try:
            await asyncio.sleep(AUDIO_IDLE_TTL_SEC)
            async with state.lock:
                age = time.monotonic() - state.last_used_at.get("audio", 0.0)
                if age < AUDIO_IDLE_TTL_SEC:
                    return

                current = await detect_engine_state("audio")
                state.engine_states["audio"] = current.value

                if current != EngineState.SLEEPING:
                    try:
                        await sleep_engine("audio", level=DEFAULT_IDLE_SLEEP_LEVEL)
                    except Exception:
                        logger.exception("Failed to auto-sleep audio worker")
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("Audio idle sleep task crashed")

    state.audio_idle_task = asyncio.create_task(_job())


# =========================
# Core switch logic
# =========================


async def _ensure_awake_and_ready(mode: str) -> None:
    """Wake mode if needed and wait until /v1/models responds 200."""
    current = await detect_engine_state(mode)
    state.engine_states[mode] = current.value

    if current == EngineState.READY:
        return

    if current == EngineState.SLEEPING:
        await wake_engine(mode)
        await wait_openai_ready(mode, timeout=READY_TIMEOUT_SEC)
        return

    # UNKNOWN / potential DOWN — container should be alive; try readiness first,
    # then fall back to wake_up.
    try:
        await wait_openai_ready(mode, timeout=10)
        return
    except WorkerReadyTimeoutError:
        if not _supports_sleep_endpoints(mode):
            raise
        logger.warning("Mode=%s not immediately ready; attempting wake_up()", mode)

    await wake_engine(mode)
    await wait_openai_ready(mode, timeout=READY_TIMEOUT_SEC)


async def _do_switch_mode(target_mode: str) -> None:
    """Internal switch; must be called under singleflight protection."""
    async with state.lock:
        _require_mode(target_mode)

        if state.current_mode == target_mode:
            touch_mode(target_mode)
            return

        previous_mode = state.current_mode
        logger.info("Switching mode: %s -> %s", previous_mode, target_mode)

        # 1) Ensure target is awake and ready.
        await _ensure_awake_and_ready(target_mode)
        touch_mode(target_mode)
        state.current_mode = target_mode

        # 2) Sleep non-primary modes that are not the target.
        # Text stays awake by default; we only aggressively sleep secondary
        # modes (currently "vision" when text is primary).
        for mode in list(MODE_URLS):
            if mode == target_mode or mode == PRIMARY_MODE:
                continue
            try:
                detected = await detect_engine_state(mode)
                state.engine_states[mode] = detected.value
                if detected != EngineState.SLEEPING:
                    await sleep_engine(mode, level=DEFAULT_IDLE_SLEEP_LEVEL)
            except Exception:
                logger.exception("Failed to sleep secondary mode=%s", mode)

        logger.info("Mode is now %s", target_mode)


async def ensure_mode(target_mode: str) -> None:
    """Public singleflight switch.

    Rules:
    - If already in target_mode → return immediately.
    - If a switch task is active → await it, then re-check.
    - Otherwise → create a shared task so all concurrent callers await it.
    """
    _require_mode(target_mode)

    if state.current_mode == target_mode:
        touch_mode(target_mode)
        return

    if state.warm_task is not None and not state.warm_task.done():
        await state.warm_task
        if state.current_mode == target_mode:
            touch_mode(target_mode)
            return
        # Mode ended up somewhere else; fall through to create a new task.

    task = asyncio.create_task(_do_switch_mode(target_mode))
    state.warm_task = task
    try:
        await task
    finally:
        if state.warm_task is task:
            state.warm_task = None


# Backward-compatible alias
async def switch_mode(target_mode: str) -> None:
    await ensure_mode(target_mode)


# =========================
# Request-path helpers
# =========================


def classify_openai_payload(payload: Dict) -> str:
    """Deterministic text / vision / audio router based on payload inspection.

    Returns:
        "vision" if any message content contains an image_url or input_image.
        "audio"  if any message content contains an input_audio item.
        "text"   otherwise.
    """
    messages = payload.get("messages", [])
    for msg in messages:
        content = msg.get("content")
        if isinstance(content, list):
            for item in content:
                item_type = item.get("type")
                if item_type in {"image_url", "input_image"}:
                    return "vision"
                if item_type == "input_audio":
                    return "audio"
    return "text"


async def route_request_mode(payload: Dict) -> str:
    """Resolve target mode and ensure the worker is ready.

    Also schedules idle-sleep timers for vision/audio when chosen.
    """
    target_mode = classify_openai_payload(payload)

    if target_mode == "text":
        await ensure_mode("text")
        return "text"

    if target_mode == "vision":
        # Cancel any pending idle sleep while we are actively using vision.
        await maybe_cancel_vision_idle_task()
        await ensure_mode("vision")
        touch_mode("vision")
        await schedule_vision_idle_sleep()
        return "vision"

    if target_mode == "audio":
        await maybe_cancel_audio_idle_task()
        await ensure_mode("audio")
        touch_mode("audio")
        if _supports_sleep_endpoints("audio"):
            await schedule_audio_idle_sleep()
        return "audio"

    raise UnknownModeError(f"Unsupported routed mode: {target_mode!r}")


def get_backend_url(mode: str) -> str:
    """Return the base URL for a given mode."""
    return _require_mode(mode)


# =========================
# Startup / shutdown
# =========================


async def startup_orchestrator() -> None:
    """Run during FastAPI lifespan startup.

    Final startup state:
    - text: READY (awake)
    - vision: SLEEPING at level 2
    """
    logger.info("Starting orchestrator bootstrap")

    # Ensure HTTP client is initialised early
    await get_http_client()

    # Initialise mode state tracking
    for mode in MODE_URLS:
        state.engine_states.setdefault(mode, EngineState.UNKNOWN.value)
        state.last_used_at.setdefault(mode, 0.0)

    # Wake primary text worker
    try:
        await _ensure_awake_and_ready(PRIMARY_MODE)
        touch_mode(PRIMARY_MODE)
        state.current_mode = PRIMARY_MODE
        logger.info("Bootstrap: text worker is ready")
    except Exception:
        logger.exception(
            "Bootstrap: failed to wake text worker; "
            "text will be woken on first request"
        )

    # Sleep secondary modes at bootstrap level=2 — safety guard for partial restarts;
    # the Compose sleeper chain is the source of truth for initial state.
    for mode in ["vision", "audio"]:
        if mode not in MODE_URLS:
            continue
        try:
            detected = await detect_engine_state(mode)
            state.engine_states[mode] = detected.value
            if detected != EngineState.SLEEPING:
                await sleep_engine(mode, level=DEFAULT_BOOTSTRAP_SLEEP_LEVEL)
        except Exception:
            logger.exception(
                "Bootstrap: failed to put %s into initial sleep state", mode
            )

    logger.info(
        "Bootstrap complete: current_mode=%s engine_states=%s",
        state.current_mode,
        state.engine_states,
    )


async def shutdown_orchestrator() -> None:
    """Run during FastAPI lifespan shutdown."""
    logger.info("Shutting down orchestrator")

    await maybe_cancel_vision_idle_task()
    await maybe_cancel_audio_idle_task()

    # Optionally sleep secondary engines on shutdown (best-effort)
    for mode in list(MODE_URLS):
        if mode == PRIMARY_MODE:
            continue
        try:
            detected = await detect_engine_state(mode)
            state.engine_states[mode] = detected.value
            if detected != EngineState.SLEEPING:
                await sleep_engine(mode, level=DEFAULT_IDLE_SLEEP_LEVEL)
        except Exception:
            logger.exception("Failed to sleep mode=%s during shutdown", mode)

    await close_http_client()
    logger.info("Orchestrator shutdown complete")


# =========================
# Debug / status
# =========================


async def get_orchestrator_status() -> dict:
    """Payload for the ``/debug/orchestrator`` endpoint."""
    now = time.monotonic()
    engine_states_live: Dict[str, str] = {}
    last_used: Dict[str, Optional[float]] = {}

    for mode in MODE_URLS:
        try:
            detected = await detect_engine_state(mode)
            state.engine_states[mode] = detected.value
        except Exception:
            detected_str = EngineState.UNKNOWN.value
        else:
            detected_str = detected.value
        engine_states_live[mode] = detected_str

        ts = state.last_used_at.get(mode, 0.0)
        last_used[mode] = None if ts == 0.0 else round(now - ts, 3)

    return {
        "current_mode": state.current_mode,
        "warm_task_active": bool(
            state.warm_task and not state.warm_task.done()
        ),
        "engine_states": engine_states_live,
        "last_used_ago_sec": last_used,
    }
