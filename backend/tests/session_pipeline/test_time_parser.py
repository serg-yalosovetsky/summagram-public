import pytest
from backend.session_pipeline.implementations.time_parser_dateparser import (
    DateparserTimeParser,
)
from backend.session_pipeline.models.stage0_normalize import NormalizedText
from backend.session_pipeline.models.common import LanguageCode


@pytest.fixture
def parser():
    return DateparserTimeParser()


@pytest.mark.asyncio
async def test_parse_days_ru(parser):
    text = NormalizedText(
        raw_text="покажи за последние 2 дня",
        normalized_text="покажи за последние 2 дня",
        lowered_text="покажи за последние 2 дня",
        tokens=[],
        detected_language=LanguageCode.RU,
        usernames=[],
        urls=[],
        numbers=["2"],
    )
    result = await parser.parse(text)
    assert len(result.expressions) > 0
    # The primary range should be ~2 days
    assert result.primary_range is not None
    assert result.primary_range.amount == 2
    assert result.primary_range.unit == "days"


@pytest.mark.asyncio
async def test_parse_weeks_ru(parser):
    text = NormalizedText(
        raw_text="3 недели назад",
        normalized_text="3 недели назад",
        lowered_text="3 недели назад",
        tokens=[],
        detected_language=LanguageCode.RU,
        usernames=[],
        urls=[],
        numbers=["3"],
    )
    result = await parser.parse(text)
    assert len(result.expressions) > 0
    assert result.primary_range is not None
    assert result.primary_range.amount == 3
    # Our internal normalization will set the unit for 'тижні' (weeks)
    assert result.primary_range.unit == "weeks"


@pytest.mark.asyncio
async def test_no_time(parser):
    text = NormalizedText(
        raw_text="привет",
        normalized_text="привет",
        lowered_text="привет",
        tokens=[],
        detected_language=LanguageCode.RU,
        usernames=[],
        urls=[],
        numbers=[],
    )
    result = await parser.parse(text)
    assert len(result.expressions) == 0
    assert result.primary_range is None
