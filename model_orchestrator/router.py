"""Route handlers for the model orchestrator API."""

import json
import logging

from fastapi import APIRouter, Request, Response

from config import MODE_URLS, WHISPER_BACKEND_URL
from exceptions import OrchestratorError, UnknownModeError
from models import (
    HealthResponse,
    ModelListResponse,
    ModelObject,
    StatusResponse,
    state,
)
from services import (
    classify_openai_payload,
    ensure_mode,
    get_backend_url,
    get_orchestrator_status,
    route_request_mode,
)

logger = logging.getLogger("orchestrator")

router = APIRouter()


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


@router.post("/v1/chat/completions", tags=["Proxy"])
async def chat_completions(request: Request):
    body = getattr(request.state, "proxy_body", await request.body())
    try:
        payload = json.loads(body)
    except json.JSONDecodeError:
        payload = {}

    try:
        target_mode = await route_request_mode(payload)
    except UnknownModeError as exc:
        logger.error("Unknown mode in payload: %s", exc)
        return Response(status_code=400, content=str(exc))
    except OrchestratorError as exc:
        logger.error("Mode switch failed: %s", exc)
        return Response(
            status_code=503,
            headers={"Retry-After": "10"},
            content=f"Service Unavailable: {exc}",
        )
    except Exception as exc:
        logger.error("Failed to switch mode: %s", exc, exc_info=True)
        return Response(
            status_code=503,
            headers={"Retry-After": "10"},
            content="Service Unavailable: failed to switch model",
        )

    backend_url = get_backend_url(target_mode)
    request.state.proxy_url = f"{backend_url}/v1/chat/completions"
    return Response(status_code=204)


@router.post("/v1/audio/transcriptions", tags=["Proxy"])
async def audio_transcriptions(request: Request):
    # Audio is handled by a separate whisper container; no sleep/wake.
    request.state.proxy_url = f"{WHISPER_BACKEND_URL}/v1/audio/transcriptions"
    return Response(status_code=204)


@router.get(
    "/v1/models",
    response_model=ModelListResponse,
    tags=["Models"],
)
async def list_models():
    if state.current_mode and state.current_mode in MODE_URLS:
        models = [ModelObject(id=state.current_mode)]
    else:
        models = []
    return ModelListResponse(data=models)


@router.get(
    "/health",
    response_model=HealthResponse,
    tags=["System"],
)
async def health():
    """Lightweight liveness check (used by Docker healthcheck)."""
    return HealthResponse(status="ok")


@router.get(
    "/status",
    response_model=StatusResponse,
    tags=["System"],
)
async def status():
    """Detailed orchestrator status."""
    return StatusResponse(
        status="ok",
        current_mode=state.current_mode,
        switching=state.lock.locked(),
        available_modes=list(MODE_URLS.keys()),
        engine_states=state.engine_states,
    )


@router.post("/warm", tags=["System"])
async def warm_model(mode: str = "text"):
    """Pre-warm a model worker (singleflight)."""
    if mode not in MODE_URLS:
        return Response(status_code=400, content=f"Unknown mode: {mode}")
    if state.current_mode == mode:
        return {"status": "already_warm", "mode": mode}
    try:
        await ensure_mode(mode)
        return {"status": "warm", "mode": mode}
    except OrchestratorError as exc:
        logger.error("Warm failed for %s: %s", mode, exc)
        return Response(
            status_code=503,
            content=f"Service Unavailable: {exc}",
        )
    except Exception as exc:
        logger.error("Warm failed for %s: %s", mode, exc, exc_info=True)
        return Response(status_code=503, content=str(exc))


@router.get("/debug/orchestrator", tags=["Debug"])
async def debug_orchestrator():
    """Live engine states, last-used timestamps and singleflight status."""
    return await get_orchestrator_status()
