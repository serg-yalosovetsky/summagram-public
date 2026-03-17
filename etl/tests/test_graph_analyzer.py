"""
Unit tests for etl/processing/graph.py — GraphAnalyzer.

Mocks:
- httpx.AsyncClient → returns fake embeddings
- database (get_db, save_graph_cache, get_latest_graph_cache)
"""

import json
import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
import numpy as np


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

SAMPLE_ROWS = [
    {
        "doc_id": "telegram_100_1",
        "content": "Hello world from Alice",
        "metadata": json.dumps(
            {
                "sender_id": 1,
                "sender_name": "Alice",
                "chat_id": 100,
                "reply_to_msg_id": None,
            }
        ),
    },
    {
        "doc_id": "telegram_100_2",
        "content": "Hi Alice, this is Bob",
        "metadata": json.dumps(
            {
                "sender_id": 2,
                "sender_name": "Bob",
                "chat_id": 100,
                "reply_to_msg_id": 1,
            }
        ),
    },
    {
        "doc_id": "telegram_100_3",
        "content": "Another message from Alice",
        "metadata": json.dumps(
            {
                "sender_id": 1,
                "sender_name": "Alice",
                "chat_id": 100,
                "reply_to_msg_id": None,
            }
        ),
    },
    {
        "doc_id": "telegram_100_4",
        "content": "Charlie joins the chat",
        "metadata": json.dumps(
            {
                "sender_id": 3,
                "sender_name": "Charlie",
                "chat_id": 100,
                "reply_to_msg_id": None,
            }
        ),
    },
]

REPLY_ROWS = [
    {
        "metadata": json.dumps(
            {
                "sender_id": 2,
                "sender_name": "Bob",
                "chat_id": 100,
                "reply_to_msg_id": 1,
            }
        ),
    }
]

FAKE_EMBEDDING_DIM = 8


def make_fake_embedding_response(texts):
    """Create a fake /v1/embeddings response."""
    data = []
    for i, _ in enumerate(texts):
        emb = np.random.default_rng(i).random(FAKE_EMBEDDING_DIM).tolist()
        data.append({"object": "embedding", "embedding": emb, "index": i})
    return {"data": data, "model": "test-model", "usage": {}}


# ---------------------------------------------------------------------------
# Helper: mock DB context manager
# ---------------------------------------------------------------------------


class FakeCursor:
    def __init__(self, rows):
        self._rows = rows
        self._idx = 0

    async def __aenter__(self):
        return self

    async def __aexit__(self, *a):
        pass

    def __aiter__(self):
        return self

    async def __anext__(self):
        if self._idx >= len(self._rows):
            raise StopAsyncIteration
        row = self._rows[self._idx]
        self._idx += 1
        return row

    async def fetchall(self):
        return self._rows

    async def fetchone(self):
        return self._rows[0] if self._rows else None


class FakeDB:
    def __init__(self, query_map=None):
        self.query_map = query_map or {}
        self.row_factory = None

    async def __aenter__(self):
        return self

    async def __aexit__(self, *a):
        pass

    async def fetch(self, sql, *args):
        # Return list of dicts reflecting asyncpg fetch() behaviour
        if "reply_to_msg_id" in sql and "IS NOT NULL" in sql:
            return REPLY_ROWS
        return SAMPLE_ROWS

    def execute(self, sql, *args):
        if "reply_to_msg_id" in sql and "IS NOT NULL" in sql:
            return FakeCursor(REPLY_ROWS)
        return FakeCursor(SAMPLE_ROWS)

    async def commit(self):
        pass


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_db():
    """Patch get_db to return our FakeDB."""
    fake = FakeDB()

    from contextlib import asynccontextmanager

    @asynccontextmanager
    async def _get_db():
        yield fake

    return _get_db


@pytest.fixture
def mock_cache_empty():
    """No cached graph."""
    return AsyncMock(return_value=None)


@pytest.fixture
def mock_save_cache():
    return AsyncMock()


@pytest.fixture
def mock_httpx():
    """Mock httpx.AsyncClient.post to return fake embeddings."""

    async def fake_post(url, json=None, **kw):
        texts = json.get("input", []) if isinstance(json, dict) else []
        resp_data = make_fake_embedding_response(texts)
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.raise_for_status = MagicMock()
        mock_resp.json.return_value = resp_data
        return mock_resp

    return fake_post


def test_aggregate_user_messages(mock_db):
    """Messages are grouped by sender_id."""
    with (
        patch("etl.processing.graph.get_db", mock_db),
        patch("etl.processing.graph.save_graph_cache", AsyncMock()),
        patch("etl.processing.graph.get_latest_graph_cache", AsyncMock(return_value=None)),
    ):
        from etl.processing.graph import GraphAnalyzer

        analyzer = GraphAnalyzer(backend_url="http://test:8000/v1")
        profiles = asyncio.run(analyzer._aggregate_user_messages())

        assert len(profiles) == 3  # Alice, Bob, Charlie
        assert 1 in profiles
        assert profiles[1].sender_name == "Alice"
        assert len(profiles[1].texts) == 2  # Two messages from Alice


def test_compute_similarity():
    """Cosine similarity matrix has correct shape."""
    from etl.processing.graph import GraphAnalyzer

    embeddings = np.random.rand(3, 8).astype(np.float32)
    sim = GraphAnalyzer._compute_similarity(embeddings)
    assert sim.shape == (3, 3)
    # Diagonal should be ~1.0
    for i in range(3):
        assert abs(sim[i][i] - 1.0) < 1e-5


def test_cluster_users():
    """KMeans clustering returns correct number of labels."""
    from etl.processing.graph import GraphAnalyzer

    analyzer = GraphAnalyzer(
        backend_url="http://test:8000/v1",
        n_clusters=2,
    )
    embeddings = np.random.rand(5, 8).astype(np.float32)
    labels = analyzer._cluster_users(embeddings)
    assert labels.shape == (5,)
    assert set(labels).issubset({0, 1})


def test_serialize_graph():
    """Graph serialization produces expected structure."""
    import networkx as nx
    from etl.processing.graph import GraphAnalyzer

    G = nx.Graph()
    G.add_node(1, label="Alice", cluster=0, message_count=5)
    G.add_node(2, label="Bob", cluster=1, message_count=3)
    G.add_edge(1, 2, weight=0.8, edge_type="similarity", interaction_count=0)

    result = GraphAnalyzer._serialize_graph(G)
    assert result.node_count == 2
    assert result.edge_count == 1
    assert len(result.nodes) == 2
    assert len(result.edges) == 1
    assert result.edges[0].weight == 0.8


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
