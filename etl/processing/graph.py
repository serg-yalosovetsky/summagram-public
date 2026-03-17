"""
Social Graph & Interest Analysis module.

Builds a user-connection graph from Telegram message history using:
- Interaction frequency (reply chains)
- Semantic similarity (cosine similarity on user embeddings via Backend API)
- KMeans clustering for topic grouping
"""

import json
from dataclasses import dataclass, field
from typing import Optional

import httpx
import numpy as np
import networkx as nx
from sklearn.metrics.pairwise import cosine_similarity
from sklearn.cluster import KMeans
from loguru import logger

from shared.config import Config
from etl.db.core import get_db
from etl.db.chats import (
    get_reply_interaction_freq,
    save_graph_cache,
    get_latest_graph_cache,
)
from etl.schemas import GraphData, GraphEdge, GraphNode
from security import mask_pii


# ---------------------------------------------------------------------------
# Data Classes
# ---------------------------------------------------------------------------


@dataclass
class UserProfile:
    sender_id: int
    sender_name: str
    texts: list[str] = field(default_factory=list)

    @property
    def combined_text(self) -> str:
        """Concatenated message text (capped at 8 000 chars for embedding)."""
        full = " ".join(self.texts)
        return full[:8000]


# ---------------------------------------------------------------------------
# GraphAnalyzer
# ---------------------------------------------------------------------------

EMBEDDING_BATCH_SIZE = 32
SIMILARITY_THRESHOLD = 0.45
DEFAULT_N_CLUSTERS = 5


