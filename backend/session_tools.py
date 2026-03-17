"""
Session agent tool execution. Dispatches LLM tool calls to DB and returns
formatted strings. Used by service.send_session_message.
"""

from __future__ import annotations

import logging
import re
from collections import namedtuple
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Awaitable, Callable, Generic, Optional, TypeVar, Literal

from loguru import logger
import chromadb
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from shared.config import Config
from etl.db.chats import find_chats_by_contact_name
from etl.db.raw_documents import (
    search_documents_by_media,
    get_chat_history,
    get_last_messages_any_chat,
    get_recent_messages_from_others,
    get_surrounding_messages,
)
from backend.session_helpers import (
    format_chat_history,
    get_media_filename,
    parse_message_metadata,
)
from backend.retrieval import (
    make_retrieval_plan,
    retrieve_documents,
    compact_context,
    synthesize_answer,
    RetrievalPlan,
    RetrievalMode,
)


ToolResult = namedtuple("ToolResult", ["result", "metadata"])


@dataclass
class SessionToolContext:
    """Context passed to session tools: session id and optional linked chat."""
    session_id: str
    context_chat_id: Optional[int]


# =============================================================================
# Shared typed infrastructure
# =============================================================================

class ToolArgsModel(BaseModel):
    model_config = ConfigDict(extra="forbid")

ArgsT = TypeVar("ArgsT", bound=ToolArgsModel)

@dataclass(slots=True)
class ToolSpec(Generic[ArgsT]):
    args_model: type[ArgsT]
    handler: Callable[[ArgsT, SessionToolContext], Awaitable[ToolResult]]

class ToolExecutionError(Exception):
    pass

class ChatResolutionError(ToolExecutionError):
    pass


# =============================================================================
# Query normalization
# =============================================================================

class QueryKind(str, Enum):
    ASSIGNMENT = "assignment"
    LINK = "link"
    FILE = "file"
    MEETING = "meeting"
    GENERIC = "generic"

class SearchFromPersonArgs(ToolArgsModel):
    query: str = Field(min_length=1)
    name: Optional[str] = None
    limit: int = Field(default=50, ge=1, le=500)

class NormalizedQuery(BaseModel):
    original: str
    normalized: str
    kind: QueryKind
    expansion_terms: list[str] = Field(default_factory=list)

    @property
    def retrieval_query(self) -> str:
        if not self.expansion_terms:
            return self.normalized
        return " ".join([*self.expansion_terms, self.normalized])

