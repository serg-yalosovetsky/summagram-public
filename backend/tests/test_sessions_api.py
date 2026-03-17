import pytest
import uuid
from etl.db.sessions import create_session

pytestmark = pytest.mark.integration


@pytest.mark.asyncio
async def test_create_session(client):
    session_id = str(uuid.uuid4())
    payload = {
        "id": session_id,
        "title": "Test Session",
        "context_chat_id": 12345,
        "meta": {"key": "value"},
    }

    response = client.post("/sessions", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == session_id
    assert data["title"] == "Test Session"


@pytest.mark.asyncio
async def test_list_sessions(client):
    # Ensure there's at least one session
    session_id = "test-session-list"
    await create_session(session_id, "List Test Session")

    response = client.get("/sessions")
    assert response.status_code == 200
    data = response.json()
    assert len(data) >= 1
    assert any(s["id"] == session_id for s in data)


@pytest.mark.asyncio
async def test_get_session_details(client):
    session_id = "test-session-details"
    await create_session(session_id, "Details Test Session")

    response = client.get(f"/session/{session_id}")
    assert response.status_code == 200
    assert response.json()["id"] == session_id


@pytest.mark.asyncio
async def test_send_session_message(client, mock_session_agent):
    session_id = "test-session-msg"
    await create_session(session_id, "Message Test Session")

    payload = {"content": "Hello AI", "context_chat_id": 12345}

    response = client.post(f"/session/{session_id}/messages", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert "user_message" in data
    assert "assistant_message" in data
    assert data["user_message"]["content"] == "Hello AI"
    assert data["assistant_message"]["content"] == "Mocked AI response"


@pytest.mark.asyncio
async def test_get_session_details_not_found(client):
    response = client.get("/session/session-that-does-not-exist")
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_get_session_messages(client):
    session_id = "test-session-msgs-list"
    await create_session(session_id, "Messages List Test")

    # Simple check for messages endpoint
    response = client.get(f"/session/{session_id}/messages?limit=10&offset=0")
    assert response.status_code == 200
    assert isinstance(response.json(), list)


@pytest.mark.asyncio
async def test_create_session_validation_error(client):
    # Missing title
    payload = {"id": "test-id"}
    response = client.post("/sessions", json=payload)
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_send_message_validation_error(client):
    session_id = "test-msg-val"
    await create_session(session_id, "Validation Test")

    # Missing content
    payload = {"context_chat_id": 12345}
    response = client.post(f"/session/{session_id}/messages", json=payload)
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_send_session_message_find_chat_tool_then_get_messages(
    client, mock_session_agent
):
    """When user asks about messages from a person, run_session_agent returns the expected response."""
    session_id = "test-session-tools"
    await create_session(session_id, "Tools Test Session", context_chat_id=None)
    mock_session_agent.return_value = ("Your last message to Lev was: Hello.", None)
    response = client.post(
        f"/session/{session_id}/messages",
        json={"content": "What is my last message to lev?"},
    )
    assert response.status_code == 200
    data = response.json()
    assert "assistant_message" in data
    assert (
        data["assistant_message"]["content"] == "Your last message to Lev was: Hello."
    )


@pytest.mark.asyncio
async def test_send_session_message_get_last_message_no_chat(
    client, mock_session_agent
):
    """When user asks 'What is my last message?' with no name, run_session_agent returns the expected response."""
    session_id = "test-session-last-msg"
    await create_session(session_id, "Last Message Test", context_chat_id=None)
    mock_session_agent.return_value = (
        "Your last message was: See you tomorrow (Chat ID: 456).",
        None,
    )
    response = client.post(
        f"/session/{session_id}/messages",
        json={"content": "What is my last message?"},
    )
    assert response.status_code == 200
    data = response.json()
    assert "assistant_message" in data
    assert (
        data["assistant_message"]["content"]
        == "Your last message was: See you tomorrow (Chat ID: 456)."
    )


@pytest.mark.asyncio
async def test_send_session_message_media_reply(client, mock_session_agent):
    """When run_session_agent returns content with media and referenced_message, API includes both."""
    session_id = "test-session-media"
    await create_session(session_id, "Media Test Session", context_chat_id=None)
    content = "Lev sent you a photo. Download: /media/tg_123_456.jpg. Description: sunset at the beach."
    referenced = {
        "chat_id": 123,
        "doc_id": "doc_1",
        "content": "",
        "media_url": "/media/tg_123_456.jpg",
        "media_type": "photo",
        "description": "sunset at the beach",
        "sender_name": "Lev",
    }
    mock_session_agent.return_value = (content, referenced)
    response = client.post(
        f"/session/{session_id}/messages",
        json={"content": "What did Lev send me last?"},
    )
    assert response.status_code == 200
    data = response.json()
    assert "assistant_message" in data
    assert "/media/" in data["assistant_message"]["content"]
    assert data["assistant_message"]["referenced_message"] is not None
    assert (
        data["assistant_message"]["referenced_message"]["media_url"]
        == "/media/tg_123_456.jpg"
    )
