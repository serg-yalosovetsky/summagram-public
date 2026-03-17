import pytest
from backend.session_pipeline.models.stage0_normalize import NormalizedText
from backend.session_pipeline.models.common import LanguageCode
from backend.session_pipeline.implementations.candidate_extractor_rules import (
    RulesCandidateExtractor,
)


@pytest.fixture
def extractor():
    return RulesCandidateExtractor()


@pytest.mark.asyncio
async def test_username_extraction(extractor):
    norm = NormalizedText(
        raw_text="find @john_doe",
        normalized_text="find @john_doe",
        lowered_text="find @john_doe",
        tokens=["find", "@john_doe"],
        detected_language=LanguageCode.EN,
        usernames=["john_doe"],
        urls=[],
        numbers=[],
    )
    res = await extractor.extract(norm)
    assert len(res.candidates) == 1
    assert res.candidates[0].raw_text == "john_doe"


@pytest.mark.asyncio
async def test_thematic_extraction(extractor):
    norm = NormalizedText(
        raw_text="що задала Аліса",
        normalized_text="що задала Аліса",
        lowered_text="що задала аліса",
        tokens=["що", "задала", "аліса"],
        detected_language=LanguageCode.UK,
        usernames=[],
        urls=[],
        numbers=[],
    )
    res = await extractor.extract(norm)
    # Thematic rule should catch "Аліса"
    assert len(res.candidates) > 0
    assert any(c.raw_text == "Аліса" for c in res.candidates)


@pytest.mark.asyncio
async def test_preposition_extraction(extractor):
    norm = NormalizedText(
        raw_text="от Ивана",
        normalized_text="от Ивана",
        lowered_text="от ивана",
        tokens=["от", "ивана"],
        detected_language=LanguageCode.RU,
        usernames=[],
        urls=[],
        numbers=[],
    )
    res = await extractor.extract(norm)
    # Preposition rule should catch "Ивана"
    assert any(c.raw_text == "Ивана" for c in res.candidates)