class QueryNormalizer:
    _ASSIGNMENT_PATTERNS = (
        r"\bчто\s+(?:задал(?:а|и)?|задав(?:ал|ала)?|нужно|надо|делать)\b",
        r"\bзадание\b",
        r"\bдомашк(?:а|у|и|ой)\b",
        r"\bhomework\b",
        r"\bassign(?:ed)?\b",
    )

    _LINK_PATTERNS = (
        r"\bссылк(?:а|у|и|е|ой)\b",
        r"\blink\b",
        r"\bhttps?://\S+",
        r"\bwww\.",
        r"\bкинул(?:а)?\s+ссылк",
    )

    _FILE_PATTERNS = (
        r"\bфайл\b",
        r"\bдокумент\b",
        r"\bpdf\b",
        r"\bdocx?\b",
        r"\bприслал(?:а)?\s+файл\b",
        r"\bкинул(?:а)?\s+файл\b",
    )

    _MEETING_PATTERNS = (
        r"\bо\s+ч[её]м\s+говорили\b",
        r"\bобсуждали\b",
        r"\bдоговорились\b",
        r"\bчто\s+решили\b",
        r"\bчто\s+обсудили\b",
    )

    _ASSIGNMENT_EXPANSION = [
        "задание",
        "домашка",
        "упражнение",
        "прочитай",
        "напиши",
        "решите",
        "выполни",
        "параграф",
        "задача",
    ]

    _LINK_EXPANSION = [
        "ссылка",
        "http",
        "https",
        "link",
        "www",
    ]

    _FILE_EXPANSION = [
        "файл",
        "документ",
        "pdf",
        "doc",
        "прикрепила",
        "отправила",
    ]

    _MEETING_EXPANSION = [
        "встреча",
        "встретимся",
        "обсудим",
        "договорились",
        "созвон",
    ]

    def normalize(self, raw_query: str) -> NormalizedQuery:
        normalized = self._normalize_text(raw_query)

        if self._matches_any(normalized, self._ASSIGNMENT_PATTERNS):
            return NormalizedQuery(
                original=raw_query,
                normalized=normalized,
                kind=QueryKind.ASSIGNMENT,
                expansion_terms=self._ASSIGNMENT_EXPANSION.copy(),
            )

        if self._matches_any(normalized, self._LINK_PATTERNS):
            return NormalizedQuery(
                original=raw_query,
                normalized=normalized,
                kind=QueryKind.LINK,
                expansion_terms=self._LINK_EXPANSION.copy(),
            )

        if self._matches_any(normalized, self._FILE_PATTERNS):
            return NormalizedQuery(
                original=raw_query,
                normalized=normalized,
                kind=QueryKind.FILE,
                expansion_terms=self._FILE_EXPANSION.copy(),
            )

        if self._matches_any(normalized, self._MEETING_PATTERNS):
            return NormalizedQuery(
                original=raw_query,
                normalized=normalized,
                kind=QueryKind.MEETING,
                expansion_terms=self._MEETING_EXPANSION.copy(),
            )

        return NormalizedQuery(
            original=raw_query,
            normalized=normalized,
            kind=QueryKind.GENERIC,
            expansion_terms=[],
        )

    @staticmethod
    def _normalize_text(text: str) -> str:
        text = text.strip().lower()
        text = re.sub(r"\s+", " ", text)
        return text

    @staticmethod
    def _matches_any(text: str, patterns: tuple[str, ...]) -> bool:
        return any(re.search(pattern, text, flags=re.IGNORECASE) for pattern in patterns)


# =============================================================================
# Chat resolution
# =============================================================================

class ChatResolution(BaseModel):
    chat_id: int
    source: str  # "name_match" | "context_chat"

class ChatResolver:
    async def resolve(
        self,
        *,
        name: Optional[str],
        context_chat_id: Optional[int],
    ) -> ChatResolution:
        clean_name = (name or "").strip()

        if clean_name:
            matches = await find_chats_by_contact_name(clean_name, limit=10)
            if matches:
                return ChatResolution(chat_id=matches[0].chat_id, source="name_match")

        if context_chat_id is not None:
            return ChatResolution(chat_id=context_chat_id, source="context_chat")

        raise ChatResolutionError("No chat found for that person or context.")


# =============================================================================
# Retrieval policy
# =============================================================================

class RetrievalPolicy(BaseModel):
    mode: str  # "sql" | "lexical" | "vector" | "hybrid"
    limit: int
    context_window: int = Field(default=1, ge=0, le=5)
    top_k_context: int = Field(default=10, ge=0, le=50)

class RetrievalPolicyBuilder:
    def build(self, normalized_query: NormalizedQuery, requested_limit: int) -> RetrievalPolicy:
        token_count = len(normalized_query.normalized.split())

        if normalized_query.kind in {
            QueryKind.ASSIGNMENT,
            QueryKind.LINK,
            QueryKind.FILE,
            QueryKind.MEETING,
        }:
            return RetrievalPolicy(
                mode="hybrid",
                limit=max(requested_limit, 120),
                context_window=1,
                top_k_context=12,
            )

        if token_count <= 3:
            return RetrievalPolicy(
                mode="hybrid",
                limit=max(requested_limit, 80),
                context_window=1,
                top_k_context=8,
            )

        return RetrievalPolicy(
            mode="vector",
            limit=requested_limit,
            context_window=1,
            top_k_context=8,
        )


