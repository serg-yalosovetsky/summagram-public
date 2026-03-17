"""
Backend application service layer.
Holds all business logic for API routes; routers remain thin and delegate here.
"""

import os
import shutil
import subprocess
import time
from datetime import datetime
from typing import Any, AsyncIterator, List, Optional
import torch
import openai

from loguru import logger

from shared.config import Config
from inference import LocalInferenceService

from backend.models import (
    Chat,
    ConfigSanitized,
    Contact,
    Session,
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
    ChatCompletionResponse,
    ChatCompletionChunk,
    ChatCompletionChoice,
    ChatCompletionChunkChoice,
    ChatMessage,
    DeltaMessage,
    VideoAnalysisRequest,
    VideoAnalysisResponse,
    SendSessionMessageResponse,
    SessionMessagePayload,
    AssistantMessagePayload,
    ReferencedMessage,
    SystemStatusResponse,
    GPUInfo,
    ModelsConfig,
    ModelNotReadyError,
    SessionNotFoundError,
)
from etl.db.chats import (
    get_chat,
    get_contact,
    get_chats,
    get_contacts,
    find_chats_by_contact_name as db_find_chats_by_contact_name,
)
from etl.db.raw_documents import (
    get_all_documents,
    get_document_counts_by_type,
    get_chat_history,
)
from etl.db.sessions import (
    get_sessions,
    get_session,
    create_session as db_create_session,
    get_session_messages,
    insert_session_message,
    update_session_updated_at,
)
from session_helpers import parse_message_metadata
from backend.session_agent import run_session_agent


# --- Chats & Contacts ---


async def list_chats(
    limit: int = 50, offset: int = 0, min_importance: float = 0.0
) -> List[Chat]:
    chats = await get_chats(limit, offset, min_importance)
    return [Chat(**c.model_dump()) for c in chats]


async def list_contacts(limit: int = 50, offset: int = 0) -> List[Contact]:
    contacts = await get_contacts(limit, offset)
    return [Contact(**c.model_dump()) for c in contacts]


async def get_chat_by_id(source_id: int) -> Optional[Chat]:
    chat = await get_chat(source_id)
    return Chat(**chat.model_dump()) if chat else None


async def get_contact_by_id(source_id: int) -> Optional[Contact]:
    contact = await get_contact(source_id)
    return Contact(**contact.model_dump()) if contact else None


async def get_chat_messages(source_id: int, limit: int = 50, offset: int = 0) -> list:
    return await get_chat_history(source_id, limit, offset)


async def get_chats_by_contact_name(query: str, limit: int = 10) -> list:
    """Resolve contact or chat name to list of ChatSearchResult (cross-script)."""
    return await db_find_chats_by_contact_name(query, limit=limit)


# --- Sessions ---


async def list_sessions(limit: int = 50, offset: int = 0) -> List[Session]:
    sessions = await get_sessions(limit, offset)
    return [Session(**s.model_dump()) for s in sessions]


async def create_session(
    session_id: str,
    title: str,
    context_chat_id: Optional[int] = None,
    meta: Optional[dict] = None,
) -> Session:
    await db_create_session(session_id, title, context_chat_id, meta)
    full = await get_session(session_id)
    return Session(**full.model_dump()) if full else Session(id=session_id, title=title)


async def get_session_by_id(session_id: str) -> Optional[Session]:
    session = await get_session(session_id)
    return Session(**session.model_dump()) if session else None


async def get_session_messages_list(
    session_id: str, limit: int = 50, offset: int = 0
) -> list:
    return await get_session_messages(session_id, limit, offset)


def _build_session_chat_messages(session_id: str) -> List[ChatMessage]:
    """Load last N session messages and map to ChatMessage list (user/assistant by sender_id)."""
    # build_session_chat_messages is async in plan but get_session_messages is async; make this async
    raise NotImplementedError("use async version")


async def build_session_chat_messages(
    session_id: str, limit: int = 10
) -> List[ChatMessage]:
    """Load last N session messages and map to ChatMessage list (user/assistant by sender_id)."""
    session_messages = await get_session_messages(session_id, limit=limit)
    out = []
    for sm in session_messages:
        meta = parse_message_metadata(sm.metadata)
        role = "user" if meta.get("sender_id") == "me" else "assistant"
        out.append(ChatMessage(role=role, content=sm.content or ""))
    return out


