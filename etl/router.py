from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import ValidationError
import asyncio
import json
from schemas import (
    JobSubmitRequest,
    JobSubmitResponse,
    JobStatusResponse,
    ReindexRequest,
    AnalyzeChatsRequest,
)
from manager import JobManager
from loguru import logger
from typing import Optional
from etl.db.chats import get_latest_graph_cache
from etl.schemas import GraphData
from shared.config import Config

router = APIRouter()


@router.post("/jobs/{source_type}", response_model=JobSubmitResponse, tags=["Jobs"])
async def submit_job(source_type: str, request: JobSubmitRequest):
    manager = JobManager()
    if source_type not in manager.sources:
        raise HTTPException(
            status_code=400, detail=f"Unknown source type: {source_type}"
        )

    job_id = await manager.submit_job(source_type, request.params)
    return JobSubmitResponse(job_id=job_id, status="queued")


@router.get("/jobs/{job_id}", response_model=JobStatusResponse, tags=["Jobs"])
async def get_job_status(job_id: str):
    manager = JobManager()
    status = manager.get_job(job_id)
    if not status:
        raise HTTPException(status_code=404, detail="Job not found")
    return status


@router.get("/jobs/stream/{job_id}", tags=["Jobs"])
async def stream_job_status(job_id: str, request: Request):
    manager = JobManager()

    async def event_generator():
        try:
            while True:
                if await request.is_disconnected():
                    break
                status = manager.get_job(job_id)
                if not status:
                    yield f"data: {json.dumps({'error': 'Job not found'})}\n\n"
                    break
                yield f"data: {status.model_dump_json()}\n\n"
                if status.status in ("completed", "failed"):
                    break
                await asyncio.sleep(1.0)
        except asyncio.CancelledError:
            raise
        except Exception as e:
            logger.error(f"Error in /jobs/stream/{job_id}: {e}")
            raise

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache, no-transform", "X-Accel-Buffering": "no"},
    )


@router.get("/health", tags=["System"])
async def health():
    return {"status": "ok", "service": "etl"}


@router.get("/sources/{source_type}/dialogs", tags=["Sources"])
async def get_source_dialogs(source_type: str, limit: Optional[int] = None):
    """
    Fetch dialogs from a source.

    Args:
        source_type: Type of source (e.g., 'telegram')
        limit: Maximum number of dialogs to fetch. None = fetch all.

    Returns:
        Dictionary with 'dialogs' list containing all fetched dialogs.
    """
    manager = JobManager()
    source_cls = manager.sources.get(source_type)
    if not source_cls:
        raise HTTPException(status_code=400, detail="Unknown source type")

    if source_type == "telegram" and (
        not Config.TELEGRAM_API_ID or not Config.TELEGRAM_API_HASH
    ):
        raise HTTPException(
            status_code=503,
            detail="Telegram credentials not configured. Set TELEGRAM_API_ID and TELEGRAM_API_HASH in .env (see https://my.telegram.org/apps).",
        )

    source = source_cls()
    try:
        await source.connect()
        dialogs = await source.get_dialogs(limit)
        logger.info(f"Fetched {len(dialogs)} dialogs from {source_type}")
        return {"dialogs": dialogs}
    except Exception as e:
        logger.error(f"Error fetching dialogs: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        await source.disconnect()


@router.post("/analyze-chats", response_model=JobSubmitResponse, tags=["Analysis"])
async def analyze_chats(request: AnalyzeChatsRequest):
    """
    Run chat analysis (description + tags) for the given chat_ids only.
    Requires non-empty chat_ids (use the dialog to select chats).
    """
    if not request.chat_ids:
        raise HTTPException(
            status_code=400,
            detail="chat_ids is required and must be non-empty",
        )
    manager = JobManager()
    job_id = await manager.submit_analyze_chats_job(request.chat_ids)
    return JobSubmitResponse(job_id=job_id, status="queued")


@router.post("/reindex-media", response_model=JobSubmitResponse, tags=["Analysis"])
async def reindex_media(request: Optional[ReindexRequest] = None):
    """
    Triggers reindexing of all media files in the database.
    Uses the job system to track progress.
    """
    if request is None:
        request = ReindexRequest()

    manager = JobManager()

    params = {
        "media_types": request.media_types,
        "force_reindex": request.force_reindex,
    }

    job_id = await manager.submit_job("reindex_media", params)
    return JobSubmitResponse(job_id=job_id, status="queued")


# --- Graph Analysis ---


@router.post("/graph/build", tags=["Graph"])
async def build_graph(force_rebuild: bool = False):
    """
    Triggers social graph analysis.
    Aggregates user messages, computes embeddings & similarity,
    builds a NetworkX graph, and caches the result.
    """
    from etl.processing.graph import GraphAnalyzer

    try:
        analyzer = GraphAnalyzer()
        return await analyzer.build(force_rebuild=force_rebuild)
    except Exception as e:
        logger.exception("Graph build failed with unexpected error")
        raise HTTPException(
            status_code=500,
            detail=f"Graph build error: {str(e)}",
        )


@router.get("/graph/data", tags=["Graph"])
async def get_graph_data():
    """Returns the latest cached graph data, or 404."""

    try:
        cached = await get_latest_graph_cache()
        if not cached:
            logger.warning("No graph data found in database cache")
            raise HTTPException(
                status_code=404,
                detail="No graph data found. POST /graph/build first.",
            )
        graph_json = (
            cached.graph_json if hasattr(cached, "graph_json") else cached["graph_json"]
        )
        return GraphData.model_validate_json(graph_json)
    except HTTPException:
        raise
    except ValidationError as e:
        logger.error(f"Failed to parse cached graph JSON: {e}")
        raise HTTPException(status_code=500, detail="Corrupted graph cache")
    except Exception as e:
        logger.exception("Unexpected error fetching graph data")
        raise HTTPException(status_code=500, detail=str(e))
