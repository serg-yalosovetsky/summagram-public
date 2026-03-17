import pytest
from backend.session_pipeline.implementations.entity_resolver_default import (
    DefaultEntityResolver,
)
from backend.session_pipeline.models.stage1_candidates import (
    CandidateMention,
    CandidateExtractionResult,
)
from backend.session_pipeline.models.common import EntityKind
from backend.session_pipeline.models.stage0_normalize import NormalizedText
from backend.session_pipeline.models.common import LanguageCode


@pytest.fixture
def resolver():
    # Provide a threshold but don't mock DB lookup to see if it gracefully returns no match or we can mock
    return DefaultEntityResolver()


@pytest.mark.asyncio
async def test_normalize_person_case_ru(resolver):
    # Test case nominative extraction
    candidate = CandidateMention(
        raw_text="ивана", kind=EntityKind.PERSON, source="test", confidence=0.9
    )
    candidates = CandidateExtractionResult(candidates=[candidate])
    text = NormalizedText(
        raw_text="от ивана",
        normalized_text="от ивана",
        lowered_text="от ивана",
        tokens=["от", "ивана"],
        detected_language=LanguageCode.RU,
    )
    res = await resolver.resolve(text, candidates)

    assert len(res.entities) == 1
    assert res.entities[0].lemma.lower() == "иван"


@pytest.mark.asyncio
async def test_normalize_person_case_uk(resolver):
    candidate = CandidateMention(
        raw_text="олега", kind=EntityKind.PERSON, source="test", confidence=0.9
    )
    candidates = CandidateExtractionResult(candidates=[candidate])
    text = NormalizedText(
        raw_text="від олега",
        normalized_text="від олега",
        lowered_text="від олега",
        tokens=["від", "олега"],
        detected_language=LanguageCode.UK,
    )
    res = await resolver.resolve(text, candidates)

    assert len(res.entities) == 1
    assert res.entities[0].lemma.lower() == "олег"


@pytest.mark.asyncio
async def test_generate_variants():
    from backend.session_pipeline.implementations.entity_resolver_default import (
        _translit_variants,
    )

    translit = _translit_variants("Олег")
    assert "Olyeh" in translit
