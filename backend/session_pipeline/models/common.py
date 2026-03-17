"""
Common enums and base classes for the session NLP pipeline.
All models use Pydantic v2 with strict extra="forbid" to catch schema drift early.
"""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field


class LanguageCode(StrEnum):
    RU = "ru"
    UK = "uk"
    EN = "en"
    MIXED = "mixed"
    UNKNOWN = "unknown"


class EntityKind(StrEnum):
    PERSON = "person"
    PLACE = "place"
    ORG = "org"
    CHAT = "chat"
    USERNAME = "username"
    URL = "url"


class QueryType(StrEnum):
    PERSON_CHAT = "person_chat"
    SEARCH_FROM_PERSON = "search_from_person"
    LAST_ANY = "last_any"
    SEARCH_TEXT = "search_text"
    SEARCH_MEDIA = "search_media"
    SUMMARIZE_UNREAD = "summarize_unread"


class BaseStageModel(BaseModel):
    """Base for all pipeline stage models. Forbids extra fields to catch schema drift."""

    model_config = ConfigDict(extra="forbid", populate_by_name=True)


class ConfidenceMixin(BaseModel):
    """Mixin for models that carry an extraction confidence score [0.0, 1.0]."""

    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
