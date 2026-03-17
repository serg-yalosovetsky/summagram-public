"""
Unit test for session message flow with run_session_agent.
"""

import pytest

from etl.db.sessions import create_session
import backend.service as svc


@pytest.mark.asyncio
async def test_message_retrieval_flow(client, mock_session_agent):
    """When user asks about messages, run_session_agent returns chat history summary."""
    session_id = "test_session_retrieval"
    chat_id = 999
    content = "What were my last messages?"

    await create_session(session_id, "Retrieval Test", context_chat_id=chat_id)
    mock_session_agent.return_value = (
        "Your last messages were from Alice and Bob.",
        None,
    )

    response = await svc.send_session_message(session_id, content, context_chat_id=None)

    assert "Alice" in response.assistant_message.content
    mock_session_agent.assert_called_once()


@pytest.mark.asyncio
async def test_thought_only_recovery_get_last_message(client, mock_session_agent):
    """When user asks for last message, run_session_agent returns the expected response."""
    session_id = "test_session_recovery"
    await create_session(session_id, "Recovery Test", context_chat_id=None)
    mock_session_agent.return_value = (
        "Your last message was: Hello from recovery test.",
        None,
    )

    response = await svc.send_session_message(session_id, "What is my last message?")

    assert "Hello from recovery test" in response.assistant_message.content
    mock_session_agent.assert_called_once()


@pytest.mark.asyncio
async def test_thought_only_recovery_post_tool_as_final_answer(
    client, mock_session_agent
):
    """When user asks for last message, run_session_agent returns summary with contact info."""
    session_id = "test_session_post_tool_recovery"
    await create_session(session_id, "Post-tool Recovery Test", context_chat_id=None)
    mock_session_agent.return_value = (
        "I received the last message from all chats. It was from 'Me' in a chat with Лев.",
        None,
    )

    response = await svc.send_session_message(session_id, "What is my last message?")

    assert "Лев" in response.assistant_message.content
    assert "Me" in response.assistant_message.content
    mock_session_agent.assert_called_once()
