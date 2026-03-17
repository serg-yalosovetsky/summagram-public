import json
from datetime import datetime
from typing import Optional, List, Dict, Any, Union
from pydantic import BaseModel, Field, field_validator, model_validator
from backend.utils import time_str_to_seconds, seconds_to_time_str
# --- Event Models ---


class BaseEvent(BaseModel):
    title: str = Field(..., description="Concise title of the event")
    start_time: str = Field(..., description="ISO8601 start time")
    end_time: str = Field(..., description="ISO8601 end time")
    # We keep payload separate in DB, but here we can define specific types


class DebtEvent(BaseEvent):
    amount: float
    currency: str
    debtor: str = Field(..., description="Who owes or is owed")
    direction: str = Field(..., description="'i_owe' or 'they_owe'")


class InterviewEvent(BaseEvent):
    company_name: str
    interviewer_name: Optional[str] = None
    meeting_link: Optional[str] = None
    interview_type: str = Field(
        ..., description="hr, technical, behavioral, system_design"
    )


class TopUpEvent(BaseEvent):
    service_name: str = Field(..., description="phone, internet, subscription")
    amount_needed: Optional[float] = None


# --- Sync Models ---


class SyncState(BaseModel):
    source_id: str
    last_synced_at: datetime
    last_msg_id: int  # or string depending on source, but Telethon uses int
    meta: Dict[str, Any] = {}


class TelegramMediaMetadata(BaseModel):
    type: str
    extension: Optional[str] = None
    path: Optional[str] = None
    description: Optional[str] = None
    size: Optional[int] = None
    mime: Optional[str] = None
    duration: Optional[float] = None
    title: Optional[str] = None
    performer: Optional[str] = None
    width: Optional[int] = None
    height: Optional[int] = None
    is_meme: Optional[bool] = None
    is_portrait: Optional[bool] = None
    tags: Optional[List[str]] = None
    url: Optional[str] = None
    # Video/Deep Analysis specific
    summary: Optional[str] = None
    transcript: Optional[str] = None
    translation: Optional[str] = None
    ocr_text: Optional[str] = None


class TelegramMetadata(BaseModel):
    sender_id: Optional[int] = None
    sender_name: str
    recipient_id: Optional[int] = None
    recipient_name: Optional[str] = None
    forward_from_id: Optional[int] = None
    forward_from_name: Optional[str] = None
    chat_id: int
    chat_title: str
    is_from_me: bool
    reply_to_msg_id: Optional[int] = None
    media: Optional[TelegramMediaMetadata] = None


class TelegramNodeMetadata(BaseModel):
    source_id: str
    timestamp: str
    author: str
    recipient: Optional[str] = None
    forwarded_from: Optional[str] = None
    is_from_me: bool
    original_text: str
    reply_to_id: Optional[int] = None
    media: Optional[str] = None  # JSON string if media exists
    tags: Optional[List[str]] = None
    media_url: Optional[str] = None


class GenericDocument(BaseModel):
    """
    Source-agnostic document format.
    """

    source_id: str
    doc_id: str  # Unique ID within source
    content: str
    timestamp: datetime
    metadata: Dict[str, Any] = {}


class GenerateRequest(BaseModel):
    prompt: str
    system_prompt: Optional[str] = None
    max_tokens: int = 2048
    temperature: float = 0.1


class GenerateResponse(BaseModel):
    text: str


class ImageAnalysisRequest(BaseModel):
    image_path: str
    prompt: Optional[str] = None


class ImageAnalysisResult(BaseModel):
    description: str = Field(
        ..., description="Factual description of the scene", max_length=500
    )
    is_meme: bool = Field(False, description="Whether the image is a meme")
    is_portrait: bool = Field(False, description="Whether it's a portrait of a person")
    detected_objects: List[str] = Field(
        default_factory=list, description="List of detected objects"
    )
    ocr_text: Optional[str] = Field(
        None, description="Extracted text from image", max_length=2000
    )
    nsfw_score: Optional[float] = Field(None, description="NSFW confidence score")
    context_tags: List[str] = Field(default_factory=list, description="Semantic tags")
    detected_language: Optional[str] = Field(
        None, description="Language code, e.g. 'uk-UA', 'en-US'", max_length=10
    )


class ImageAnalysisResponse(BaseModel):
    description: str
    structured_analysis: Optional[ImageAnalysisResult] = None


class VideoAnalysisRequest(BaseModel):
    video_path: str
    adaptive_fps: Optional[float] = 1.0
    use_scene_detection: bool = True


class VideoTemporalSegment(BaseModel):
    start_time: float
    end_time: float
    description: str
    transcript: Optional[str] = None


# --- Модели ---


class VideoSegment(BaseModel):
    start_time: str = Field(description="Start time in MM:SS format")
    end_time: str = Field(description="End time in MM:SS format")
    description: str


