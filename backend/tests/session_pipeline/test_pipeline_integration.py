import pytest
from unittest.mock import AsyncMock
from backend.session_pipeline.services.factory import get_pipeline
from backend.session_pipeline.models.common import LanguageCode, QueryType
from backend.session_pipeline.models.stage4_intent import QueryIntent
from backend.session_pipeline.models.pipeline import SessionPipelineRequest

@pytest.mark.asyncio
async def test_full_pipeline_ru():
    pipeline = get_pipeline()
    
    # Mock the intent classifier to return a static deterministic result
    mock_classifier = AsyncMock()
    mock_classifier.classify.return_value = QueryIntent(
        query_type=QueryType.SEARCH_TEXT,
        search_query="отчеты",
        wants_only_from_person=True,
    )
    pipeline._intent_classifier = mock_classifier
    pipeline._return_trace = True

    # Message text
    text = "Найди все отчеты от @john_doe за последние 2 дня"
    request = SessionPipelineRequest(session_id="test_ru", user_text=text)

    result = await pipeline.run(request)

    # Normalization
    assert result.trace is not None
    assert result.trace.normalized.detected_language in (LanguageCode.RU, LanguageCode.MIXED)
    # We extracted @john_doe, which normalizer finds as 'john_doe' username
    assert "john_doe" in result.trace.normalized.usernames

    # Candidates (Rules + Natasha)
    # The normalizer replaces the username, but raw_text doesn't.
    # However we can be sure it found john_doe in URLs/usernames at least.
    
    # Intent
    assert result.intent.query_type == QueryType.SEARCH_TEXT
    assert result.intent.search_query == "отчеты"

@pytest.mark.asyncio
async def test_full_pipeline_uk():
    pipeline = get_pipeline()
    
    mock_classifier = AsyncMock()
    mock_classifier.classify.return_value = QueryIntent(
        query_type=QueryType.SEARCH_TEXT,
        search_query="звіт",
    )
    pipeline._intent_classifier = mock_classifier
    pipeline._return_trace = True

    text = "що Аліса задала вчора"
    request = SessionPipelineRequest(session_id="test_uk", user_text=text)
    result = await pipeline.run(request)

    # Since it's trace return enabled for tests we can check normalized
    # but the pipeline Result doesn't expose normalized directly in top-level, it's under trace.
    # Alternatively we can check intent
    assert result.intent.query_type == QueryType.SEARCH_TEXT
    assert result.intent.search_query == "звіт"
