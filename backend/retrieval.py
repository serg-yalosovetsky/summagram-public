import logging
from typing import List, Optional, Literal, Dict, Any
from pydantic import BaseModel

from etl.db.raw_documents import (
    search_messages_from_others,
    get_recent_messages,
    _escape_like,
)
from etl.db.raw_documents import get_raw_documents_by_ids
from etl.db.core import (
    get_db,
    row_to_raw_document,
)
from shared.config import Config

logger = logging.getLogger(__name__)


# --- Models ---
class RetrievalMode(BaseModel):
    mode: Literal[
        "select_tail",
        "select_head",
        "select_time",
        "lexical",
        "vector",
        "hybrid",
        "none",
    ]
    reason: str


class RetrievalPlan(BaseModel):
    modes: List[RetrievalMode]
    limit: int = 50
    target_chat_ids: Optional[List[int]] = None
    time_range: Optional[tuple[int, int]] = None
    query: Optional[str] = None


class RetrievedItem(BaseModel):
    score: float = 0.0
    doc_id: str
    chat_id: int
    text: str
    metadata: Dict[str, Any]


class ContextPack(BaseModel):
    items: List[RetrievedItem]
    total_tokens_approx: int


# --- Helpers ---
_TASK_QUESTION_PATTERNS = [
    "?",
    "homework",
    "task",
    "assignment",
    "exercise",
    "завдання",
    "домашка",
    "задача",
    "задание",
    "зроби",
    "напиши",
    "виконай",
    "прочитай",
    "please",
    "write",
    "read",
    "send",
    "check",
    "надішли",
    "перевір",
    "подивись",
]


def make_retrieval_plan(
    query: str, chat_id: Optional[int], limit: int = 20
) -> RetrievalPlan:
    """Plan retrieval based on heuristic rules."""
    q = query.lower()
    plan = RetrievalPlan(
        modes=[],
        target_chat_ids=[chat_id] if chat_id else None,
        query=query,
        limit=limit,
    )

    if "last" in q or "recent" in q or "последн" in q or "останн" in q:
        plan.modes.append(
            RetrievalMode(mode="select_tail", reason="User asked for recent info")
        )

    if "first" in q or "beginning" in q or "первы" in q or "початк" in q:
        plan.modes.append(
            RetrievalMode(mode="select_head", reason="User asked for early messages")
        )

    is_task_q = any(p in q for p in _TASK_QUESTION_PATTERNS)
    words = len(q.split())

    if is_task_q or words <= 3:
        plan.modes.append(
            RetrievalMode(mode="hybrid", reason="Task request or keyword search")
        )
    elif words > 3 and not plan.modes:
        plan.modes.append(
            RetrievalMode(
                mode="vector", reason="Semantic query implies meaning-based matching"
            )
        )

    if not plan.modes:
        plan.modes.append(
            RetrievalMode(mode="hybrid", reason="Default recommended mode")
        )

    return plan


def _reciprocal_rank_fusion(*result_lists: list, k: int = 60, top_n: int = 15) -> list:
    scores: dict[str, float] = {}
    doc_map: dict[str, object] = {}
    for results in result_lists:
        for rank, doc in enumerate(results):
            doc_id = (
                doc.doc_id if hasattr(doc, "doc_id") else doc.get("doc_id", str(rank))
            )
            scores[doc_id] = scores.get(doc_id, 0.0) + 1.0 / (k + rank + 1)
            doc_map[doc_id] = doc
    ranked_ids = sorted(scores, key=lambda did: scores[did], reverse=True)[:top_n]
    return [doc_map[did] for did in ranked_ids]


# Duplicate from session_tools for pure retrieval
async def _sqlite_text_search(query: str, chat_id: Optional[int], limit: int) -> list:
    conditions = ["content ILIKE ?"]
    pattern = f"%{_escape_like(query)}%"
    params: list = [pattern]
    if chat_id is not None:
        conditions.append("metadata->>'chat_id' = ?")
        params.append(str(chat_id))
    params.append(limit)
    # Note: asyncpg requires indexed params ($1, $2) instead of ?
    # Let's fix params indexing:
    conditions_pg = ["content ILIKE $1"]
    if chat_id is not None:
        conditions_pg.append("metadata->>'chat_id' = $2")
    where_pg = " AND ".join(conditions_pg)
    sql_pg = f"""
        SELECT content, timestamp, source_id, metadata, doc_id
        FROM raw_documents WHERE {where_pg}
        ORDER BY timestamp DESC LIMIT ${len(params)}
    """
    async with get_db() as db:
        rows = await db.fetch(sql_pg, *params)
        results = [row_to_raw_document(r) for r in rows]
        results.reverse()
        return results