class VideoAnalysisResult(BaseModel):
    summary: str
    transcript: str
    segments: List[VideoTemporalSegment] = []
    metadata: Dict[str, Any] = {}

    @model_validator(mode="after")
    def enforce_continuity(self):
        """
        Автоматически исправляет таймкоды:
        1. Первый сегмент всегда начинается с 00:00.
        2. Начало следующего сегмента всегда равно концу предыдущего.
        """
        if not self.segments:
            return self

        # 1. Фиксим первый сегмент (всегда 00:00)
        first_seg = self.segments[0]
        if first_seg.start_time != "00:00":
            # Можно логировать предупреждение здесь
            first_seg.start_time = "00:00"

        # 2. Сшиваем остальные сегменты
        for i in range(1, len(self.segments)):
            prev_seg = self.segments[i - 1]
            curr_seg = self.segments[i]

            # Если начало текущего не совпадает с концом предыдущего -> исправляем текущий
            if curr_seg.start_time != prev_seg.end_time:
                curr_seg.start_time = prev_seg.end_time

                # Дополнительная защита: если после исправления start стал больше end (глюк LLM),
                # сдвигаем end текущего сегмента
                start_sec = time_str_to_seconds(curr_seg.start_time)
                end_sec = time_str_to_seconds(curr_seg.end_time)

                if end_sec <= start_sec:
                    # Например, добавляем минимум 5 секунд или берем длительность из описания
                    # Тут простое решение: сдвигаем конец на +10 сек от начала
                    curr_seg.end_time = seconds_to_time_str(start_sec + 10)

        return self


class VideoAnalysisResponse(BaseModel):
    analysis: VideoAnalysisResult


class AudioTranscriptionRequest(BaseModel):
    audio_path: str


class AudioTranscriptionResponse(BaseModel):
    transcript: str
    language: str
    duration: float
    language_probability: Optional[float] = None
    transcription_confidence: Optional[float] = None
    cleaned_transcript: Optional[str] = None
    translation: Optional[str] = None


class PDFAnalysisRequest(BaseModel):
    pdf_path: str


class PDFAnalysisResponse(BaseModel):
    text: str
    metadata: Dict[str, Any] = {}
    tables: List[Any] = []
    images: List[Any] = []
    page_count: int = 0


class EmbeddingRequest(BaseModel):
    input: Union[str, List[str]]
    model: str = "default"


class ConfigSanitized(BaseModel):
    """Sanitized configuration exposed to clients."""

    LLM_MODEL: Optional[str] = None
    VISION_PROVIDER: str
    OLLAMA_VISION_MODEL: str
    EMBEDDING_MODEL: str


class EmbeddingResponse(BaseModel):
    object: str = "list"
    data: List[dict]
    model: str
    usage: dict


# --- Agent / Tool-calling (Guided JSON) ---


class PartialAgentResponse(BaseModel):
    """
    Parsed LLM output without validation. Used for recovery from thought-only responses
    where AgentResponse.model_validate_json would fail.
    """

    thought: Optional[str] = None
    tool_call: Optional[Dict[str, Any]] = None
    final_answer: Optional[str] = None


class ToolCall(BaseModel):
    """Schema for a single tool invocation from the LLM."""

    name: str = Field(..., description="Tool name, e.g. get_messages")
    arguments: Dict[str, Any] = Field(
        default_factory=dict, description="Tool arguments as key-value pairs"
    )


class AgentResponse(BaseModel):
    """Structured agent turn: thought (Chain-of-Thought), then either tool_call or final_answer."""

    thought: Optional[str] = Field(
        None, description="Short reasoning before acting (ReAct-style)"
    )
    tool_call: Optional[ToolCall] = Field(
        None, description="If set, the model wants to call a tool"
    )
    final_answer: Optional[str] = Field(
        None, description="If set, the model's reply to the user"
    )

    @model_validator(mode="after")
    def check_tool_or_answer(self) -> "AgentResponse":
        if not self.tool_call and not self.final_answer:
            raise ValueError(
                "Invalid response: You must provide either a 'tool_call' or a 'final_answer'. "
                "A 'thought' alone is not permitted."
            )
        return self


# --- Chat Completion Models (OpenAI Compatible) ---


class ChatMessage(BaseModel):
    role: str
    content: str


class ChatCompletionRequest(BaseModel):
    model: str = "default"
    messages: List[ChatMessage]
    temperature: float = 0.3
    max_tokens: int = 2048
    stream: bool = False


class ChatCompletionChoice(BaseModel):
    index: int
    message: ChatMessage
    finish_reason: Optional[str] = "stop"


class ChatCompletionResponse(BaseModel):
    id: str
    object: str = "chat.completion"
    created: int
    model: str
    choices: List[ChatCompletionChoice]
    usage: dict


