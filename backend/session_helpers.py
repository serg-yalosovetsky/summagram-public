"""
Shared helpers for session message formatting and metadata.
Used by service.send_session_message and session_tools so tool logic stays DRY.
"""

import json
from typing import Any, Union

from pydantic import BaseModel, ConfigDict, ValidationError


class ChatHistoryMediaInfo(BaseModel):
    """Validated media metadata for chat history items."""

    model_config = ConfigDict(extra="ignore")

    type: str = "media"
    path: str | None = None
    description: str | None = None


class ChatHistoryItemMetadata(BaseModel):
    """Validated metadata for a chat history item."""

    model_config = ConfigDict(extra="ignore")

    is_from_me: bool = False
    sender_name: str | None = None
    chat_id: int | str | None = None
    media: ChatHistoryMediaInfo | None = None


def _parse_raw_metadata(meta: Any) -> dict:
    """Normalize metadata: if string, try json.loads; otherwise return meta or {}."""
    if meta is None:
        return {}
    if isinstance(meta, str):
        try:
            return json.loads(meta) if meta else {}
        except Exception:
            return {}
    if isinstance(meta, dict):
        return meta
    return {}


def parse_message_metadata(meta: Any) -> dict:
    """Normalize metadata: if string, try json.loads; otherwise return meta or {}."""
    return _parse_raw_metadata(meta)


def validate_message_metadata(meta: Any) -> ChatHistoryItemMetadata:
    """Parse raw metadata and validate into ChatHistoryItemMetadata. Returns defaults on failure."""
    raw = _parse_raw_metadata(meta)
    try:
        return ChatHistoryItemMetadata.model_validate(raw)
    except ValidationError:
        return ChatHistoryItemMetadata()


def get_media_filename(metadata: Union[dict, ChatHistoryItemMetadata]) -> str | None:
    """
    Derive public media URL path from metadata.media.path.
    Path is stored as /app/storage/media/tg_{chat_id}_{msg_id}.ext
    Returns /media/{filename} or None if no media.
    """
    if isinstance(metadata, ChatHistoryItemMetadata):
        media = metadata.media
        if not media or not media.path:
            return None
        path = media.path
    else:
        media = metadata.get("media") if isinstance(metadata, dict) else None
        if not media or not isinstance(media, dict):
            return None
        path = media.get("path")
        if not path or not isinstance(path, str):
            return None
    filename = path.split("/")[-1]
    return f"/media/{filename}" if filename else None


def _get_item_field(item: Union[dict, BaseModel], key: str, default: Any = None) -> Any:
    """Get field from dict or Pydantic model (supports both dict and RawDocumentRow)."""
    return (
        item.get(key, default)
        if isinstance(item, dict)
        else getattr(item, key, default)
    )


def format_chat_history(history: list, include_media: bool = True) -> str:
    """
    Format a list of chat history items (content + optional metadata) into
    lines like "[Me]: ..." or "[sender_name]: ...". Uses Pydantic validation.
    Accepts both dict and Pydantic models (e.g. RawDocumentRow).
    When include_media is True and a message has media, appends:
    " | Media type: X | Download: /media/filename | Description: ..."
    """
    lines = []
    for h in history:
        meta = validate_message_metadata(_get_item_field(h, "metadata"))
        prefix = "[Me]" if meta.is_from_me else f"[{meta.sender_name or 'Unknown'}]"
        content = (_get_item_field(h, "content") or "").strip()
        line = f"{prefix}: {content}"
        if include_media:
            media_url = get_media_filename(meta)
            if media_url:
                media_type = meta.media.type if meta.media else "media"
                desc = (meta.media.description or "") if meta.media else ""
                line += f" | Media type: {media_type} | Download: {media_url}"
                if desc:
                    line += f" | Description: {desc[:200]}{'...' if len(desc) > 200 else ''}"
        lines.append(line)
    return "\n".join(lines)
