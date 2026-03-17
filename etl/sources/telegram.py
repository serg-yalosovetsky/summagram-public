from loguru import logger
import os
import re
import json
from collections import namedtuple
from datetime import datetime, timezone, timedelta
from typing import AsyncGenerator, Any, Callable

import httpx
from telethon import TelegramClient
from telethon.tl.types import (
    Message,
    Document,
    DocumentAttributeAudio,
    DocumentAttributeFilename,
    DocumentAttributeVideo,
    MessageMediaDocument,
    MessageMediaPhoto,
)
from pydantic import BaseModel
from tenacity import retry, retry_base, stop_after_attempt, wait_fixed

ForwardInfo = namedtuple("ForwardInfo", ["sender_id", "from_name"])
ProcessMediaResult = namedtuple("ProcessMediaResult", ["media", "content_prefix"])

from .base import BaseSource
from prompts import Prompts
from shared.config import Config
from models import (
    Chat,
    Contact,
    GenericDocument,
    TelegramMetadata,
    TelegramMediaMetadata,
)
from etl.db.raw_documents import (
    get_downloaded_ranges,
    add_downloaded_range,
)
from etl.db.chats import (
    save_chat,
    save_contact,
    save_chat_member,
    get_chat_message_stats,
    get_chat,
    get_contact,
)


def get_backend_url(path: str) -> str:
    """Helper to get backend URL from BACKEND_URL config."""
    base = Config.BACKEND_URL.rstrip("/")
    return f"{base}/{path.lstrip('/')}"


MAX_CONTEXT_TOKENS = 8192
PROMPT_TEMPLATE_OVERHEAD_TOKENS = 200
DEFAULT_MAX_GENERATION_TOKENS = 2048
MAX_INPUT_TOKENS = (
    MAX_CONTEXT_TOKENS - DEFAULT_MAX_GENERATION_TOKENS - PROMPT_TEMPLATE_OVERHEAD_TOKENS
)


def _estimate_tokens(text: str) -> int:
    """Rough token estimate: ~3 chars per token for multilingual content."""
    return len(text) // 3


def _truncate_messages(
    message_sections: list[list[str]],
    max_tokens: int = MAX_INPUT_TOKENS,
) -> list[list[str]]:
    """
    Proportionally reduce messages per section so combined text fits max_tokens.
    Each section is a list of message strings. Returns truncated copies.
    """
    combined = "\n".join(msg for section in message_sections for msg in section)
    if _estimate_tokens(combined) <= max_tokens:
        return message_sections

    total_msgs = sum(len(s) for s in message_sections)
    if total_msgs == 0:
        return message_sections

    ratio = max_tokens / max(_estimate_tokens(combined), 1)
    truncated = []
    for section in message_sections:
        keep = max(1, int(len(section) * ratio))
        truncated.append(section[:keep])

    return truncated


class _retry_on_server_or_network_error(retry_base):
    """Retry on connection errors and 5xx; never retry 4xx (client error)."""

    def __call__(self, retry_state):
        exc = retry_state.outcome.exception()
        if exc is None:
            return False
        if isinstance(exc, httpx.RequestError):
            return True
        if isinstance(exc, httpx.HTTPStatusError):
            return exc.response.status_code >= 500
        return False


@retry(
    stop=stop_after_attempt(3),
    wait=wait_fixed(2),
    retry=_retry_on_server_or_network_error(),
    reraise=True,
)
async def generate_text_with_retry(
    prompt: str, max_tokens: int = 2048, temperature: float = 0.3
) -> str:
    """Generate text via backend /generate API."""
    async with httpx.AsyncClient(timeout=120.0) as client:
        resp = await client.post(
            get_backend_url("generate"),
            json={
                "prompt": prompt,
                "max_tokens": max_tokens,
                "temperature": temperature,
            },
        )
        resp.raise_for_status()
        return resp.json().get("text", "")


