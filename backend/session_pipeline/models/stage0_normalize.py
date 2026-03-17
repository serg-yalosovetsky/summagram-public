"""Stage 0: text normalisation output model."""

from __future__ import annotations

from pydantic import Field

from .common import BaseStageModel, LanguageCode


class NormalizedText(BaseStageModel):
    """Output of text normalisation: cleaned text, detected tokens/artefacts."""

    raw_text: str
    normalized_text: str
    lowered_text: str
    detected_language: LanguageCode = LanguageCode.UNKNOWN
    tokens: list[str] = Field(default_factory=list)
    usernames: list[str] = Field(default_factory=list)
    urls: list[str] = Field(default_factory=list)
    numbers: list[str] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)