async def persist_user_message(
    session_id: str, content: str, context_chat_id: Optional[int]
) -> str:
    """Persist user message; returns timestamp for response."""
    timestamp = datetime.now().isoformat()
    doc_id = f"msg_{int(datetime.now().timestamp() * 1000)}"
    metadata: dict = {"session_id": session_id, "sender_id": "me", "is_from_me": True}
    if context_chat_id is not None:
        metadata["chat_id"] = context_chat_id
    await insert_session_message("ui_session", doc_id, content, timestamp, metadata)
    return timestamp


async def persist_assistant_message(
    session_id: str,
    content: str,
    context_chat_id: Optional[int],
    referenced_message: Optional[dict] = None,
) -> None:
    """Persist assistant message and update session updated_at."""
    assistant_doc_id = f"msg_{int(datetime.now().timestamp() * 1000) + 1}"
    assistant_metadata: dict = {
        "session_id": session_id,
        "sender_id": "assistant",
        "is_from_me": False,
    }
    if context_chat_id is not None:
        assistant_metadata["chat_id"] = context_chat_id
    if referenced_message is not None:
        assistant_metadata["referenced_message"] = referenced_message
    await insert_session_message(
        "ui_session",
        assistant_doc_id,
        content,
        datetime.now().isoformat(),
        assistant_metadata,
    )
    await update_session_updated_at(session_id)


# --- Circuit breaker for LLM calls ---


class LLMCircuitBreaker:
    """Trips only after *threshold* consecutive non-transient failures.

    Transient errors (e.g. 503 "busy") are NOT counted — they indicate
    the model is temporarily overloaded, not broken.
    """

    def __init__(
        self,
        cooldown: float = 15.0,
        threshold: int = 3,
    ) -> None:
        self._last_failure_time: float = 0.0
        self._cooldown: float = cooldown
        self._threshold: int = threshold
        self._consecutive_failures: int = 0

    def check(self) -> None:
        if self._consecutive_failures < self._threshold:
            return
        elapsed = time.time() - self._last_failure_time
        if elapsed < self._cooldown:
            raise ModelNotReadyError(
                f"Model is warming up, please retry in a moment "
                f"({self._consecutive_failures} consecutive failures, "
                f"last {elapsed:.0f}s ago)"
            )
        # Cooldown expired — reset
        self._consecutive_failures = 0

    def record_failure(self) -> None:
        self._consecutive_failures += 1
        self._last_failure_time = time.time()

    def record_success(self) -> None:
        self._consecutive_failures = 0
        self._last_failure_time = 0.0

    @staticmethod
    def is_transient(exc: Exception) -> bool:
        """Return True for transient/recoverable errors.

        Transient (do NOT count toward breaker):
        - 503  busy / warming
        - 429  rate-limited
        - timeouts (APITimeoutError)
        - connection errors (APIConnectionError)

        Non-transient (DO count toward breaker):
        - 500  server bug
        - other status codes

        Client errors (400/422) should not reach the breaker
        at all — they mean "fix the request", not "service down".
        """
        if isinstance(exc, openai.APITimeoutError):
            return True
        if isinstance(exc, openai.APIConnectionError):
            return True
        if isinstance(exc, openai.APIStatusError):
            return exc.status_code in (503, 429)
        return False


_llm_circuit_breaker = LLMCircuitBreaker()


async def send_session_message(
    session_id: str, content: str, context_chat_id: Optional[int] = None
) -> SendSessionMessageResponse:
    """
    Session chat with tool calling via LlamaIndex + SGLang.
    SGLang must be reachable at LLM_SERVER_URL (checked at startup).

    Includes a circuit-breaker: if the last ``threshold`` LLM calls
    failed within ``cooldown`` seconds, raises immediately instead
    of blocking another worker on a dead model.
    """
    _llm_circuit_breaker.check()

    session = await get_session(session_id)
    if not session:
        raise SessionNotFoundError(f"Session {session_id} not found")

    context_chat_id = context_chat_id or session.context_chat_id
    timestamp = await persist_user_message(session_id, content, context_chat_id)
    current_messages = await build_session_chat_messages(session_id, limit=10)

    try:
        assistant_content, referenced_message = await run_session_agent(
            session_id=session_id,
            context_chat_id=context_chat_id,
            message=content,
            chat_history=[m.model_dump() for m in current_messages[:-1]],
        )
    except openai.APIStatusError as exc:
        if not LLMCircuitBreaker.is_transient(exc):
            _llm_circuit_breaker.record_failure()
        logger.error(
            f"LLM call failed (API Error {exc.status_code}), "
            f"transient={LLMCircuitBreaker.is_transient(exc)}: {exc}"
        )
        raise ModelNotReadyError(str(exc))
    except Exception as exc:
        _llm_circuit_breaker.record_failure()
        logger.error(f"LLM call failed, circuit-breaker activated: {exc}")
        raise

    _llm_circuit_breaker.record_success()

    await persist_assistant_message(
        session_id, assistant_content, context_chat_id, referenced_message
    )

    user_msg = SessionMessagePayload(role="user", content=content, timestamp=timestamp)
    assistant_msg = AssistantMessagePayload(
        role="assistant",
        content=assistant_content,
        timestamp=datetime.now().isoformat(),
        referenced_message=ReferencedMessage.model_validate(referenced_message)
        if referenced_message
        else None,
    )
    return SendSessionMessageResponse(
        user_message=user_msg, assistant_message=assistant_msg
    )


