import pytest
from unittest.mock import patch, AsyncMock


@pytest.mark.asyncio
async def test_sim():
    with patch(
        "backend.retrieval.search_messages_from_others", new_callable=AsyncMock
    ) as m:
        m.return_value = ["mock_doc"]
        from backend.retrieval import retrieve_documents, make_retrieval_plan

        plan = make_retrieval_plan("task", 123)
        docs = await retrieve_documents(plan)
        print("DOCS WAS:", docs)
        m.assert_called()


import asyncio  # noqa: E402

asyncio.run(test_sim())