@retry(
    stop=stop_after_attempt(3),
    wait=wait_fixed(2),
    retry=_retry_on_server_or_network_error(),
    reraise=True,
)
async def transcribe_audio_with_retry(path: str) -> dict:
    async with httpx.AsyncClient(timeout=120.0) as client:
        resp = await client.post(
            get_backend_url("transcribe-audio"), json={"audio_path": path}
        )
        resp.raise_for_status()
        return resp.json()


@retry(
    stop=stop_after_attempt(3),
    wait=wait_fixed(2),
    retry=_retry_on_server_or_network_error(),
    reraise=True,
)
async def analyze_image_with_retry(path: str) -> dict:
    async with httpx.AsyncClient(timeout=60.0) as client:
        resp = await client.post(
            get_backend_url("analyze-image"), json={"image_path": path}
        )
        resp.raise_for_status()
        return resp.json()


def parse_vision_analysis(analysis_text: str) -> dict:
    """
    Robustly extracts JSON from vision model output.
    """
    # 1. Try to find JSON in markdown blocks
    json_match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", analysis_text, re.DOTALL)
    if json_match:
        try:
            return json.loads(json_match.group(1))
        except Exception:
            pass

    # 2. Try to find anything that looks like a JSON object
    json_match = re.search(r"(\{.*\})", analysis_text, re.DOTALL)
    if json_match:
        try:
            return json.loads(json_match.group(1))
        except Exception:
            pass

    # 3. Fallback: return as description
    return {"description": analysis_text}


class VisionAnalysisResult(BaseModel):
    """Structured result from vision model analysis."""

    description: str
    is_meme: bool = False
    is_portrait: bool = False
    tags: str | None = None  # Comma-separated tags


def _parse_vision_result(
    raw_response: dict, fallback_text: str
) -> VisionAnalysisResult:
    """
    Parse vision API response into structured result.

    Args:
        raw_response: Raw JSON response from vision API
        fallback_text: Fallback description if parsing fails

    Returns:
        VisionAnalysisResult with parsed data
    """
    parsed = parse_vision_analysis(raw_response.get("description", fallback_text))

    # Convert tags list to comma-separated string for ChromaDB compatibility
    tags_list = parsed.get("tags", [])
    tags_str = (
        ", ".join(tags_list) if isinstance(tags_list, list) and tags_list else None
    )

    return VisionAnalysisResult(
        description=parsed.get("description", fallback_text),
        is_meme=parsed.get("is_meme", False),
        is_portrait=parsed.get("is_portrait", False),
        tags=tags_str,
    )


