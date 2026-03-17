import pytest


@pytest.mark.asyncio
async def test_submit_job(client):
    payload = {"params": {"source": "test"}}
    response = client.post("/jobs/telegram", json=payload)
    assert response.status_code == 200
    assert response.json()["job_id"] == "test-job-id"
    assert response.json()["status"] == "queued"


@pytest.mark.asyncio
async def test_get_job_status(client):
    response = client.get("/jobs/test-job-id")
    assert response.status_code == 200
    assert response.json()["job_id"] == "test-job-id"
    assert response.json()["status"] == "processing"


@pytest.mark.asyncio
async def test_health_check(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


@pytest.mark.asyncio
async def test_submit_job_errors(client):
    # Unsupported source
    response = client.post("/jobs/invalid_source", json={"params": {}})
    assert response.status_code == 400

    # Missing params in body
    response = client.post("/jobs/telegram", json={})
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_reindex_media(client):
    # Test default photo/audio
    payload = {"media_types": ["photo", "audio"], "force_reindex": True}
    response = client.post("/reindex-media", json=payload)
    assert response.status_code == 200
    assert "job_id" in response.json()
    assert response.json()["status"] == "queued"

    # Test with all supported types
    payload = {
        "media_types": ["photo", "audio", "document", "voice", "video"],
        "force_reindex": False,
    }
    response = client.post("/reindex-media", json=payload)
    assert response.status_code == 200
    assert response.json()["status"] == "queued"

    # Test error: invalid media type
    payload = {"media_types": ["completely_invalid_type"], "force_reindex": False}
    response = client.post("/reindex-media", json=payload)
    assert response.status_code == 422  # Pydantic validation error due to Literal