async def retrieve_documents(plan: RetrievalPlan, chroma_collection=None) -> List[Any]:
    merged_docs = []

    # Simple single-chat fallback for now
    chat_id = plan.target_chat_ids[0] if plan.target_chat_ids else None
    limit = plan.limit

    lexical_results = []
    vector_results = []

    for mode in plan.modes:
        if mode.mode == "select_tail":
            docs = await get_recent_messages(chat_id=chat_id, limit=limit)
            return docs

        elif mode.mode in ["lexical", "hybrid"]:
            lexical_results = await search_messages_from_others(
                chat_id=chat_id, query=plan.query or "?", limit=limit
            )

        if mode.mode in ["vector", "hybrid"]:
            if plan.query and chroma_collection:
                try:
                    from inference import LocalInferenceService

                    service = LocalInferenceService()
                    embeddings = await service.get_embeddings([plan.query])
                    if embeddings and embeddings[0]:
                        chroma_kwargs: dict = {
                            "query_embeddings": [embeddings[0]],
                            "n_results": limit,
                        }
                        if chat_id is not None:
                            chroma_kwargs["where"] = {"chat_id": chat_id}

                        results = chroma_collection.query(**chroma_kwargs)
                        ids = results.get("ids", [[]])[0]
                        metadatas = results.get("metadatas", [[]])[0]
                        if ids:
                            specs = []
                            for c_id, m in zip(ids, metadatas):
                                meta = m or {}
                                m_doc_id = meta.get("doc_id") or c_id
                                m_source_id = (
                                    meta.get("source_id") or f"telegram_{chat_id}"
                                )
                                specs.append((m_source_id, m_doc_id))
                            vector_results = await get_raw_documents_by_ids(specs)
                except Exception as exc:
                    logger.warning(f"Vector search failed: {exc}")

    if lexical_results and vector_results:
        merged_docs = _reciprocal_rank_fusion(
            lexical_results, vector_results, top_n=limit
        )
    elif lexical_results:
        merged_docs = lexical_results
    elif vector_results:
        merged_docs = vector_results

    return merged_docs


def compact_context(docs: List[Any], max_tokens: int = 4000) -> ContextPack:
    # 1. Deduplicate by doc_id
    seen = set()
    unique_items = []

    for d in docs:
        doc_id = getattr(
            d, "doc_id", d.get("doc_id") if isinstance(d, dict) else str(id(d))
        )
        if doc_id not in seen:
            seen.add(doc_id)
            meta = (
                getattr(d, "metadata", d.get("metadata", {}))
                if isinstance(d, dict)
                else d.metadata
            )
            chat_id = meta.get("chat_id", 0)
            text = (
                getattr(d, "content", d.get("content", ""))
                if isinstance(d, dict)
                else d.content
            )

            # Use original text if available
            if "original_text" in meta:
                text = meta["original_text"]

            unique_items.append(
                RetrievedItem(doc_id=doc_id, chat_id=chat_id, text=text, metadata=meta)
            )

    # Compute char counts proxy for token length
    # Truncate if exceeding max approximations (character counting proxy = length / 3)
    total_tokens = 0
    final_items = []

    # Add from most recent backwards or maintain heuristic ordering
    for i in unique_items:
        toks = len(i.text) // 3 + 10  # heuristic
        if total_tokens + toks > max_tokens and len(final_items) > 3:
            # We keep at least 3 items
            break
        final_items.append(i)
        total_tokens += toks

    return ContextPack(items=final_items, total_tokens_approx=total_tokens)


def build_backlinks(text: str, doc_id: str, chat_id: int) -> str:
    """Append a markdown backlink to a specific statement or context block."""
    cit_link = f"[#cite]({Config.FRONTEND_URL}/#/chat/{chat_id}?msg={doc_id})"
    return f"{text} {cit_link}"


def synthesize_answer(context: ContextPack, user_query: str) -> str:
    """Format the context pack to be injected into an LLM prompt as context."""
    if not context.items:
        return "No relevant context found."

    parts = ["--- RETRIEVED CONTEXT ---"]
    for idx, item in enumerate(context.items):
        t = build_backlinks(item.text, item.doc_id, item.chat_id)
        author = item.metadata.get("author", "Unknown")
        ts = item.metadata.get("timestamp", "")
        parts.append(f"[{idx + 1}] {ts} {author}: {t}")
    parts.append("-------------------------")

    return "\n".join(parts)