# =============================================================================
# Search service
# =============================================================================

class SearchHit(BaseModel):
    doc_id: str
    timestamp: Any
    content: str = ""
    score: Optional[float] = None
    metadata: dict[str, Any] = Field(default_factory=dict)

class SearchBundle(BaseModel):
    primary_hits: list[SearchHit]
    context_hits: list[SearchHit]

    @property
    def all_hits(self) -> list[SearchHit]:
        merged: dict[str, SearchHit] = {}

        for hit in self.primary_hits:
            merged[hit.doc_id] = hit

        for hit in self.context_hits:
            merged.setdefault(hit.doc_id, hit)

        return sorted(merged.values(), key=lambda item: item.timestamp)

class SearchFromPersonService:
    def __init__(
        self,
        *,
        query_normalizer: QueryNormalizer,
        chat_resolver: ChatResolver,
        retrieval_policy_builder: RetrievalPolicyBuilder,
    ) -> None:
        self.query_normalizer = query_normalizer
        self.chat_resolver = chat_resolver
        self.retrieval_policy_builder = retrieval_policy_builder

    async def execute(
        self,
        args: SearchFromPersonArgs,
        ctx: SessionToolContext,
    ) -> ToolResult:
        normalized_query = self.query_normalizer.normalize(args.query)
        chat_resolution = await self.chat_resolver.resolve(
            name=args.name,
            context_chat_id=ctx.context_chat_id,
        )
        policy = self.retrieval_policy_builder.build(normalized_query, args.limit)

        logger.info(
            "Session %s: search_from_person query=%r normalized=%r kind=%s chat_id=%s mode=%s",
            ctx.session_id,
            args.query,
            normalized_query.retrieval_query,
            normalized_query.kind.value,
            chat_resolution.chat_id,
            policy.mode,
        )

        bundle = await self._retrieve(
            chat_id=chat_resolution.chat_id,
            normalized_query=normalized_query,
            policy=policy,
        )

        if not bundle.primary_hits:
            return ToolResult(
                result="No messages found from that person.",
                metadata={
                    "tool": "search_from_person",
                    "chat_id": chat_resolution.chat_id,
                    "query_kind": normalized_query.kind.value,
                    "retrieval_mode": policy.mode,
                    "match_count": 0,
                },
            )

        # In your codebase retrieved_documents from retrieve_documents or get_surrounding_messages
        # are typical models that can be converted back, but here we construct raw objects to pass to compact_context?
        # Let's verify what `compact_context` expects. It expects instances with .doc_id, .timestamp, .content, etc.
        # So SearchHit itself acts as the object. Let's pass `bundle.all_hits` directly.
        context_pack = compact_context(bundle.all_hits)
        answer = synthesize_answer(context_pack, normalized_query.original)

        return ToolResult(
            result=answer,
            metadata={
                "tool": "search_from_person",
                "chat_id": chat_resolution.chat_id,
                "query_kind": normalized_query.kind.value,
                "retrieval_mode": policy.mode,
                "match_count": len(bundle.primary_hits),
                "doc_ids": [hit.doc_id for hit in bundle.primary_hits],
            },
        )

    async def _retrieve(
        self,
        *,
        chat_id: int,
        normalized_query: NormalizedQuery,
        policy: RetrievalPolicy,
    ) -> SearchBundle:
        plan = RetrievalPlan(
            modes=[RetrievalMode(mode=policy.mode, reason="Explicitly chosen by RetrievalPolicyBuilder")],
            target_chat_ids=[chat_id] if chat_id else None,
            query=normalized_query.retrieval_query,
            limit=policy.limit,
        )

        try:
            collection = _get_chroma_collection()
        except Exception as e:
            logger.warning(f"Failed to get Chroma collection in search_from_person: {e}")
            collection = None

        docs = await retrieve_documents(plan, chroma_collection=collection)
        if not docs:
            return SearchBundle(primary_hits=[], context_hits=[])

        primary_hits = [self._to_hit(doc) for doc in docs]

        seen_ids = {hit.doc_id for hit in primary_hits}
        context_hits: list[SearchHit] = []

        for hit in primary_hits[: policy.top_k_context]:
            surrounding_docs = await get_surrounding_messages(
                chat_id=chat_id,
                doc_id=hit.doc_id,
                window=policy.context_window,
            )
            for doc in surrounding_docs:
                candidate = self._to_hit(doc)
                if candidate.doc_id not in seen_ids:
                    seen_ids.add(candidate.doc_id)
                    context_hits.append(candidate)

        return SearchBundle(
            primary_hits=primary_hits,
            context_hits=context_hits,
        )

    @staticmethod
    def _to_hit(doc: Any) -> SearchHit:
        return SearchHit(
            doc_id=getattr(doc, "doc_id", str(id(doc))),
            timestamp=getattr(doc, "timestamp", 0),
            content=getattr(doc, "content", ""),
            score=getattr(doc, "score", None),
            metadata=getattr(doc, "metadata", {}) or {},
        )