class GraphAnalyzer:
    """Analyses user connections and semantic interests."""

    def __init__(
        self,
        backend_url: Optional[str] = None,
        similarity_threshold: float = SIMILARITY_THRESHOLD,
        n_clusters: int = DEFAULT_N_CLUSTERS,
    ):
        # Derive embeddings URL from LLM_API_BASE
        base = backend_url or Config.LLM_API_BASE or "http://localhost:8003/v1"
        self.embeddings_url = base.rstrip("/").removesuffix("/v1") + "/v1/embeddings"
        self.similarity_threshold = similarity_threshold
        self.n_clusters = n_clusters

    # ------------------------------------------------------------------
    # Step 1: Aggregate messages by user
    # ------------------------------------------------------------------

    async def _aggregate_user_messages(self) -> dict[int, UserProfile]:
        """Group message content by sender_id from raw_documents."""
        profiles: dict[int, UserProfile] = {}

        async with get_db() as conn:
            rows = await conn.fetch(
                """
                SELECT content, metadata
                FROM raw_documents
                WHERE content IS NOT NULL AND content != ''
                """
            )
            for row in rows:
                content = row["content"]
                meta = row["metadata"]
                if not isinstance(meta, dict):
                    try:
                        meta = (
                            json.loads(meta) if isinstance(meta, str) else (meta or {})
                        )
                    except (json.JSONDecodeError, TypeError):
                        continue

                sender_id_raw = meta.get("sender_id")
                sender_name = meta.get("sender_name", "Unknown")
                if sender_id_raw is None:
                    continue

                try:
                    sender_id = int(sender_id_raw)
                except (ValueError, TypeError):
                    logger.debug(f"Skipping non-integer sender_id: {sender_id_raw}")
                    continue
                if sender_id not in profiles:
                    profiles[sender_id] = UserProfile(
                        sender_id=sender_id, sender_name=sender_name
                    )
                profiles[sender_id].texts.append(content)

        logger.info(f"Aggregated messages for {len(profiles)} users")
        return profiles

    # ------------------------------------------------------------------
    # Step 2: Get embeddings from Backend API (batched)
    # ------------------------------------------------------------------

    async def _get_embeddings(self, texts: list[str]) -> np.ndarray:
        """Call Backend /v1/embeddings in batches, return (n, dim) matrix."""
        all_embeddings: list[list[float]] = []

        async with httpx.AsyncClient(timeout=120.0) as client:
            for i in range(0, len(texts), EMBEDDING_BATCH_SIZE):
                batch = texts[i : i + EMBEDDING_BATCH_SIZE]
                logger.debug(
                    f"Embedding batch {i // EMBEDDING_BATCH_SIZE + 1}, size={len(batch)}"
                )
                logger.debug(
                    f"Sending request to embeddings API: {self.embeddings_url}"
                )
                try:
                    resp = await client.post(
                        self.embeddings_url,
                        json={"input": batch, "model": "default"},
                    )
                    resp.raise_for_status()
                except httpx.HTTPStatusError as se:
                    logger.error(
                        f"Embeddings API returned error: {se.response.status_code} - {se.response.text}"
                    )
                    raise
                except Exception as ex:
                    logger.error(
                        f"Failed to connect to embeddings API at {self.embeddings_url}: {ex}"
                    )
                    raise

                data = resp.json()["data"]
                # Sort by index to preserve ordering
                data.sort(key=lambda d: d["index"])
                all_embeddings.extend([d["embedding"] for d in data])

        matrix = np.array(all_embeddings, dtype=np.float32)
        logger.info(f"Embeddings matrix shape: {matrix.shape}")
        return matrix

    # ------------------------------------------------------------------
    # Step 3: Cosine similarity
    # ------------------------------------------------------------------

    @staticmethod
    def _compute_similarity(embeddings: np.ndarray) -> np.ndarray:
        """Return (n, n) cosine-similarity matrix."""
        return cosine_similarity(embeddings)

    # ------------------------------------------------------------------
    # Step 4: Build NetworkX graph
    # ------------------------------------------------------------------

    async def _compute_interaction_freq(self) -> dict[tuple[int, int], int]:
        """Count reply-based interactions between users."""
        rows = await get_reply_interaction_freq()
        freq = {(u1, u2): cnt for u1, u2, cnt in rows}
        logger.info(f"Found {len(freq)} interaction pairs from replies")
        return freq

    def _build_graph(
        self,
        profiles: dict[int, UserProfile],
        similarity_matrix: np.ndarray,
        interaction_freq: dict[tuple[int, int], int],
        clusters: np.ndarray,
    ) -> nx.Graph:
        """Build the social graph with nodes=users, edges=interactions+similarity."""
        G = nx.Graph()
        user_ids = list(profiles.keys())

        # Add nodes
        for idx, uid in enumerate(user_ids):
            p = profiles[uid]
            G.add_node(
                uid,
                label=mask_pii(p.sender_name),
                sender_name=p.sender_name,
                cluster=int(clusters[idx]) if clusters is not None else 0,
                message_count=len(p.texts),
            )

        # Add edges from semantic similarity
        n = len(user_ids)
        for i in range(n):
            for j in range(i + 1, n):
                sim = float(similarity_matrix[i][j])
                if sim >= self.similarity_threshold:
                    G.add_edge(
                        user_ids[i],
                        user_ids[j],
                        weight=sim,
                        edge_type="similarity",
                    )

        # Add / reinforce edges from interaction frequency
        for (a, b), count in interaction_freq.items():
            if G.has_edge(a, b):
                # Reinforce existing edge
                G[a][b]["weight"] = max(G[a][b]["weight"], min(count / 10.0, 1.0))
                G[a][b]["interaction_count"] = count
                G[a][b]["edge_type"] = "both"
            elif a in G.nodes and b in G.nodes:
                G.add_edge(
                    a,
                    b,
                    weight=min(count / 10.0, 1.0),
                    interaction_count=count,
                    edge_type="interaction",
                )

        logger.info(
            f"Graph built: {G.number_of_nodes()} nodes, {G.number_of_edges()} edges"
        )
        return G

    # ------------------------------------------------------------------
    # Step 5: Cluster users by interests
    # ------------------------------------------------------------------

    def _cluster_users(self, embeddings: np.ndarray) -> np.ndarray:
        """KMeans clustering. Returns cluster labels array."""
        n_samples = embeddings.shape[0]
        k = min(self.n_clusters, n_samples)
        if k < 2:
            return np.zeros(n_samples, dtype=int)

        kmeans = KMeans(n_clusters=k, random_state=42, n_init="auto")
        labels = kmeans.fit_predict(embeddings)
        logger.info(f"Clustered {n_samples} users into {k} groups")
        return labels

    # ------------------------------------------------------------------
    # Step 6: Orchestrator
    # ------------------------------------------------------------------

    async def build(self, force_rebuild: bool = False) -> GraphData:
        """
        Full pipeline: aggregate → embed → similarity → cluster → graph → cache.
        Returns serialised graph as Pydantic model.
        """
        # Check cache first
        if not force_rebuild:
            cached = await get_latest_graph_cache()
            if cached:
                logger.info("Returning cached graph data")
                return GraphData.model_validate_json(cached.graph_json)

        # 1. Aggregate
        logger.info("Step 1: Aggregating user messages...")
        profiles = await self._aggregate_user_messages()
        if len(profiles) < 2:
            logger.warning(f"Too few users found for graph ({len(profiles)})")
            return GraphData(
                nodes=[], edges=[], clusters=[], node_count=0, edge_count=0
            )

        user_ids = list(profiles.keys())

        # 2. Embeddings
        logger.info(f"Step 2: Generating embeddings for {len(user_ids)} users...")
        texts = [profiles[uid].combined_text for uid in user_ids]
        embeddings = await self._get_embeddings(texts)

        # 3. Similarity
        logger.info("Step 3: Computing similarity matrix...")
        sim_matrix = self._compute_similarity(embeddings)

        # 4. Interaction frequency (reply-based)
        logger.info("Step 4: Computing interaction frequency...")
        interaction_freq = await self._compute_interaction_freq()

        # 5. Clustering
        logger.info("Step 5: Clustering users...")
        clusters = self._cluster_users(embeddings)

        # 6. Build graph
        logger.info("Step 6: Building NetworkX graph object...")
        G = self._build_graph(profiles, sim_matrix, interaction_freq, clusters)

        # Serialise
        logger.info("Serializing graph data...")
        graph_data = self._serialize_graph(G)

        # 7. Persist
        logger.info("Step 7: Persisting graph cache to database...")
        graph_json = graph_data.model_dump_json(exclude_none=False)
        await save_graph_cache(graph_json, G.number_of_nodes(), G.number_of_edges())

        logger.info("Graph build completed successfully")
        return graph_data

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _serialize_graph(G: nx.Graph) -> GraphData:
        """Convert NetworkX graph to Pydantic GraphData model."""
        nodes = [
            GraphNode(
                id=nid,
                label=attrs.get("label", str(nid)),
                cluster=attrs.get("cluster", 0),
                message_count=attrs.get("message_count", 0),
            )
            for nid, attrs in G.nodes(data=True)
        ]

        edges = [
            GraphEdge(
                source=u,
                target=v,
                weight=round(attrs.get("weight", 0), 4),
                edge_type=attrs.get("edge_type", "unknown"),
                interaction_count=attrs.get("interaction_count", 0),
            )
            for u, v, attrs in G.edges(data=True)
        ]

        cluster_ids = sorted({n.cluster for n in nodes})

        return GraphData(
            nodes=nodes,
            edges=edges,
            clusters=cluster_ids,
            node_count=len(nodes),
            edge_count=len(edges),
        )