# --- Documents ---


async def list_documents(
    limit: int = 50, offset: int = 0, media_type: str | None = None
) -> list:
    return await get_all_documents(limit, offset, media_type)


async def document_counts() -> dict:
    return await get_document_counts_by_type()


# --- Config & Health ---


def get_config_sanitized() -> ConfigSanitized:
    return ConfigSanitized(
        LLM_MODEL=Config.LLM_MODEL,
        VISION_PROVIDER=Config.VISION_PROVIDER,
        OLLAMA_VISION_MODEL=Config.OLLAMA_VISION_MODEL,
        EMBEDDING_MODEL=Config.EMBEDDING_MODEL,
    )


def update_config_sanitized(updates: dict) -> ConfigSanitized:
    if updates.get("VISION_PROVIDER"):
        Config.VISION_PROVIDER = updates["VISION_PROVIDER"]
    return get_config_sanitized()


def health_status() -> dict:
    return {"status": "ok", "model": Config.LLM_MODEL}


def _get_nvidia_smi_gpu_info() -> Optional[GPUInfo]:
    """Attempt to get GPU memory stats via nvidia-smi."""
    if not shutil.which("nvidia-smi"):
        return None

    cmd = [
        "nvidia-smi",
        "--query-gpu=name,memory.total,memory.used,memory.free",
        "--format=csv,noheader,nounits",
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, check=True)
    lines = result.stdout.strip().split("\n")
    if not lines:
        return None

    parts = [p.strip() for p in lines[0].split(",")]
    if len(parts) < 4:
        return None

    return GPUInfo(
        cuda_available=True,
        gpu_name=parts[0],
        memory_total_mb=float(parts[1]),
        memory_allocated_mb=float(parts[2]),
        memory_reserved_mb=float(parts[2]),
        memory_free_mb=float(parts[3]),
    )


def _get_torch_cuda_info() -> Optional[GPUInfo]:
    """Attempt to get GPU memory stats via PyTorch."""
    if not torch.cuda.is_available():
        return None

    props = torch.cuda.get_device_properties(0)
    total_mb = float(props.total_memory) / (1024**2)
    allocated_mb = float(torch.cuda.memory_allocated(0)) / (1024**2)
    reserved_mb = float(torch.cuda.memory_reserved(0)) / (1024**2)

    return GPUInfo(
        cuda_available=True,
        gpu_name=props.name,
        memory_total_mb=total_mb,
        memory_allocated_mb=allocated_mb,
        memory_reserved_mb=reserved_mb,
        memory_free_mb=total_mb - reserved_mb,
    )


def _get_gpu_info() -> GPUInfo:
    """Gather GPU information, trying nvidia-smi first, then torch.cuda."""
    try:
        if info := _get_nvidia_smi_gpu_info():
            return info
    except Exception as e:
        logger.warning(f"Failed to read GPU stats from nvidia-smi: {e}")

    try:
        if info := _get_torch_cuda_info():
            return info
    except Exception as e:
        logger.warning(f"Failed to read GPU stats from PyTorch: {e}")

    return GPUInfo(cuda_available=False)


def get_system_status(scheduler: Any) -> SystemStatusResponse:
    """Gather task queue sizes, active model, GPU memory, and model config."""
    # Local imports to avoid circular dependencies during initialization
    from backend.task_queue import ProcessingQueueManager
    from backend.system_stats import get_container_metrics

    queue_mgr = ProcessingQueueManager()
    queue_sizes = queue_mgr.get_queue_sizes()
    total_pending = sum(queue_sizes.values())

    # Map ContainerMetrics objects to dicts for the Pydantic model
    containers = [vars(c) for c in get_container_metrics(prefix="summagram_")]

    return SystemStatusResponse(
        queue=queue_sizes,
        total_pending=total_pending,
        current_model=scheduler.current_model if scheduler else None,
        containers=containers,
        gpu=_get_gpu_info(),
        models_config=ModelsConfig(
            vision=Config.OLLAMA_VISION_MODEL if Config.VISION_PROVIDER != "local" else Config.HF_MODEL_MEDIA,
            text=Config.LLM_MODEL or Config.HF_MODEL_TEXT,
            embedding=Config.EMBEDDING_MODEL,
        ),
    )