# =============================================================================
# Helper functions for other tools
# =============================================================================

def _build_referenced_message(msg: dict, require_media: bool = False) -> Optional[dict]:
    meta = parse_message_metadata(msg.get("metadata"))
    chat_id = meta.get("chat_id")
    if chat_id is None:
        return None
    media_url = get_media_filename(meta)
    if require_media and not media_url:
        return None
    media_obj = meta.get("media") or {}
    return {
        "chat_id": int(chat_id),
        "doc_id": str(msg.get("doc_id", "")),
        "content": (msg.get("content") or "").strip() if msg.get("content") else "",
        "media_url": media_url,
        "media_type": media_obj.get("type") if media_obj else None,
        "description": media_obj.get("description") if media_obj else None,
        "sender_name": meta.get("sender_name"),
    }

def _msg_dict(msg) -> dict:
    return msg.model_dump() if hasattr(msg, "model_dump") else msg

def _compute_since_timestamp(
    time_amount: int,
    time_unit: Literal["minutes", "hours", "days", "weeks", "months"],
) -> str:
    now = datetime.utcnow()
    if time_unit == "minutes":
        delta = timedelta(minutes=time_amount)
    elif time_unit == "hours":
        delta = timedelta(hours=time_amount)
    elif time_unit == "days":
        delta = timedelta(days=time_amount)
    elif time_unit == "weeks":
        delta = timedelta(weeks=time_amount)
    elif time_unit == "months":
        delta = timedelta(days=time_amount * 30)
    else:
        delta = timedelta(days=1)
    threshold = now - delta
    return threshold.isoformat()

def _get_chroma_collection():
    if Config.CHROMA_DB_IP and Config.CHROMA_DB_IP != "localhost":
        client = chromadb.HttpClient(
            host=Config.CHROMA_DB_IP, port=int(Config.CHROMA_DB_PORT)
        )
    else:
        client = chromadb.PersistentClient(path=Config.CHROMA_DB_PATH)
    return client.get_or_create_collection("summagram_chats")


