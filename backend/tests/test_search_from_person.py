import pytest
from unittest.mock import patch, MagicMock

from backend.session_tools import (
    _handle_search_from_person,
    SessionToolContext,
    SearchFromPersonArgs,
    ChatResolutionError,
    run_tool
)
from backend.retrieval import _reciprocal_rank_fusion
from etl.models import RawDocumentRow
from etl.db.chats import ChatSearchResult


@pytest.fixture
def mock_context():
    return SessionToolContext(session_id="test_session", context_chat_id=123)


@pytest.fixture
def sample_raw_docs():
    def _make_doc(doc_id, content, timestamp, is_from_me=False):
        return RawDocumentRow(
            source_id="telegram_123",
            doc_id=doc_id,
            content=content,
            timestamp=timestamp,
            metadata={"chat_id": 123, "is_from_me": is_from_me, "sender_name": "Alice"},
        )

    return _make_doc


def test_reciprocal_rank_fusion(sample_raw_docs):
    doc1 = sample_raw_docs("doc1", "a", "2023-01-01T10:00:00")
    doc2 = sample_raw_docs("doc2", "b", "2023-01-01T10:01:00")
    doc3 = sample_raw_docs("doc3", "c", "2023-01-01T10:02:00")

    list1 = [doc1, doc2]
    list2 = [doc2, doc3]

    merged = _reciprocal_rank_fusion(list1, list2, k=60, top_n=3)

    assert len(merged) == 3
    assert merged[0].doc_id == "doc2"
    assert set([m.doc_id for m in merged]) == {"doc1", "doc2", "doc3"}


@pytest.mark.asyncio
@patch("backend.session_tools.ChatResolver.resolve")
@patch("backend.session_tools.retrieve_documents")
@patch("backend.session_tools.get_surrounding_messages")
async def test_handle_search_from_person_lexical_only(
    mock_get_surrounding_messages,
    mock_retrieve_documents,
    mock_resolve,
    mock_context,
    sample_raw_docs,
):
    from backend.session_tools import ChatResolution
    mock_resolve.return_value = ChatResolution(chat_id=123, source="name_match")

    lexical_doc = sample_raw_docs("doc1", "what is your task?", "2023-01-01T10:00:00")
    mock_retrieve_documents.return_value = [lexical_doc]

    surrounding_doc = sample_raw_docs(
        "doc0", "I have a task", "2023-01-01T09:59:00", is_from_me=True
    )
    mock_get_surrounding_messages.return_value = [surrounding_doc]

    args = SearchFromPersonArgs(query="task", name="Alice", limit=200)

    with (
        patch(
            "backend.session_tools._get_chroma_collection",
            side_effect=Exception("Chroma failure"),
        ),
        patch("backend.session_tools.synthesize_answer") as mock_sync,
    ):
        mock_sync.return_value = "what is your task?\nI have a task\nokay"
        result = await _handle_search_from_person(args, mock_context)

    assert "what is your task?" in result.result
    assert "I have a task" in result.result


@pytest.mark.asyncio
@patch("backend.session_tools.ChatResolver.resolve")
async def test_handle_search_from_person_no_chat(mock_resolve, mock_context):
    mock_resolve.side_effect = ChatResolutionError("No chat found")
    
    empty_context = SessionToolContext(session_id="test", context_chat_id=None)
    
    result = await run_tool("search_from_person", {"query": "test"}, empty_context)
    
    assert "No chat found" in result.result


@pytest.mark.asyncio
@patch("backend.session_tools.ChatResolver.resolve")
@patch("backend.session_tools.retrieve_documents")
async def test_handle_search_from_person_no_results(
    mock_retrieve_documents,
    mock_resolve,
    mock_context,
):
    from backend.session_tools import ChatResolution
    mock_resolve.return_value = ChatResolution(chat_id=123, source="name_match")

    mock_retrieve_documents.return_value = []

    args = SearchFromPersonArgs(query="something", name="Alice", limit=50)

    with patch(
        "backend.session_tools._get_chroma_collection",
        side_effect=Exception("Chroma failure"),
    ):
        result = await _handle_search_from_person(args, mock_context)

    assert "No messages found from that person" in result.result
