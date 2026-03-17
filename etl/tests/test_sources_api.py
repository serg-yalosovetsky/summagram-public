import pytest
from unittest.mock import AsyncMock, MagicMock

pytestmark = pytest.mark.integration


@pytest.mark.asyncio
async def test_get_source_dialogs(client, mock_job_manager):
    # Mock source class and instance
    mock_source_cls = MagicMock()
    mock_source = mock_source_cls.return_value
    mock_source.connect = AsyncMock()
    mock_source.disconnect = AsyncMock()
    mock_source.get_dialogs = AsyncMock(return_value=[{"id": "1", "name": "Test Chat"}])

    # Configure manager to return our mock source class
    mock_job_manager.sources = {"telegram": mock_source_cls}

    response = client.get("/sources/telegram/dialogs?limit=10")
    assert response.status_code == 200
    data = response.json()
    assert "dialogs" in data
    assert data["dialogs"][0]["name"] == "Test Chat"
    mock_source.get_dialogs.assert_called_with(10)


@pytest.mark.asyncio
async def test_get_source_dialogs_unsupported(client, mock_job_manager):
    mock_job_manager.sources = {}
    response = client.get("/sources/unsupported_type/dialogs")
    assert response.status_code == 400
    assert response.json()["detail"] == "Unknown source type"
