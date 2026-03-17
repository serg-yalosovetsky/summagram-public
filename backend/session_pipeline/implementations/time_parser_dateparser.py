"""
Stage 3: Time expression parsing using dateparser.
Handles RU/UK/EN relative and absolute dates without involving LLM.

Examples handled:
  "за 2 дні"  → date_from=now-2days
  "вчора"     → date_from=yesterday
  "last 6 hours" → date_from=now-6h
  "за минулий тиждень" → date_from=now-7days

Local import dateparser is intentional: heavy transitive dep, loaded only when needed.
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone

from loguru import logger

from backend.session_pipeline.models.stage0_normalize import NormalizedText
from backend.session_pipeline.models.stage3_time import (
    ParsedTimeExpression,
    TimeParseResult,
)

_DATEPARSER_LANGUAGES = ["ru", "uk", "en"]

# Mapping of common RU/UK time unit words to our canonical unit strings.
# Keys must be unique — RU and UK entries are merged without repetition.
_UNIT_MAP: dict[str, str] = {
    # Russian
    "минут": "minutes",
    "минуту": "minutes",
    "минуты": "minutes",
    "час": "hours",
    "часа": "hours",
    "часов": "hours",
    "часы": "hours",
    "день": "days",
    "дня": "days",
    "дней": "days",
    "неделю": "weeks",
    "недели": "weeks",
    "неделей": "weeks",
    "месяц": "months",
    "месяца": "months",
    "месяцев": "months",
    # Ukrainian (unique keys only)
    "хвилин": "minutes",
    "хвилину": "minutes",
    "годину": "hours",
    "годин": "hours",
    "години": "hours",
    "днів": "days",
    "дні": "days",
    "тиждень": "weeks",
    "тижні": "weeks",
    "тижнів": "weeks",
    "місяць": "months",
    "місяці": "months",
}


def _parse_sync(text: str) -> list[ParsedTimeExpression]:
    """Run dateparser.search.search_dates synchronously."""
    import dateparser.search  # noqa: PLC0415
    import re  # noqa: PLC0415

    expressions: list[ParsedTimeExpression] = []
    now = datetime.now(tz=timezone.utc)

    try:
        results = dateparser.search.search_dates(
            text,
            languages=_DATEPARSER_LANGUAGES,
            settings={
                "PREFER_DAY_OF_MONTH": "first",
                "PREFER_DATES_FROM": "past",
                "RETURN_AS_TIMEZONE_AWARE": False,
                "TIMEZONE": "UTC",
            },
        )
    except Exception as exc:
        logger.warning(f"dateparser.search_dates failed: {exc}")
        return []

    if not results:
        return []

    for raw_text, parsed_dt in results:
        if parsed_dt is None:
            continue

        # Determine if relative
        relative = any(
            kw in text.lower()
            for kw in [
                "вчора",
                "вчера",
                "yesterday",
                "last",
                "за",
                "минулий",
                "прошлую",
                "прошлой",
            ]
        )

        # Try to extract amount+unit from matched text
        amount: int | None = None
        unit: str | None = None
        num_match = re.search(r"(\d+)", raw_text)
        if num_match:
            amount = int(num_match.group(1))
            for kw, u in _UNIT_MAP.items():
                if kw in raw_text.lower():
                    unit = u
                    break

        expressions.append(
            ParsedTimeExpression(
                raw_text=raw_text,
                amount=amount,
                unit=unit,
                date_from=parsed_dt,
                date_to=now,
                relative=relative,
                parser_name="dateparser",
            )
        )

    return expressions


class DateparserTimeParser:
    """
    Time expression parser using dateparser.
    Runs in a thread pool to avoid blocking the async event loop.
    """

    async def parse(self, text: NormalizedText) -> TimeParseResult:
        try:
            expressions = await asyncio.to_thread(_parse_sync, text.raw_text)
        except Exception as exc:
            logger.warning(f"Time parsing failed: {exc}")
            return TimeParseResult(expressions=[], primary_range=None)

        primary = expressions[0] if expressions else None
        return TimeParseResult(expressions=expressions, primary_range=primary)