async def _tool_get_last_messages(
    name: Optional[str],
    limit: int,
    context: SessionToolContext,
    since_timestamp: Optional[str] = None,
) -> ToolResult:
    if name and name.strip():
        matches = await find_chats_by_contact_name(name.strip(), limit=10)
        if not matches:
            return ToolResult("No chat found for that name.", None)
        chat_id = matches[0].chat_id
        history = await get_chat_history(
            chat_id, limit=limit, offset=0, since_timestamp=since_timestamp
        )
        logger.info(
            f"Session {context.session_id}: get_last_messages(name={name!r}): chat_id={chat_id}, {len(history)} msgs"
        )
    elif context.context_chat_id is not None:
        history = await get_chat_history(
            context.context_chat_id,
            limit=limit,
            offset=0,
            since_timestamp=since_timestamp,
        )
        logger.info(
            f"Session {context.session_id}: get_last_messages(linked chat): {len(history)} msgs"
        )
    else:
        history = await get_last_messages_any_chat(
            limit=limit, since_timestamp=since_timestamp
        )
        logger.info(
            f"Session {context.session_id}: get_last_messages(any chat): {len(history)} msgs"
        )

    formatted = format_chat_history(history)
    result = formatted or "No messages found."

    ref_meta = None
    if limit == 1 and len(history) == 1:
        ref_msg = _build_referenced_message(_msg_dict(history[0]), require_media=False)
        if ref_msg:
            ref_meta = {"referenced_message": ref_msg}

    return ToolResult(result, ref_meta)


# =============================================================================
# Args models for other tools
# =============================================================================

class GetLastMessagesArgs(ToolArgsModel):
    name: Optional[str] = None
    query: Optional[str] = None
    limit: int = Field(default=50, ge=1, le=500)
    time_amount: Optional[int] = None
    time_unit: Optional[Literal["minutes", "hours", "days", "weeks", "months"]] = None

class SearchChatHistoryArgs(ToolArgsModel):
    query: Optional[str] = None
    name: Optional[str] = None
    limit: int = Field(default=20, ge=1, le=500)

class SearchFilesAndMediaArgs(ToolArgsModel):
    query: Optional[str] = None
    name: Optional[str] = None
    limit: int = Field(default=20, ge=1, le=500)

class GetUnreadMessagesArgs(ToolArgsModel):
    name: Optional[str] = None
    limit: int = Field(default=50, ge=1, le=500)


# =============================================================================
# Existing handlers
# =============================================================================

async def _handle_get_last_messages(
    args: GetLastMessagesArgs,
    ctx: SessionToolContext,
) -> ToolResult:
    name = args.name or args.query
    if name is not None and not isinstance(name, str):
        name = None
    since_ts = None
    if args.time_amount is not None and args.time_unit is not None:
        try:
            since_ts = _compute_since_timestamp(args.time_amount, args.time_unit)
        except (ValueError, TypeError):
            pass
    return await _tool_get_last_messages(name, args.limit, ctx, since_timestamp=since_ts)


async def _handle_search_chat_history(
    args: SearchChatHistoryArgs,
    ctx: SessionToolContext,
) -> ToolResult:
    query = (args.query or "").strip()
    if not query:
        return ToolResult("Please provide search keywords.", None)

    chat_id: Optional[int] = None
    if args.name and isinstance(args.name, str) and args.name.strip():
        matches = await find_chats_by_contact_name(args.name.strip(), limit=10)
        if matches:
            chat_id = matches[0].chat_id

    plan = make_retrieval_plan(query, chat_id, limit=args.limit)
    try:
        collection = _get_chroma_collection()
    except Exception as e:
        logger.warning(f"Failed to get Chroma collection in search_chat_history: {e}")
        collection = None

    docs = await retrieve_documents(plan, chroma_collection=collection)

    if not docs:
        return ToolResult("No messages found matching your search.", None)

    context_pack = compact_context(docs)
    result = synthesize_answer(context_pack, query)

    logger.info(
        f"Session {ctx.session_id}: search_chat_history(query={query!r}): {len(docs)} results"
    )
    return ToolResult(result, None)


