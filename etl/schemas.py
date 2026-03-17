from pydantic import BaseModel
from typing import Dict, Any, Optional, List, Literal


class JobSubmitRequest(BaseModel):
    params: Dict[str, Any]


class JobSubmitResponse(BaseModel):
    job_id: str
    status: str


class JobStatusResponse(BaseModel):
    job_id: str
    status: str
    progress: float
    message: str
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None


MediaType = Literal["photo", "audio", "document", "voice", "video"]


class ReindexRequest(BaseModel):
    media_types: List[MediaType] = ["photo", "audio", "document", "voice"]
    force_reindex: bool = False


class AnalyzeChatsRequest(BaseModel):
    chat_ids: List[int]


# ---------------------------------------------------------------------------
# Social Graph API response models
# ---------------------------------------------------------------------------


class GraphNode(BaseModel):
    """Single node in the social graph."""

    id: int
    label: str
    cluster: int = 0
    message_count: int = 0


class GraphEdge(BaseModel):
    """Single edge in the social graph."""

    source: int
    target: int
    weight: float
    edge_type: str = "unknown"
    interaction_count: int = 0


class GraphData(BaseModel):
    """Serialised social graph for API/visualisation."""

    nodes: List[GraphNode] = []
    edges: List[GraphEdge] = []
    clusters: List[int] = []
    node_count: int = 0
    edge_count: int = 0