class DeltaMessage(BaseModel):
    role: Optional[str] = None
    content: Optional[str] = None


class ChatCompletionChunkChoice(BaseModel):
    index: int
    delta: DeltaMessage
    finish_reason: Optional[str] = None


class ChatCompletionChunk(BaseModel):
    id: str
    object: str = "chat.completion.chunk"
    created: int
    model: str
    choices: List[ChatCompletionChunkChoice]


def _parse_json_list(val: Any) -> Optional[List[str]]:
    """Parse JSON string or comma-separated string to list of strings. DB stores tags/interests as TEXT."""
    if val is None:
        return None
    if isinstance(val, list):
        return [str(x) for x in val] if val else None
    if isinstance(val, str):
        s = val.strip()
        if not s:
            return None
        try:
            parsed = json.loads(s)
            return [str(x) for x in parsed] if isinstance(parsed, list) else [s]
        except (json.JSONDecodeError, TypeError):
            return [t.strip() for t in s.split(",") if t.strip()] or None
    return None


# --- Chat & Contact Models (Backend) ---


class Chat(BaseModel):
    id: Optional[int] = None
    source_id: int
    title: Optional[str] = None
    description: Optional[str] = None
    tags: Optional[List[str]] = None
    image_path: Optional[str] = None
    image_description: Optional[str] = None
    message_count_total: int = 0
    message_count_me: int = 0
    importance_score: float = 0.0
    is_private: bool = False
    last_analyzed_at: Optional[str] = None
    created_at: Optional[str] = None

    @field_validator("tags", mode="before")
    @classmethod
    def _parse_tags(cls, v: Any) -> Optional[List[str]]:
        return _parse_json_list(v)


class Contact(BaseModel):
    id: Optional[int] = None
    source_id: int
    name: Optional[str] = None
    username: Optional[str] = None
    phone: Optional[str] = None
    description: Optional[str] = None
    interests: Optional[List[str]] = None
    tags: Optional[List[str]] = None
    image_path: Optional[str] = None
    image_description: Optional[str] = None
    address: Optional[str] = None
    last_analyzed_at: Optional[str] = None
    created_at: Optional[str] = None

    @field_validator("interests", "tags", mode="before")
    @classmethod
    def _parse_list_fields(cls, v: Any) -> Optional[List[str]]:
        return _parse_json_list(v)


class ChatAnalysisResult(BaseModel):
    description: str
    tags: List[str]


class ContactAnalysisResult(BaseModel):
    description: str
    interests: List[str]
    tags: List[str]
    address: Optional[str] = None


# --- Referenced Message (for assistant responses about a specific message) ---


class ReferencedMessage(BaseModel):
    """Structured reference to a message the assistant is replying about."""

    chat_id: int
    doc_id: str
    content: str = ""
    media_url: Optional[str] = None
    media_type: Optional[str] = None
    description: Optional[str] = None
    sender_name: Optional[str] = None


# --- Session Models ---


class Session(BaseModel):
    id: str
    title: Optional[str] = None
    context_chat_id: Optional[int] = None
    meta: Optional[Dict[str, Any]] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


class CreateSessionRequest(BaseModel):
    id: str
    title: str
    context_chat_id: Optional[int] = None
    meta: Optional[Dict[str, Any]] = None


# --- Session Message Response ---


class SessionMessagePayload(BaseModel):
    """User or assistant message payload with timestamp."""

    role: str
    content: str
    timestamp: str


class AssistantMessagePayload(BaseModel):
    """Assistant message with optional referenced message."""

    role: str = "assistant"
    content: str
    timestamp: str
    referenced_message: Optional[ReferencedMessage] = None


class SendSessionMessageResponse(BaseModel):
    """Response from send_session_message: user and assistant messages."""

    user_message: SessionMessagePayload
    assistant_message: AssistantMessagePayload


# --- Domain Exceptions ---


class ModelNotReadyError(Exception):
    """Raised when the LLM circuit breaker is active because it recently failed."""

    pass


class SessionNotFoundError(Exception):
    """Raised when the requested session could not be found."""

    pass


# --- System Status ---


class GPUInfo(BaseModel):
    cuda_available: bool
    gpu_name: Optional[str] = None
    memory_total_mb: Optional[float] = None
    memory_allocated_mb: Optional[float] = None
    memory_reserved_mb: Optional[float] = None
    memory_free_mb: Optional[float] = None


class ModelsConfig(BaseModel):
    vision: Optional[str] = None
    text: Optional[str] = None
    embedding: Optional[str] = None


class SystemStatusResponse(BaseModel):
    queue: Dict[str, int]
    total_pending: int
    current_model: Optional[str] = None
    containers: List[Dict[str, Any]] = Field(default_factory=list)
    total_pending: int
    current_model: Optional[str] = None
    gpu: GPUInfo
    models_config: ModelsConfig