async def _handle_search_files_and_media(
    args: SearchFilesAndMediaArgs,
    ctx: SessionToolContext,
) -> ToolResult:
    query = (args.query or "").strip()
    if not query:
        return ToolResult(
            "Please provide a media search query (e.g. 'photo of cat', 'pdf', 'voice message').",
            None,
        )

    chat_id: Optional[int] = None
    if args.name and isinstance(args.name, str) and args.name.strip():
        matches = await find_chats_by_contact_name(args.name.strip(), limit=10)
        if matches:
            chat_id = matches[0].chat_id

    history = await search_documents_by_media(query, chat_id=chat_id, limit=args.limit)
    formatted = format_chat_history(history)
    result = formatted or "No media or files found matching your search."
    logger.info(
        f"Session {ctx.session_id}: search_files_and_media(query={query!r}): {len(history)} results"
    )
    return ToolResult(result, None)


async def _handle_get_unread_messages(
    args: GetUnreadMessagesArgs,
    ctx: SessionToolContext,
) -> ToolResult:
    chat_id: Optional[int] = None
    if args.name and isinstance(args.name, str) and args.name.strip():
        matches = await find_chats_by_contact_name(args.name.strip(), limit=10)
        if matches:
            chat_id = matches[0].chat_id
    elif ctx.context_chat_id is not None:
        chat_id = ctx.context_chat_id

    since_ts = _compute_since_timestamp(7, "days")

    history = await get_recent_messages_from_others(
        chat_id=chat_id,
        limit=args.limit,
        since_timestamp=since_ts,
    )
    formatted = format_chat_history(history)
    result = formatted or "No recent messages from others found."
    logger.info(
        f"Session {ctx.session_id}: get_unread_messages: {len(history)} results"
    )
    return ToolResult(result, None)


_search_from_person_service = SearchFromPersonService(
    query_normalizer=QueryNormalizer(),
    chat_resolver=ChatResolver(),
    retrieval_policy_builder=RetrievalPolicyBuilder(),
)


async def _handle_search_from_person(
    args: SearchFromPersonArgs,
    ctx: SessionToolContext,
) -> ToolResult:
    return await _search_from_person_service.execute(args, ctx)


# =============================================================================
# Tool registry and dispatcher
# =============================================================================

_TOOL_REGISTRY: dict[str, ToolSpec[Any]] = {
    "get_last_messages": ToolSpec(
        args_model=GetLastMessagesArgs,
        handler=_handle_get_last_messages,
    ),
    "search_chat_history": ToolSpec(
        args_model=SearchChatHistoryArgs,
        handler=_handle_search_chat_history,
    ),
    "search_files_and_media": ToolSpec(
        args_model=SearchFilesAndMediaArgs,
        handler=_handle_search_files_and_media,
    ),
    "get_unread_messages": ToolSpec(
        args_model=GetUnreadMessagesArgs,
        handler=_handle_get_unread_messages,
    ),
    "search_from_person": ToolSpec(
        args_model=SearchFromPersonArgs,
        handler=_handle_search_from_person,
    ),
}


async def run_tool(
    name: str, arguments: dict[str, Any], context: SessionToolContext
) -> ToolResult:
    """
    Dispatch a tool by name; returns ToolResult(result, metadata).
    Metadata may include referenced_message when the tool returns a single message with media.
    """
    logger.info(f"LLM Tool Call: {name}({arguments})")

    spec = _TOOL_REGISTRY.get(name)
    if spec is None:
        return ToolResult(result=f"Error: Unknown tool {name}", metadata=None)

    try:
        parsed_args = spec.args_model.model_validate(arguments)
    except ValidationError as e:
        logger.warning(f"Tool {name} validation failed: {e}")
        return ToolResult(
            result=f"Error: Invalid arguments for tool {name}",
            metadata={
                "tool": name,
                "validation_errors": e.errors(),
            },
        )

    try:
        return await spec.handler(parsed_args, context)
    except ChatResolutionError as e:
        logger.info(f"Tool {name} chat resolution failed: {e}")
        return ToolResult(result="No chat found for that person.", metadata={"tool": name})
    except Exception as e:
        logger.exception(f"Tool {name} failed")
        return ToolResult(
            result=f"Error: Tool {name} failed",
            metadata={"tool": name},
        )
