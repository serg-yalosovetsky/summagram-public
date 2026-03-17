import pytest
from backend.session_pipeline.implementations.normalizer_default import (
    DefaultTextNormalizer,
)
from backend.session_pipeline.models.common import LanguageCode


@pytest.fixture
def normalizer():
    return DefaultTextNormalizer()


@pytest.mark.asyncio
async def test_basic_cleaning(normalizer):
    text = "  Hello \t\n world!  "
    result = await normalizer.normalize(text)
    assert result.normalized_text == "Hello \n world!"
    assert result.tokens == ["hello", "world!"]


@pytest.mark.asyncio
async def test_url_extraction(normalizer):
    text = "Look at https://example.com and http://test.org/path?q=1"
    result = await normalizer.normalize(text)
    assert result.normalized_text == "Look at   and"
    assert len(result.urls) == 2
    assert result.urls[0] == "https://example.com"
    assert result.urls[1] == "http://test.org/path?q=1"


@pytest.mark.asyncio
async def test_username_extraction(normalizer):
    text = "Message from @john_doe and @alice"
    result = await normalizer.normalize(text)
    assert result.normalized_text == "Message from @john_doe and @alice"
    assert len(result.usernames) == 2
    assert result.usernames[0] == "john_doe"
    assert result.usernames[1] == "alice"


@pytest.mark.asyncio
async def test_language_detection(normalizer):
    res_ru = await normalizer.normalize("привет мир")
    assert res_ru.detected_language == LanguageCode.RU
    res_uk = await normalizer.normalize("привіт світ")
    assert res_uk.detected_language == LanguageCode.UK
    res_en = await normalizer.normalize("hello world")
    assert res_en.detected_language == LanguageCode.EN
    res_unknown = await normalizer.normalize("12345")
    assert res_unknown.detected_language == LanguageCode.UNKNOWN
