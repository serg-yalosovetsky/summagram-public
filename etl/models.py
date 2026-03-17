from datetime import datetime
from typing import Optional, Dict, Any, Literal
from pydantic import BaseModel, Field

# --- Event Models ---


class BaseEvent(BaseModel):
    title: str = Field(..., description="Concise title of the event")
    start_time: str = Field(..., description="ISO8601 start time")
    end_time: str = Field(..., description="ISO8601 end time")
    description: Optional[str] = Field(
        None, description="Detailed description or summary of the event"
    )
    context: Optional[str] = Field(
        None, description="The specific text chunk or quote that led to this event"
    )
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
    type: str = "unknown"
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
    file_name: Optional[str] = None
    tags: Optional[str] = None  # Comma-separated string for ChromaDB compatibility
    url: Optional[str] = None
    language: Optional[str] = None
    language_probability: Optional[float] = None
    confidence: Optional[float] = None
    original_transcript: Optional[str] = None
    translation: Optional[str] = None


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


class TelegramLinkage(BaseModel):
    platform: Literal["telegram"] = "telegram"
    peer_id: int
    message_id: int
    chat_username: Optional[str] = None
    topic_id: Optional[int] = None


class TelegramNodeMetadata(BaseModel):
    # identity
    source_id: str
    chat_id: int  # authoritative peer_id
    doc_id: str  # canonical key = TextNode.id_ = message_id

    # time
    ts_unix_ms: int = Field(
        ..., description="Primary timestamp for sorting/range queries"
    )
    ts_iso: str = Field(..., description="ISO8601 for display")

    # authoring
    author: str
    is_from_me: bool
    recipient: Optional[str] = None
    forwarded_from: Optional[str] = None
    reply_to_doc_id: Optional[str] = None
    reply_to_message_id: Optional[int] = None

    # content
    original_text: str
    content_norm: str
    char_count: int
    approx_token_count: int
    lang_hint: Optional[Literal["ru", "uk", "en", "mixed"]] = None

    # media
    has_media: bool = False
    media: Optional[TelegramMediaMetadata] = None
    media_json: Optional[str] = None
    media_url: Optional[str] = None

    # retrieval helpers
    contains_question_mark: bool = False
    contains_link: bool = False
    tags_csv: Optional[str] = None

    # linkage for backlinks
    link: Optional[TelegramLinkage] = None

    # lifecycle
    ingested_at_unix_ms: int
    edited_at_unix_ms: Optional[int] = None
    deleted: bool = False


class ChromaMessageMeta(BaseModel):
    chat_id: int
    doc_id: str
    is_from_me: bool
    ts_unix_ms: int
    author: str
    has_media: bool = False
    tags_csv: Optional[str] = None


class GenericDocument(BaseModel):
    """
    Source-agnostic document format.
    """

    source_id: str
    doc_id: str  # Unique ID within source
    content: str
    timestamp: datetime
    metadata: Dict[str, Any] = {}


class ReindexParams(BaseModel):
    media_types: list[str] = Field(
        default_factory=lambda: ["photo", "audio", "document"]
    )
    force_reindex: bool = False


# --- Backend API response models (for parsing HTTP JSON) ---


class ImageAnalysisStructured(BaseModel):
    """Structured analysis from vision model (mirrors backend ImageAnalysisResult)."""

    description: str = ""
    is_meme: bool = False
    is_portrait: bool = False
    context_tags: list[str] = []


class ImageAnalysisResponse(BaseModel):
    """Response from backend /analyze-image endpoint."""

    description: str
    structured_analysis: ImageAnalysisStructured | None = None


class AudioTranscriptionResponse(BaseModel):
    """Response from backend /transcribe-audio endpoint."""

    transcript: str = ""
    language: str = ""
    duration: float = 0.0
    language_probability: float | None = None
    transcription_confidence: float | None = None
    cleaned_transcript: str | None = None
    translation: str | None = None


class PDFAnalysisResponse(BaseModel):
    """Response from backend /analyze-pdf endpoint."""

    text: str = ""
    page_count: int = 0
    metadata: Dict[str, Any] = {}


# --- Chat & Contact Models ---


class Chat(BaseModel):
    id: Optional[int] = None
    source_id: int
    title: Optional[str] = None
    description: Optional[str] = None
    tags: Optional[str] = None  # JSON list or comma-separated
    image_path: Optional[str] = None
    image_description: Optional[str] = None
    message_count_total: int = 0
    message_count_me: int = 0
    importance_score: float = 0.0
    is_private: bool = False
    last_analyzed_at: Optional[str] = None
    created_at: Optional[str] = None


class ConfigSanitized(BaseModel):
    """Sanitized configuration exposed to clients."""

    HF_MODEL_TEXT: str
    HF_MODEL_MEDIA: str
    VISION_PROVIDER: str
    OLLAMA_VISION_MODEL: str
    EMBEDDING_MODEL: str


class Contact(BaseModel):
    id: Optional[int] = None
    source_id: int
    name: Optional[str] = None
    username: Optional[str] = None
    phone: Optional[str] = None
    description: Optional[str] = None
    interests: Optional[str] = None  # JSON list or comma-separated
    tags: Optional[str] = None  # JSON list or comma-separated
    image_path: Optional[str] = None
    image_description: Optional[str] = None
    address: Optional[str] = None
    last_analyzed_at: Optional[str] = None
    created_at: Optional[str] = None


class ChatAnalysisResult(BaseModel):
    description: str
    tags: list[str]


class ContactAnalysisResult(BaseModel):
    description: str
    interests: list[str]
    tags: list[str]
    address: Optional[str] = None


class ChatMessageStats(BaseModel):
    """Message counts for a chat (total and from current user)."""

    total: int
    me: int


class RawDocumentRow(BaseModel):
    """Single raw document row from raw_documents (e.g. chat history item)."""

    content: str = ""
    timestamp: str = ""
    source_id: Optional[str] = None
    metadata: Dict[str, Any] = {}
    doc_id: str = ""


class GraphCacheRow(BaseModel):
    """Cached social graph row from social_graph_cache."""

    id: int
    graph_json: str
    node_count: int = 0
    edge_count: int = 0
    created_at: Optional[str] = None


class DownloadedRange(BaseModel):
    """Date range for downloaded chat messages."""

    start_date: str
    end_date: str


class SaveMessageResult(BaseModel):
    """Result of saving a message to raw_documents."""

    doc_id: str
    timestamp: str


class ChatSearchResult(BaseModel):
    """Result of find_chats_by_contact_name: chat with contact/chat title info."""

    chat_id: int
    contact_name: str
    chat_title: str
    is_private: bool


class Session(BaseModel):
    """AI session row from sessions table."""

    id: str
    title: Optional[str] = None
    context_chat_id: Optional[int] = None
    meta: Optional[Dict[str, Any]] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


class CreateSessionResult(BaseModel):
    """Result of create_session: minimal session info."""

    id: str
    title: str
