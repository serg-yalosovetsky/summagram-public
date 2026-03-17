"""Stage 3: time expression parsing output model."""

from __future__ import annotations

from datetime import datetime

from pydantic import Field

from .common import BaseStageModel


class ParsedTimeExpression(BaseStageModel):
    """A single parsed time expression from user text."""

    raw_text: str
    amount: int | None = None
    unit: str | None = None  # minutes | hours | days | weeks | months
    date_from: datetime | None = None
    date_to: datetime | None = None
    timezone: str | None = None
    relative: bool = False
    parser_name: str = "dateparser"


class TimeParseResult(BaseStageModel):
    """All time expressions found in this user turn."""

    expressions: list[ParsedTimeExpression] = Field(default_factory=list)
    primary_range: ParsedTimeExpression | None = None
