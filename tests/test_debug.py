import asyncio
from unittest.mock import patch, AsyncMock
from backend.session_tools import _handle_search_from_person, SessionToolContext
from etl.database import ChatSearchResult
from etl.models import RawDocumentRow


async def run():
    ctx = SessionToolContext(session_id="t", context_chat_id=123)
    args = {"query": "task", "name": "Alice"}

    with patch(
        "backend.session_tools.find_chats_by_contact_name", new_callable=AsyncMock
    ) as m_fc:
        m_fc.return_value = [
            ChatSearchResult(
                chat_id=123, contact_name="Alice", chat_title="A", is_private=True
            )
        ]

        with patch(
            "backend.retrieval.search_messages_from_others", new_callable=AsyncMock
        ) as m_s:
            doc = RawDocumentRow(
                source_id="1", doc_id="1", content="t", timestamp="2023", metadata={}
            )
            m_s.return_value = [doc]

            with patch(
                "etl.database.get_surrounding_messages", new_callable=AsyncMock
            ) as m_gets:
                m_gets.return_value = []

                with patch("backend.session_tools._get_chroma_collection") as m_chroma:
                    m_chroma.side_effect = Exception("Chroma fail")

                    res = await _handle_search_from_person(args, ctx)
                    print("RESULT:", res)


asyncio.run(run())
