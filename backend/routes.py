"""
API routers. Handlers are thin: validate, call service, map errors to HTTP.
"""

import asyncio
from typing import Optional, List

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse
from sse_starlette.sse import EventSourceResponse
from loguru import logger
from pydantic import BaseModel

from backend.models import (
    GenerateRequest,
    GenerateResponse,
    ImageAnalysisRequest,
    ImageAnalysisResponse,
    AudioTranscriptionRequest,
    AudioTranscriptionResponse,
    PDFAnalysisRequest,
    PDFAnalysisResponse,
    EmbeddingRequest,
    EmbeddingResponse,
    ChatCompletionRequest,
    Chat,
    Contact,
    VideoAnalysisRequest,
    VideoAnalysisResponse,
    Session,
    CreateSessionRequest,
    SendSessionMessageResponse,
    SystemStatusResponse,
    ModelNotReadyError,
    SessionNotFoundError,
)
from backend.task_queue import (
    EnqueueRequest,
    BulkEnqueueRequest,
    ProcessingTask,
    ProcessingQueueManager,
    TaskStatusResponse,
    TaskResultItem,
)
import backend.service as svc
from shared.config import Config

router = APIRouter()


# --- Request bodies (route-specific) ---


class SendSessionMessageRequest(BaseModel):
    content: str
    context_chat_id: Optional[int] = None


class ConfigUpdate(BaseModel):
    VISION_PROVIDER: Optional[str] = None


# --- Chats & Contacts ---


@router.get("/chats", response_model=List[Chat], tags=["Chats"])
async def list_chats(limit: int = 50, offset: int = 0, min_importance: float = 0.0):
    """List chats, optionally filtered by importance."""
    logger.info(
        f"LIST CHATS: limit={limit}, offset={offset}, min_importance={min_importance}"
    )
    try:
        chats = await svc.list_chats(limit, offset, min_importance)
        logger.info(f"LIST CHATS: Found {len(chats)} chats")
        return chats
    except Exception as e:
        logger.error(f"Failed to fetch chats: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/chat/{source_id}", response_model=Chat, tags=["Chats"])
async def get_chat_details(source_id: int):
    chat = await svc.get_chat_by_id(source_id)
    if not chat:
        raise HTTPException(status_code=404, detail="Chat not found")
    return chat


@router.get("/contacts", response_model=List[Contact], tags=["Contacts"])
async def list_contacts(limit: int = 50, offset: int = 0):
    """List contacts."""
    try:
        return await svc.list_contacts(limit, offset)
    except Exception as e:
        logger.error(f"Failed to fetch contacts: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/contact/{source_id}", response_model=Contact, tags=["Contacts"])
async def get_contact_details(source_id: int):
    contact = await svc.get_contact_by_id(source_id)
    if not contact:
        raise HTTPException(status_code=404, detail="Contact not found")
    return contact