class TelegramSource(BaseSource):
    def __init__(self, session_name: str = "summagram_session"):
        self.session_name = session_name
        self.client = TelegramClient(
            self.session_name, Config.TELEGRAM_API_ID, Config.TELEGRAM_API_HASH
        )
        self.phone = Config.TELEGRAM_PHONE
        self._current_job_id: str | None = None
        self._task_buffer: list[dict] = []

    def set_job_id(self, job_id: str) -> None:
        self._current_job_id = job_id

    _MEDIA_TYPE_TO_TASK: dict[str, tuple[str, str]] = {
        "photo": ("analyze_image", "vision"),
        "audio": ("transcribe_audio", "audio"),
        "voice": ("transcribe_audio", "audio"),
    }
    _ANALYZABLE_DOC_EXTS = frozenset(
        {"pdf", "docx", "pptx", "xlsx", "doc", "ppt", "xls"}
    )

    async def _enqueue_media_task(
        self, media: TelegramMediaMetadata, source_id: str, doc_id: str
    ) -> None:
        """Buffer a processing task for the backend queue (non-blocking)."""
        if not media.path or not self._current_job_id:
            return

        mapping = self._MEDIA_TYPE_TO_TASK.get(media.type)
        if not mapping and media.type == "document":
            ext = (media.extension or "").lower()
            if ext in self._ANALYZABLE_DOC_EXTS:
                mapping = ("analyze_pdf", "document")
        if not mapping:
            return

        task_subtype, model_type = mapping
        self._task_buffer.append(
            {
                "job_id": self._current_job_id,
                "model_type": model_type,
                "task_subtype": task_subtype,
                "source_id": source_id,
                "doc_id": doc_id,
                "input_path": media.path,
                "input_params": {},
            }
        )
        if len(self._task_buffer) >= 50:
            await self._flush_tasks()

    async def _flush_tasks(self) -> None:
        if not self._task_buffer:
            return
            
        tasks_to_send = self._task_buffer[:]
        self._task_buffer.clear()
        
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                await client.post(
                    get_backend_url("tasks/enqueue/bulk"),
                    json={"tasks": tasks_to_send},
                )
            logger.debug(f"Bulk enqueued {len(tasks_to_send)} tasks")
        except Exception as exc:
            logger.error(f"Failed to bulk enqueue tasks: {exc}")

    @property
    def source_name(self) -> str:
        return "telegram"

    async def connect(self):
        await self.client.connect()
        if not await self.client.is_user_authorized():
            # In a headless service, we can't really do interactive auth easily.
            # We rely on the session file being mounted and already valid.
            if self.phone:
                try:
                    # check if we can sign in? No, this requires code input.
                    # We just raise error if not authorized.
                    pass
                except Exception:
                    pass

            if not await self.client.is_user_authorized():
                raise Exception(
                    "Session not authorized. Please run auth locally and mount session file."
                )

    async def disconnect(self):
        await self.client.disconnect()

    async def process_chats(self, dialogs):
        """
        Iterates over dialogs and updates the Chat table.
        """
        logger.info(f"Processing {len(dialogs)} chats...")

        # Cache my_id
        me = await self.client.get_me()
        my_id = me.id

        total_messages_sent_by_me = 0
        chat_stats_map = {}

        for d in dialogs:
            chat_id = d.id
            stats = await get_chat_message_stats(chat_id, my_id)
            chat_stats_map[chat_id] = stats
            total_messages_sent_by_me += stats.me

            # Extract basic info
            title = d.name
            is_private = d.is_user

            # Construct Chat object
            chat = Chat(
                source_id=chat_id,
                title=title,
                is_private=is_private,
                message_count_total=stats.total,
                message_count_me=stats.me,
                importance_score=0.0,  # Will calculate after loop
            )

            # Save basic info
            await save_chat(chat.model_dump(exclude_none=True))

        # Update importance scores
        if total_messages_sent_by_me > 0:
            for chat_id, stats in chat_stats_map.items():
                importance = stats.me / total_messages_sent_by_me
                await save_chat({"source_id": chat_id, "importance_score": importance})

    async def analyze_chat(self, chat_id: int):
        """
        Analyzes a chat using the new segment-based hierarchical pipeline.
        NOTE: LLM client instantiation is handled by the manager and passed in,
        but for backward compatibility of this method signature, we instantiate
        a default client here if needed. Usually, the manager will call
        `etl.chat_analysis.service.analyze_chat` directly.
        """
        from etl.chat_analysis.service import analyze_chat as run_pipeline
        from etl.chat_analysis.llm_client import ChatAnalysisLlmClient
        logger.info(f"Analyzing chat {chat_id} using segment pipeline...")
        client = ChatAnalysisLlmClient()
        try:
            await run_pipeline(chat_id=chat_id, llm_client=client)
        except Exception as e:
            logger.error(f"Failed to analyze chat {chat_id}: {e}")

    async def process_contacts(self, dialogs):
        """
        Identify contacts from private chats and populate contacts table.
        """
        logger.info("Processing contacts...")
        me = await self.client.get_me()
        my_id = me.id
        my_name = " ".join(filter(None, [me.first_name, me.last_name])).strip() or "Me"
        await save_contact({"source_id": my_id, "name": my_name, "username": me.username})

        for d in dialogs:
            if d.is_user:
                user_id = d.id
                user = d.entity

                name = f"{user.first_name or ''} {user.last_name or ''}".strip()
                username = user.username
                phone = user.phone

                contact = Contact(
                    source_id=user_id, name=name, username=username, phone=phone
                )

                await save_contact(contact.model_dump(exclude_none=True))
                await save_chat_member(user_id, user_id)
                await save_chat_member(user_id, my_id)

    async def analyze_contact(self, user_id: int):
        """
        Analyzes a contact using LLM to generate description, interests, tags.
        """
        logger.info(f"Analyzing contact {user_id}...")

        contact_data = await get_contact(user_id)
        if not contact_data:
            logger.warning(f"Contact {user_id} not found in DB.")
            return

        name = contact_data.name or "Unknown"
        image_description = contact_data.image_description or "No image"

        try:
            my_messages = []
            async for msg in self.client.iter_messages(
                user_id, limit=50, from_user="me"
            ):
                if msg.text:
                    my_messages.append(f"[{msg.date}] Me: {msg.text}")
            my_messages.reverse()

            [my_messages] = _truncate_messages([my_messages])
            my_messages_text = "\n".join(my_messages)
            shared_chats_text = "Unknown (API limitation)"

            prompt = Prompts.get_contact_analysis_prompt(
                name, my_messages_text, shared_chats_text, image_description
            )
            response_text = await generate_text_with_retry(prompt)

            match = re.search(r"\{.*\}", response_text, re.DOTALL)
            if match:
                result = json.loads(match.group(0))
                contact_update = {
                    "source_id": user_id,
                    "description": result.get("description"),
                    "interests": json.dumps(result.get("interests", [])),
                    "tags": json.dumps(result.get("tags", [])),
                    "address": result.get("address"),
                    "last_analyzed_at": datetime.now().isoformat(),
                }
                await save_contact(contact_update)
                logger.info(f"Analyzed contact {name}")
        except Exception as e:
            logger.error(f"Failed to analyze contact {user_id}: {e}")

    async def get_dialogs(self, limit: int = 100) -> list[dict[str, Any]]:
        # Logic copied from original source
        if not self.client.is_connected():
            await self.connect()

        dialogs = []
        async for dialog in self.client.iter_dialogs(limit=limit):
            date_ts = dialog.date.timestamp() if dialog.date else 0
            is_archived = getattr(dialog, "archived", False) or (
                getattr(dialog, "folder_id", 0) == 1
            )

            if dialog.is_user:
                chat_type = "personal"
            elif dialog.is_group:
                chat_type = "group"
            elif dialog.is_channel:
                chat_type = "channel"
            else:
                chat_type = "unknown"

            dialogs.append(
                {
                    "id": int(dialog.id),
                    "name": dialog.name or "Deleted Account",
                    "date": date_ts,
                    "archived": is_archived,
                    "type": chat_type,
                }
            )
        return dialogs

    def _get_sender_name(self, sender) -> str:
        """Извлекает имя отправителя из объекта sender."""
        if not sender:
            return "Unknown"

        first = getattr(sender, "first_name", "")
        last = getattr(sender, "last_name", "")
        username = getattr(sender, "username", "")

        if first or last:
            return f"{first or ''} {last or ''}".strip()
        elif username:
            return username
        else:
            return "Unknown"

    async def _get_forward_info(self, message: Message) -> ForwardInfo:
        """Extract forward information from a message."""
        if not message.forward:
            return ForwardInfo(None, None)

        fwd = message.forward
        fwd_from_id = fwd.sender_id if fwd.sender_id else None
        fwd_from_name = None

        if fwd.sender_id:
            # Attempt to get name from object if available
            if hasattr(fwd, "original_fwd") and fwd.original_fwd.from_name:
                fwd_from_name = fwd.original_fwd.from_name
            else:
                try:
                    fwd_entity = await message.get_forward_from()
                    if fwd_entity:
                        fwd_first = getattr(fwd_entity, "first_name", "")
                        fwd_last = getattr(fwd_entity, "last_name", "")
                        fwd_from_name = (
                            fwd.from_name
                            or f"{fwd_first or ''} {fwd_last or ''}".strip()
                            or getattr(fwd_entity, "username", None)
                        )
                except Exception:
                    fwd_from_name = fwd.from_name or "Unknown Source"
        else:
            fwd_from_name = fwd.from_name or "Unknown Source"

        return ForwardInfo(fwd_from_id, fwd_from_name)

    async def _process_photo(
        self, message: Message, chat_id: int
    ) -> TelegramMediaMetadata:
        """Download photo. Analysis is deferred to the model scheduler."""
        logger.info(f"Processing PHOTO for msg {message.id} in chat {chat_id}")

        save_path = f"/app/storage/media/tg_{chat_id}_{message.id}.jpg"
        filename = os.path.basename(save_path)

        media = TelegramMediaMetadata(type="photo", extension="jpg")

        try:
            await self.client.download_media(message, file=save_path)
            media.path = save_path
            media.url = f"{Config.MEDIA_BASE_URL}/{filename}"
            logger.info(f"  Downloaded photo to: {save_path}")
        except Exception as e:
            logger.error(f"  Failed to download photo: {e}")

        return media

    async def _process_audio(
        self, message: Message, chat_id: int, doc: Document, is_voice: bool
    ) -> TelegramMediaMetadata:
        """Download audio/voice. Transcription is deferred to the model scheduler."""
        media_type = "voice" if is_voice else "audio"
        logger.info(
            f"Processing {media_type.upper()} for msg {message.id} in chat {chat_id}"
        )

        media = TelegramMediaMetadata(
            type=media_type, size=doc.size, mime=doc.mime_type
        )

        for attr in doc.attributes:
            if isinstance(attr, DocumentAttributeAudio):
                media.duration = float(attr.duration) if attr.duration else None
                media.title = attr.title
                media.performer = attr.performer

        ext = "ogg" if is_voice else "mp3"
        media.extension = ext
        save_path = f"/app/storage/media/tg_{chat_id}_{message.id}.{ext}"

        try:
            actual_path = await self.client.download_media(message, file=save_path)
            media.path = actual_path
            logger.info(f"  Downloaded {media_type} to: {actual_path}")
        except Exception as e:
            logger.error(f"  Failed to download {media_type}: {e}")

        return media

    async def _process_document(
        self, message: Message, chat_id: int, doc: Document
    ) -> TelegramMediaMetadata:
        """Download analysable documents (PDF, Office). Analysis is deferred to the model scheduler."""
        logger.info(f"Processing DOCUMENT for msg {message.id} in chat {chat_id}")

        original_name = self._get_doc_filename(doc)

        media = TelegramMediaMetadata(
            type="document",
            size=doc.size,
            mime=doc.mime_type,
            file_name=original_name,
        )

        ext_map = {
            "application/pdf": "pdf",
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document": "docx",
            "application/vnd.openxmlformats-officedocument.presentationml.presentation": "pptx",
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": "xlsx",
            "application/msword": "doc",
            "application/vnd.ms-powerpoint": "ppt",
            "application/vnd.ms-excel": "xls",
        }
        ext = ext_map.get(doc.mime_type, "bin")
        save_path = f"/app/storage/media/tg_{chat_id}_{message.id}.{ext}"
        media.extension = ext

        try:
            actual_path = await self.client.download_media(message, file=save_path)
            media.path = actual_path
            logger.info(f"  Downloaded document to: {actual_path}")
        except Exception as e:
            logger.error(f"  Failed to download document: {e}")

        return media

    # ------------------------------------------------------------------
    # Helpers shared across media handlers
    # ------------------------------------------------------------------

    @staticmethod
    def _get_doc_filename(doc: Document) -> str | None:
        """Extract original filename from Telegram document attributes."""
        for attr in doc.attributes:
            if isinstance(attr, DocumentAttributeFilename):
                return attr.file_name
        return None

    @staticmethod
    def _ext_from_mime(mime: str | None) -> str:
        """Derive a file extension from a MIME type, falling back to 'bin'."""
        if not mime or "/" not in mime:
            return "bin"
        subtype = mime.split("/")[-1].split(";")[0].strip()
        return "bin" if subtype == "octet-stream" else subtype

    def _media_save_path(self, chat_id: int, msg_id: int, ext: str) -> tuple[str, str]:
        """Return (save_path, public_url) for a media file."""
        save_path = f"/app/storage/media/tg_{chat_id}_{msg_id}.{ext}"
        url = f"{Config.MEDIA_BASE_URL}/{os.path.basename(save_path)}"
        return save_path, url

    async def _download_media(
        self, message: Message, media: TelegramMediaMetadata, save_path: str, url: str
    ) -> None:
        """Download and populate path/url on the metadata object. Raises on failure."""
        actual_path = await self.client.download_media(message, file=save_path)
        media.path = actual_path or save_path
        media.url = url

    # ------------------------------------------------------------------
    # Per-type document processors
    # ------------------------------------------------------------------

    async def _process_image_document(
        self, message: Message, chat_id: int, doc: Document
    ) -> TelegramMediaMetadata:
        """Download image files sent as MessageMediaDocument (e.g. webp, gif). Analysis deferred."""
        ext = self._ext_from_mime(doc.mime_type)
        save_path, url = self._media_save_path(chat_id, message.id, ext)

        media = TelegramMediaMetadata(
            type="photo",
            extension=ext,
            size=doc.size,
            mime=doc.mime_type,
        )

        try:
            await self._download_media(message, media, save_path, url)
            logger.info(f"  Downloaded image-document to: {media.path}")
        except Exception as e:
            logger.error(
                f"  Failed to download image-document for msg {message.id}: {e}"
            )

        return media

    async def _process_generic_document(
        self, message: Message, chat_id: int, doc: Document
    ) -> TelegramMediaMetadata:
        """Download and store any unrecognized document type."""
        original_name = self._get_doc_filename(doc)

        ext = None
        if original_name and "." in original_name:
            ext = original_name.rsplit(".", 1)[-1].lower()
        if not ext:
            ext = self._ext_from_mime(doc.mime_type)

        save_path, url = self._media_save_path(chat_id, message.id, ext)

        media = TelegramMediaMetadata(
            type="document",
            extension=ext,
            size=doc.size,
            mime=doc.mime_type,
            file_name=original_name,
        )

        try:
            await self._download_media(message, media, save_path, url)
            logger.info(f"  Downloaded generic document to: {media.path}")
        except Exception as e:
            logger.error(
                f"  Failed to download generic document for msg {message.id}: {e}"
            )

        return media

    # ------------------------------------------------------------------
    # Document classification
    # ------------------------------------------------------------------

    _ANALYZABLE_DOC_MIMES = frozenset(
        {
            "application/pdf",
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            "application/vnd.openxmlformats-officedocument.presentationml.presentation",
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            "application/msword",
            "application/vnd.ms-powerpoint",
            "application/vnd.ms-excel",
        }
    )

    async def _process_document_media(
        self, message: Message, chat_id: int, doc: Document
    ) -> TelegramMediaMetadata | None:
        """Classify and process a MessageMediaDocument into the right handler."""
        # Video
        for attr in doc.attributes:
            if isinstance(attr, DocumentAttributeVideo):
                return TelegramMediaMetadata(
                    type="video",
                    size=doc.size,
                    mime=doc.mime_type,
                    duration=float(attr.duration) if attr.duration else None,
                    width=attr.w,
                    height=attr.h,
                )

        # Audio / voice
        is_voice = any(
            isinstance(a, DocumentAttributeAudio) and getattr(a, "voice", False)
            for a in doc.attributes
        )
        is_audio = any(isinstance(a, DocumentAttributeAudio) for a in doc.attributes)
        if is_voice or is_audio:
            return await self._process_audio(message, chat_id, doc, is_voice)

        # Known analysable document (PDF, Office)
        if doc.mime_type in self._ANALYZABLE_DOC_MIMES:
            return await self._process_document(message, chat_id, doc)

        # Image wrapped as document (webp, gif, etc.)
        if doc.mime_type and doc.mime_type.startswith("image/"):
            return await self._process_image_document(message, chat_id, doc)

        # Everything else -- still download so the file is available
        return await self._process_generic_document(message, chat_id, doc)

    # ------------------------------------------------------------------
    # Main media dispatcher
    # ------------------------------------------------------------------

    @staticmethod
    def _build_content_prefix(media: TelegramMediaMetadata | None) -> str:
        if not media:
            return ""
        type_label = (media.type or "MEDIA").upper()
        desc = media.description or ""
        if type_label in ("AUDIO", "VOICE") and desc:
            return f"[{type_label} TRANSCRIPT] {desc}\n"
        return f"[{type_label}] {desc}\n" if desc else f"[{type_label}]\n"

    async def _process_media(
        self, message: Message, chat_id: int
    ) -> ProcessMediaResult:
        """Coordinate processing of all media types."""
        if not message.media:
            return ProcessMediaResult(None, "")

        logger.info(f"MEDIA PROCESSING msg {message.id} in chat {chat_id}")

        media_info: TelegramMediaMetadata | None = None

        if isinstance(message.media, MessageMediaPhoto):
            media_info = await self._process_photo(message, chat_id)
        elif isinstance(message.media, MessageMediaDocument):
            media_info = await self._process_document_media(
                message, chat_id, message.media.document
            )
        else:
            media_type = type(message.media).__name__
            logger.warning(f"  Unsupported media type: {media_type}")

        content_prefix = self._build_content_prefix(media_info)

        desc_len = (
            len(media_info.description) if media_info and media_info.description else 0
        )
        logger.info(
            f"  MEDIA RESULT: type={media_info.type if media_info else 'unknown'} "
            f"size={media_info.size if media_info else 'N/A'} "
            f"path={media_info.path if media_info else 'N/A'} "
            f"desc_len={desc_len}"
        )

        return ProcessMediaResult(media_info, content_prefix)

    def _format_content(
        self,
        message: Message,
        sender_name: str,
        chat_title: str,
        is_from_me: bool,
        fwd_from_name: str | None,
        content_prefix: str,
    ) -> str:
        """Формирует итоговую строку content."""
        prefix = "Me" if is_from_me else sender_name
        fwd_str = f" (Forwarded from {fwd_from_name})" if fwd_from_name else ""
        msg_text = message.message or ""

        return f"[{message.date.isoformat()}] {prefix} (in {chat_title}){fwd_str}: {content_prefix}{msg_text}"

    async def _msg_to_doc(
        self, message: Message, chat_id: int, chat_title: str
    ) -> GenericDocument:
        """Convert a Telegram message into a GenericDocument."""
        sender = await message.get_sender()
        sender_name = self._get_sender_name(sender)
        is_from_me = getattr(message, "out", False)

        fwd_from_id, fwd_from_name = await self._get_forward_info(message)

        media_info, content_prefix = await self._process_media(message, chat_id)

        # Enqueue deferred analysis tasks for downloaded media
        if media_info and media_info.path and self._current_job_id:
            await self._enqueue_media_task(
                media_info, f"telegram_{chat_id}", str(message.id)
            )

        content = self._format_content(
            message, sender_name, chat_title, is_from_me, fwd_from_name, content_prefix
        )

        tg_meta = TelegramMetadata(
            sender_id=sender.id if sender else None,
            sender_name=sender_name,
            chat_id=chat_id,
            chat_title=chat_title,
            is_from_me=is_from_me,
            forward_from_id=fwd_from_id,
            forward_from_name=fwd_from_name,
            reply_to_msg_id=message.reply_to.reply_to_msg_id
            if message.reply_to
            else None,
            media=media_info,
        )

        return GenericDocument(
            source_id=f"telegram_{chat_id}",
            doc_id=str(message.id),
            content=content,
            timestamp=message.date,
            metadata=tg_meta.model_dump(),
        )

    async def fetch(
        self, params: dict[str, Any], progress_callback: Callable[[str, float], None]
    ) -> AsyncGenerator[GenericDocument, None]:
        """
        params: {
            "chat_ids": list[int],
            "days_back": int,
            "sync_metadata": bool (default True)
        }
        """
        chat_ids = params.get("chat_ids", [])
        days_back = params.get("days_back", 90)
        do_sync_metadata = params.get("sync_metadata", True)

        if not chat_ids:
            return

        end_date = datetime.now(timezone.utc)
        start_date = end_date - timedelta(days=days_back)

        # Sync Metadata (Chats & Contacts)
        if do_sync_metadata:
            try:
                logger.info("Syncing metadata (chats & contacts)...")
                dialogs_objs = []
                async for d in self.client.iter_dialogs(limit=None):
                    dialogs_objs.append(d)

                await self.process_chats(dialogs_objs)
                await self.process_contacts(dialogs_objs)
            except Exception as e:
                logger.error(f"Failed to sync metadata: {e}")

        total_chats = len(chat_ids)

        for idx, chat_id in enumerate(chat_ids):
            # Report Progress
            progress = idx / total_chats
            progress_callback(f"Processing chat {chat_id}...", progress)

            # Analyze Chat (metadata)
            try:
                await self.analyze_chat(chat_id)
            except Exception as e:
                logger.error(f"Failed to trigger analysis for chat {chat_id}: {e}")

            # 1. Calculate Ranges (Logic copied from original)
            ranges_to_fetch = [(start_date, end_date)]

            # Using database from etl/database.py which shares same logic/file
            existing_ranges = await get_downloaded_ranges(chat_id)
            parsed_ranges = []
            for r in existing_ranges:
                s_str, e_str = r.start_date, r.end_date
                try:
                    s = datetime.fromisoformat(s_str)
                    e = datetime.fromisoformat(e_str)
                    if s.tzinfo is None:
                        s = s.replace(tzinfo=timezone.utc)
                    if e.tzinfo is None:
                        e = e.replace(tzinfo=timezone.utc)
                    parsed_ranges.append((s, e))
                except Exception:
                    pass

            for ex_s, ex_e in parsed_ranges:
                new_needed = []
                for req_s, req_e in ranges_to_fetch:
                    if req_e <= ex_s or req_s >= ex_e:
                        new_needed.append((req_s, req_e))
                    elif req_s < ex_s and req_e > ex_e:
                        new_needed.append((req_s, ex_s))
                        new_needed.append((ex_e, req_e))
                    elif req_s < ex_s and req_e <= ex_e:
                        new_needed.append((req_s, ex_s))
                    elif req_s >= ex_s and req_e > ex_e:
                        new_needed.append((ex_e, req_e))
                ranges_to_fetch = new_needed

            if not ranges_to_fetch:
                logger.info(f"Chat {chat_id} up to date.")
                continue

            # Get Chat Title
            try:
                entity = await self.client.get_entity(chat_id)
                chat_title = getattr(entity, "title", None)
                if not chat_title:
                    first = getattr(entity, "first_name", "")
                    last = getattr(entity, "last_name", "")
                    chat_title = f"{first or ''} {last or ''}".strip() or getattr(
                        entity, "username", "Unknown"
                    )
            except Exception:
                chat_title = f"Chat {chat_id}"

            # Fetch Messages
            for r_start, r_end in ranges_to_fetch:
                count = 0
                async for message in self.client.iter_messages(
                    chat_id, offset_date=r_start, reverse=True
                ):
                    if message.date < r_start:
                        continue
                    if message.date > r_end:
                        break

                    if message.id and (message.message or message.media):
                        count += 1
                        yield await self._msg_to_doc(message, chat_id, chat_title)

                await add_downloaded_range(chat_id, r_start, r_end)
                logger.info(f"Fetched {count} msgs from {chat_id}")

        await self._flush_tasks()
        progress_callback("Completed", 1.0)
