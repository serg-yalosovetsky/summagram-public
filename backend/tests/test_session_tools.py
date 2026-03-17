import pytest

from backend.session_tools import (
    QueryKind,
    QueryNormalizer,
    RetrievalPolicyBuilder,
)


@pytest.fixture()
def normalizer() -> QueryNormalizer:
    return QueryNormalizer()


def test_assignment_query_detected(normalizer: QueryNormalizer) -> None:
    q = normalizer.normalize("Что задала?")
    assert q.kind == QueryKind.ASSIGNMENT
    assert "задание" in q.expansion_terms
    assert "домашка" in q.retrieval_query


def test_link_query_detected(normalizer: QueryNormalizer) -> None:
    q = normalizer.normalize("Она кинула ссылку?")
    assert q.kind == QueryKind.LINK
    assert "https" in q.expansion_terms
    assert "ссылка" in q.retrieval_query


def test_file_query_detected(normalizer: QueryNormalizer) -> None:
    q = normalizer.normalize("Какой файл она прислала?")
    assert q.kind == QueryKind.FILE
    assert "pdf" in q.expansion_terms
    assert "документ" in q.retrieval_query


def test_meeting_query_detected(normalizer: QueryNormalizer) -> None:
    q = normalizer.normalize("О чем говорили?")
    assert q.kind == QueryKind.MEETING
    assert "встреча" in q.expansion_terms
    assert "созвон" in q.retrieval_query


def test_generic_query_stays_generic(normalizer: QueryNormalizer) -> None:
    q = normalizer.normalize("Что она думает про отпуск?")
    assert q.kind == QueryKind.GENERIC
    assert q.expansion_terms == []
    assert q.retrieval_query == "что она думает про отпуск?"


def test_policy_for_assignment_is_hybrid(normalizer: QueryNormalizer) -> None:
    builder = RetrievalPolicyBuilder()
    q = normalizer.normalize("Что задала?")
    policy = builder.build(q, requested_limit=20)

    assert policy.mode == "hybrid"
    assert policy.limit >= 120
    assert policy.context_window == 1


def test_policy_for_short_generic_is_hybrid(normalizer: QueryNormalizer) -> None:
    builder = RetrievalPolicyBuilder()
    q = normalizer.normalize("отпуск летом")
    policy = builder.build(q, requested_limit=10)

    assert policy.mode == "hybrid"
    assert policy.limit >= 80


def test_policy_for_long_generic_is_vector(normalizer: QueryNormalizer) -> None:
    builder = RetrievalPolicyBuilder()
    q = normalizer.normalize("что она говорила про поездку в карпаты на майские в прошлом году")
    policy = builder.build(q, requested_limit=30)

    assert policy.mode == "vector"
    assert policy.limit == 30