@router.get("/chat/{source_id}/messages", tags=["Chats"])
async def get_messages(source_id: int, limit: int = 50, offset: int = 0):
    logger.info(f"GET MESSAGES: chat_id={source_id}, limit={limit}, offset={offset}")
    try:
        messages = await svc.get_chat_messages(source_id, limit, offset)
        logger.info(
            f"GET MESSAGES: Found {len(messages)} messages for chat {source_id}"
        )
        return messages
    except Exception as e:
        logger.error(f"Failed to fetch messages for chat {source_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# --- Sessions ---


@router.get("/sessions", response_model=List[Session], tags=["Sessions"])
async def list_sessions(limit: int = 50, offset: int = 0):
    """List AI sessions."""
    try:
        return await svc.list_sessions(limit, offset)
    except Exception as e:
        logger.error(f"Failed to fetch sessions: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/sessions", response_model=Session, tags=["Sessions"])
async def create_new_session(request: CreateSessionRequest):
    """Create a new session."""
    try:
        return await svc.create_session(
            request.id,
            request.title,
            request.context_chat_id,
            request.meta,
        )
    except Exception as e:
        logger.error(f"Failed to create session: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/session/{session_id}", response_model=Session, tags=["Sessions"])
async def get_session_details(session_id: str):
    session = await svc.get_session_by_id(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    return session


@router.get("/session/{session_id}/messages", tags=["Sessions"])
async def get_session_messages_route(session_id: str, limit: int = 50, offset: int = 0):
    """Fetches messages for a session."""
    try:
        return await svc.get_session_messages_list(session_id, limit, offset)
    except Exception as e:
        logger.error(f"Failed to fetch messages for session {session_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post(
    "/session/{session_id}/messages",
    response_model=SendSessionMessageResponse,
    tags=["Sessions"],
)
async def send_session_message(session_id: str, request: SendSessionMessageRequest):
    """Handles AI interaction in a session with tool calling support."""
    logger.info(f"Session {session_id}: Received message")
    try:
        return await svc.send_session_message(
            session_id, request.content, request.context_chat_id
        )
    except SessionNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ModelNotReadyError as e:
        raise HTTPException(status_code=503, detail=str(e))
    except Exception as e:
        logger.error(f"Session {session_id}: Failed to process message: {e}")
        import traceback

        logger.error(traceback.format_exc())
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/warm", tags=["System"])
async def warm_model(mode: str = "text"):
    """Forward pre-warm request to model orchestrator."""
    import httpx

    base = Config.LLM_SERVER_URL
    if not base:
        return {"status": "unavailable"}
    # Strip /v1 suffix to reach orchestrator root
    orchestrator_url = base.rstrip("/").removesuffix("/v1")
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.post(
                f"{orchestrator_url}/warm",
                params={"mode": mode},
            )
            return resp.json()
    except Exception:
        return {"status": "unavailable"}


# --- Documents ---


@router.get("/documents", tags=["Documents"])
async def list_documents(
    limit: int = 50, offset: int = 0, media_type: str | None = None
):
    try:
        return await svc.list_documents(limit, offset, media_type)
    except Exception as e:
        logger.error(f"Failed to fetch documents: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/documents/counts", tags=["Documents"])
async def document_counts():
    try:
        return await svc.document_counts()
    except Exception as e:
        logger.error(f"Failed to fetch document counts: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# --- Config & Health ---


@router.get("/config", tags=["Config"])
async def get_config():
    """Returns current configuration (sanitized)."""
    return svc.get_config_sanitized()


@router.post("/config", tags=["Config"])
async def update_config(update: ConfigUpdate):
    """Updates configuration."""
    updates = {}
    if update.VISION_PROVIDER:
        updates["VISION_PROVIDER"] = update.VISION_PROVIDER
    config = svc.update_config_sanitized(updates)
    return {"status": "updated", "config": config}


@router.get("/health", tags=["System"])
async def health():
    return svc.health_status()


@router.get("/system/status", response_model=SystemStatusResponse, tags=["System"])
async def system_status(request: Request):
    # logger.info("Received /system/status request")
    scheduler = getattr(request.app.state, "scheduler", None)
    data = svc.get_system_status(scheduler)
    # logger.info(f"Sending /system/status data: {data.model_dump_json()}")
    return data


@router.get("/system/status/stream", tags=["System"])
async def system_status_stream(request: Request):
    logger.info("Client connected to /system/status/stream")
    scheduler = getattr(request.app.state, "scheduler", None)

    async def event_generator():
        try:
            while True:
                if await request.is_disconnected():
                    logger.info("Client disconnected from /system/status/stream")
                    break
                data = svc.get_system_status(scheduler)
                # logger.info(f"Generated status data: {data}")
                yield {"data": data.model_dump_json()}
                await asyncio.sleep(3)
        except asyncio.CancelledError:
            logger.info("Stream await cancelled for /system/status/stream")
            raise
        except Exception as e:
            logger.error(f"Error in /system/status/stream generator: {e}")
            raise

    return EventSourceResponse(
        event_generator(),
        headers={"Cache-Control": "no-cache, no-transform", "X-Accel-Buffering": "no"},
    )


# --- Inference ---


@router.post("/generate", response_model=GenerateResponse, tags=["Inference"])
async def generate_text(request: GenerateRequest):
    logger.info(f"Received /generate request: {request}")
    try:
        result = await svc.generate_text(request)
        logger.info(f"Generated text response length: {len(result.text)}")
        return result
    except Exception as e:
        logger.error(f"Generation error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/analyze-image", response_model=ImageAnalysisResponse, tags=["Inference"])
async def analyze_image(request: ImageAnalysisRequest):
    logger.info(f"Received /analyze-image request for: {request.image_path}")
    try:
        return await svc.analyze_image(request)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Image file not found")
    except Exception as e:
        logger.error(f"Image analysis error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/analyze-video", response_model=VideoAnalysisResponse, tags=["Inference"])
async def analyze_video(request: VideoAnalysisRequest):
    logger.info(f"Received /analyze-video request for: {request.video_path}")
    try:
        return await svc.analyze_video(request)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Video file not found")
    except Exception as e:
        logger.error(f"Video analysis error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post(
    "/transcribe-audio", response_model=AudioTranscriptionResponse, tags=["Inference"]
)
async def transcribe_audio(request: AudioTranscriptionRequest):
    logger.info(f"Received /transcribe-audio request for: {request.audio_path}")
    try:
        return await svc.transcribe_audio(request)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Audio file not found")
    except Exception as e:
        logger.error(f"Audio transcription error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/analyze-pdf", response_model=PDFAnalysisResponse, tags=["Inference"])
async def analyze_pdf(request: PDFAnalysisRequest):
    logger.info(f"Received /analyze-pdf request for: {request.pdf_path}")
    try:
        return await svc.analyze_pdf(request)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="PDF file not found")
    except Exception as e:
        logger.error(f"PDF analysis error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/v1/embeddings", response_model=EmbeddingResponse, tags=["Inference"])
async def create_embeddings(request: EmbeddingRequest):
    logger.info(f"Received /v1/embeddings request. Input type: {type(request.input)}")
    try:
        return await svc.create_embeddings(request)
    except Exception as e:
        logger.error(f"Embedding error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# --- Task Queue ---


@router.post("/tasks/enqueue", response_model=dict, tags=["Task Queue"])
async def enqueue_task(request: EnqueueRequest):
    """Submit a media-processing task to the model-aware queue."""
    task = ProcessingTask(
        job_id=request.job_id,
        model_type=request.model_type,
        task_subtype=request.task_subtype,
        source_id=request.source_id,
        doc_id=request.doc_id,
        input_path=request.input_path,
        input_params=request.input_params,
    )
    qm = ProcessingQueueManager()
    qm.enqueue(task)
    return {"task_id": task.task_id}


@router.post("/tasks/enqueue/bulk", response_model=dict, tags=["Task Queue"])
async def enqueue_bulk(request: BulkEnqueueRequest):
    """Submit multiple media-processing tasks to the model-aware queue."""
    if not request.tasks:
        return {"task_ids": []}

    qm = ProcessingQueueManager()
    tasks = []
    task_ids = []
    
    for req in request.tasks:
        task = ProcessingTask(
            job_id=req.job_id,
            model_type=req.model_type,
            task_subtype=req.task_subtype,
            source_id=req.source_id,
            doc_id=req.doc_id,
            input_path=req.input_path,
            input_params=req.input_params,
        )
        tasks.append(task)
        task_ids.append(task.task_id)

    qm.enqueue_bulk(tasks)
    return {"task_ids": task_ids}


@router.post("/tasks/seal/{job_id}", tags=["Task Queue"])
async def seal_job(job_id: str):
    """Signal that all tasks for this job have been submitted."""
    qm = ProcessingQueueManager()
    qm.seal_job(job_id)
    return {"status": "sealed", "job_id": job_id}


@router.get(
    "/tasks/status/{job_id}", response_model=TaskStatusResponse, tags=["Task Queue"]
)
async def task_status(job_id: str):
    """Get completion status for all tasks belonging to a job."""
    qm = ProcessingQueueManager()
    return qm.get_job_status(job_id)


@router.get(
    "/tasks/status/stream/{job_id}", tags=["Task Queue"]
)
async def task_status_stream(job_id: str, request: Request):
    """Stream completion status for all tasks belonging to a job."""
    qm = ProcessingQueueManager()

    async def event_generator():
        try:
            while True:
                if await request.is_disconnected():
                    break
                status = qm.get_job_status(job_id)
                yield {"data": status.model_dump_json()}
                if status.done:
                    break
                await asyncio.sleep(1.0)
        except asyncio.CancelledError:
            raise
        except Exception as e:
            logger.error(f"Error in /tasks/status/stream generator: {e}")
            raise

    return EventSourceResponse(
        event_generator(),
        headers={"Cache-Control": "no-cache, no-transform", "X-Accel-Buffering": "no"},
    )


@router.get(
    "/tasks/results/{job_id}", response_model=List[TaskResultItem], tags=["Task Queue"]
)
async def task_results(job_id: str):
    """Get results for all tasks belonging to a job."""
    qm = ProcessingQueueManager()
    return qm.get_job_results(job_id)


@router.post("/v1/chat/completions", tags=["Inference"])
async def chat_completions(request: ChatCompletionRequest):
    logger.info(
        f"Received /v1/chat/completions request. Model: {request.model}, Stream: {request.stream}"
    )
    if request.stream:

        async def stream_generator():
            async for chunk_json in svc.chat_completions_stream(request):
                yield f"data: {chunk_json}\n\n"
            yield "data: [DONE]\n\n"

        return StreamingResponse(stream_generator(), media_type="text/event-stream")
    try:
        return await svc.chat_completions_non_stream(request)
    except Exception as e:
        logger.error(f"Chat completion error: {e}")
        raise HTTPException(status_code=500, detail=str(e))
