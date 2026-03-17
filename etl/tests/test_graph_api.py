import pytest
from unittest.mock import patch
import json

pytestmark = pytest.mark.integration


@pytest.mark.asyncio
async def test_build_graph(client):
    with patch("etl.processing.graph.GraphAnalyzer.build") as mock_build:
        mock_build.return_value = {"nodes": [], "edges": []}
        response = client.post("/graph/build")
        assert response.status_code == 200
        assert "nodes" in response.json()
        mock_build.assert_called_with(force_rebuild=False)

        # Test force_rebuild=True
        response = client.post("/graph/build?force_rebuild=true")
        assert response.status_code == 200
        mock_build.assert_called_with(force_rebuild=True)


@pytest.mark.asyncio
async def test_get_graph_data(client):
    with patch("router.get_latest_graph_cache") as mock_get:
        mock_get.return_value = {"graph_json": json.dumps({"nodes": [], "edges": []})}
        response = client.get("/graph/data")
        assert response.status_code == 200
        assert "nodes" in response.json()
