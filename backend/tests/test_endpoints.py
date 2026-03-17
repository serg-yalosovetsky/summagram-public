import pytest
from unittest.mock import patch, AsyncMock

pytestmark = pytest.mark.integration


@pytest.mark.asyncio
async def test_list_chats(client):
    with patch("routes.svc.list_chats", new_callable=AsyncMock) as mock_list_chats:
        # 1. Default call
        mock_list_chats.return_value = [{"source_id": 1}]
        response = client.get("/chats")
        assert response.status_code == 200
        assert len(response.json()) == 1
        mock_list_chats.assert_called_with(50, 0, 0.0)

        # 2. Call with params
        response = client.get("/chats?limit=10&offset=5&min_importance=0.5")
        assert response.status_code == 200
        mock_list_chats.assert_called_with(10, 5, 0.5)


@pytest.mark.asyncio
async def test_list_contacts(client):
    with patch(
        "routes.svc.list_contacts", new_callable=AsyncMock
    ) as mock_list_contacts:
        mock_list_contacts.return_value = []
        response = client.get("/contacts")
        assert response.status_code == 200
        mock_list_contacts.assert_called_with(50, 0)


@pytest.mark.asyncio
async def test_list_contacts_with_params(client):
    with patch(
        "routes.svc.list_contacts", new_callable=AsyncMock
    ) as mock_list_contacts:
        mock_list_contacts.return_value = []
        response = client.get("/contacts?limit=5&offset=2")
        assert response.status_code == 200
        mock_list_contacts.assert_called_with(5, 2)


@pytest.mark.asyncio
async def test_sessions_endpoints(client):
    with (
        patch("routes.svc.list_sessions", new_callable=AsyncMock) as mock_list_sessions,
        patch(
            "routes.svc.create_session", new_callable=AsyncMock
        ) as mock_create_session,
    ):
        # Test GET /sessions
        mock_list_sessions.return_value = [{"id": "sessions-1", "title": "Test"}]
        response = client.get("/sessions")
        assert response.status_code == 200
        assert len(response.json()) == 1
        mock_list_sessions.assert_called_with(50, 0)

        # Test POST /sessions (New Session)
        mock_create_session.return_value = {
            "id": "new-session-id",
            "title": "New",
            "context_chat_id": None,
            "meta": {},
        }
        response = client.post(
            "/sessions", json={"id": "new-session-id", "title": "New"}
        )
        assert response.status_code == 200
        mock_create_session.assert_called_with("new-session-id", "New", None, None)

        # Test POST /sessions (From Chat)
        response = client.post(
            "/sessions",
            json={
                "id": "session-from-chat",
                "title": "From Chat",
                "context_chat_id": 123,
            },
        )
        assert response.status_code == 200
        mock_create_session.assert_called_with(
            "session-from-chat", "From Chat", 123, None
        )


@pytest.mark.asyncio
async def test_get_chat_details(client):
    with patch("routes.svc.get_chat_by_id", new_callable=AsyncMock) as mock_get_chat:
        # Valid
        mock_get_chat.return_value = {"source_id": 123, "title": "Test"}
        response = client.get("/chat/123")
        assert response.status_code == 200
        assert response.json()["source_id"] == 123

        # Not found
        mock_get_chat.return_value = None
        response = client.get("/chat/999")
        assert response.status_code == 404


@pytest.mark.asyncio
async def test_get_contact_details(client):
    with patch(
        "routes.svc.get_contact_by_id", new_callable=AsyncMock
    ) as mock_get_contact:
        mock_get_contact.return_value = {"source_id": 456, "name": "User"}
        response = client.get("/contact/456")
        assert response.status_code == 200

        mock_get_contact.return_value = None
        response = client.get("/contact/999")
        assert response.status_code == 404


@pytest.mark.asyncio
async def test_get_chat_messages(client):
    with patch(
        "routes.svc.get_chat_messages", new_callable=AsyncMock
    ) as mock_get_messages:
        mock_get_messages.return_value = [{"content": "hi"}]
        response = client.get("/chat/123/messages?limit=20&offset=10")
        assert response.status_code == 200
        mock_get_messages.assert_called_with(123, 20, 10)


@pytest.mark.asyncio
async def test_get_documents(client):
    with patch("routes.svc.list_documents", new_callable=AsyncMock) as mock_list_docs:
        mock_list_docs.return_value = []
        response = client.get("/documents")
        assert response.status_code == 200
        mock_list_docs.assert_called_with(50, 0, None)


@pytest.mark.asyncio
async def test_health_check(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


@pytest.mark.asyncio
async def test_config_endpoints(client):
    # GET
    response = client.get("/config")
    assert response.status_code == 200
    assert "VISION_PROVIDER" in response.json()

    # POST (Update)
    response = client.post("/config", json={"VISION_PROVIDER": "google"})
    assert response.status_code == 200
    assert response.json()["config"]["VISION_PROVIDER"] == "google"


@pytest.mark.asyncio
async def test_analyze_image_errors(client):
    with patch("os.path.exists", return_value=False):
        response = client.post(
            "/analyze-image", json={"image_path": "/invalid/path.jpg"}
        )
        assert response.status_code == 404
        assert "not found" in response.json()["detail"]