# --- Inference (generate, analyze, embed, chat) ---


async def generate_text(request: GenerateRequest) -> GenerateResponse:
    service = LocalInferenceService()
    text = await service.generate_text(
        prompt=request.prompt,
        system_prompt=request.system_prompt or "",
        max_tokens=request.max_tokens,
        temperature=request.temperature,
    )
    return GenerateResponse(text=text)


async def analyze_image(request: ImageAnalysisRequest) -> ImageAnalysisResponse:
    if not os.path.exists(request.image_path):
        raise FileNotFoundError(f"Image file not found: {request.image_path}")
    service = LocalInferenceService()
    return await service.analyze_image(request.image_path, request.prompt)


async def analyze_video(request: VideoAnalysisRequest) -> VideoAnalysisResponse:
    if not os.path.exists(request.video_path):
        raise FileNotFoundError(f"Video file not found: {request.video_path}")
    service = LocalInferenceService()
    analysis = await service.analyze_video(request)
    return VideoAnalysisResponse(analysis=analysis)


async def transcribe_audio(
    request: AudioTranscriptionRequest,
) -> AudioTranscriptionResponse:
    if not os.path.exists(request.audio_path):
        raise FileNotFoundError(f"Audio file not found: {request.audio_path}")
    service = LocalInferenceService()
    return await service.transcribe_audio(request.audio_path)


async def analyze_pdf(request: PDFAnalysisRequest) -> PDFAnalysisResponse:
    if not os.path.exists(request.pdf_path):
        raise FileNotFoundError(f"PDF file not found: {request.pdf_path}")
    service = LocalInferenceService()
    return await service.analyze_pdf_with_kreuzberg(request.pdf_path)


async def create_embeddings(request: EmbeddingRequest) -> EmbeddingResponse:
    service = LocalInferenceService()
    inputs = request.input if isinstance(request.input, list) else [request.input]
    embeddings = await service.get_embeddings(inputs)
    data = [
        {"object": "embedding", "embedding": emb, "index": i}
        for i, emb in enumerate(embeddings)
    ]
    return EmbeddingResponse(
        data=data,
        model=Config.EMBEDDING_MODEL,
        usage={"prompt_tokens": 0, "total_tokens": 0},
    )


async def chat_completions_non_stream(
    request: ChatCompletionRequest,
) -> ChatCompletionResponse:
    service = LocalInferenceService()
    generated_text = await service.generate_text_from_messages(
        messages=request.messages,
        max_tokens=request.max_tokens,
        temperature=request.temperature,
    )
    return ChatCompletionResponse(
        id=f"chatcmpl-{os.urandom(4).hex()}",
        created=int(time.time()),
        model=request.model,
        choices=[
            ChatCompletionChoice(
                index=0,
                message=ChatMessage(role="assistant", content=generated_text),
                finish_reason="stop",
            )
        ],
        usage={"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
    )


async def chat_completions_stream(
    request: ChatCompletionRequest,
) -> AsyncIterator[str]:
    """Yields SSE payload strings: each is JSON for one ChatCompletionChunk."""
    service = LocalInferenceService()
    request_id = f"chatcmpl-{os.urandom(4).hex()}"
    created_time = int(time.time())

    yield ChatCompletionChunk(
        id=request_id,
        created=created_time,
        model=request.model,
        choices=[
            ChatCompletionChunkChoice(
                index=0,
                delta=DeltaMessage(role="assistant", content=""),
                finish_reason=None,
            )
        ],
    ).model_dump_json()

    async for char in service.stream_generate_text_from_messages(
        messages=request.messages,
        max_tokens=request.max_tokens,
        temperature=request.temperature,
    ):
        chunk = ChatCompletionChunk(
            id=request_id,
            created=created_time,
            model=request.model,
            choices=[
                ChatCompletionChunkChoice(
                    index=0,
                    delta=DeltaMessage(content=char),
                    finish_reason=None,
                )
            ],
        )
        yield chunk.model_dump_json()

    yield ChatCompletionChunk(
        id=request_id,
        created=created_time,
        model=request.model,
        choices=[
            ChatCompletionChunkChoice(
                index=0,
                delta=DeltaMessage(),
                finish_reason="stop",
            )
        ],
    ).model_dump_json()
