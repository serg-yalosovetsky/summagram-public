"""
Session agent using a 3-stage pipeline: intent -> fetch -> synthesize.
Uses SGLang (OpenAI-compatible API) for LLM calls.
Replaces the single FunctionAgent when LLM_SERVER_URL is set.
"""

from typing import Optional, List, Literal

from loguru import logger
from pydantic import BaseModel, Field

from shared.config import Config
from backend.prompts import Prompts
from backend.sglang_client import generate_json, generate_text_from_messages
from backend.session_tools import SessionToolContext, run_tool


class SessionIntent(BaseModel):
    """Structured output from Stage 1: user intent extraction."""

    person_name: Optional[str] = Field(
        default=None,
        description="Person or chat name (e.g. Lev, Alisa, Лев). Extract even short names. Set null only when no person/chat is mentioned.",
    )
    limit: int = Field(
        default=50,
        description="For recency queries ('last 5 messages from X', 'last 2 days') use the exact count or 50. For thematic/search queries (search_from_person, search_text, search_media) use 200 so older messages are not missed.",
    )
    time_amount: Optional[int] = Field(
        None,
        description="Numeric value for time period. E.g. '5 minutes' -> 5, '2 days' -> 2.",
    )
    time_unit: Optional[Literal["minutes", "hours", "days", "weeks", "months"]] = Field(
        None,
        description="Time unit. Null if no time specified.",
    )
    query_type: Literal[
        "last_any",
        "person_chat",
        "search_from_person",
        "search_text",
        "search_media",
        "summarize_unread",
    ] = Field(
        description=(
            "last_any=recent across all; "
            "person_chat=recent messages by name (recency); "
            "search_from_person=what someone asked/assigned/sent (thematic); "
            "search_text=keyword search; "
            "search_media=media/files; "
            "summarize_unread=unread only"
        )
    )
    search_query: Optional[str] = Field(
        None,
        description=(
            "Keywords for search when query_type is "
            "search_text, search_media, or search_from_person"
        ),
    )


def _session_context_str(context_chat_id: Optional[int]) -> str:
    """Build session context string for prompts."""
    if context_chat_id is None:
        return "No specific chat linked."
    return (
        f"This session is linked to Telegram Chat ID: {context_chat_id}. "
        "You can use get_last_messages to query it."
    )


def _build_intent_prompt(user_msg: str, chat_history: List[dict]) -> str:
    """Build the prompt for Stage 1 intent extraction."""
    parts = []
    if chat_history:
        for msg in chat_history[-5:]:  # Last 5 turns for context
            role = (
                msg.get("role", "user")
                if isinstance(msg, dict)
                else getattr(msg, "role", "user")
            )
            content = (
                msg.get("content", "")
                if isinstance(msg, dict)
                else getattr(msg, "content", "")
            )
            prefix = "User" if str(role).lower() == "user" else "Assistant"
            parts.append(f"{prefix}: {content}")
        parts.append("")
    parts.append(f"Current user message: {user_msg}")
    parts.append("\nExtract intent. Output valid JSON only.")
    return "\n".join(parts)


async def _stage1_intent(
    user_msg: str,
    chat_history: List[dict],
) -> SessionIntent:
    """Stage 1: Extract user intent (person_name, limit, query_type) via structured JSON."""
    prompt = _build_intent_prompt(user_msg, chat_history)
    system_prompt = Prompts.SESSION_INTENT_PROMPT
    schema = SessionIntent.model_json_schema()
    raw = await generate_json(
        prompt=prompt,
        json_schema=schema,
        system_prompt=system_prompt,
        max_tokens=256,
        temperature=0.1,
    )
    logger.info(f"Session intent 1: raw: {raw}")
    intent = SessionIntent.model_validate_json(raw)
    logger.info(
        f"Session intent: person_name={intent.person_name!r}, query_type={intent.query_type}, limit={intent.limit}"
    )
    return intent


async def _stage2_fetch(
    intent: SessionIntent,
    context: SessionToolContext,
    tool_metadata: dict,
    user_message: str = "",
) -> str:
    """Stage 2: Router. Dispatch to the appropriate tool based on intent."""
    name = intent.person_name
    base_params: dict = {"name": name, "limit": intent.limit}
    if intent.time_amount is not None and intent.time_unit is not None:
        base_params["time_amount"] = intent.time_amount
        base_params["time_unit"] = intent.time_unit

    if intent.query_type in ("last_any", "person_chat"):
        result = await run_tool("get_last_messages", base_params, context)
    elif intent.query_type == "search_from_person":
        result = await run_tool(
            "search_from_person",
            {
                **base_params,
                "query": intent.search_query or user_message,
            },
            context,
        )
    elif intent.query_type == "search_text":
        result = await run_tool(
            "search_chat_history",
            {**base_params, "query": intent.search_query or ""},
            context,
        )
    elif intent.query_type == "search_media":
        result = await run_tool(
            "search_files_and_media",
            {**base_params, "query": intent.search_query or ""},
            context,
        )
    elif intent.query_type == "summarize_unread":
        result = await run_tool("get_unread_messages", {"name": name}, context)
    else:
        result = await run_tool("get_last_messages", base_params, context)

    if result.metadata:
        tool_metadata.update(result.metadata)
    return result.result


def _build_synthesis_messages(
    user_msg: str,
    tool_result: str,
    session_context: str,
) -> List[dict]:
    """Build messages for Stage 3 synthesis. Enforces natural language and summarization."""
    system = Prompts.SESSION_SYNTHESIS_PROMPT.format(session_context=session_context)
    user_content = (
        f"User asked: {user_msg}\n\n"
        f"Fetched database raw data:\n{tool_result}\n\n"
        "INSTRUCTIONS:\n"
        "1. Analyze the raw data above and answer the user's question.\n"
        "2. Respond in natural, human-like conversational language.\n"
        "3. NEVER output raw JSON or code blocks. Convert all tags and metadata into a readable story/summary.\n"
        "4. Include Download URLs and Descriptions when the data contains media.\n"
        "5. CRITICAL: If the fetched data contains 3 or more messages, DO NOT list them one by one. "
        "Instead, provide a general, cohesive summary of the conversation or the requested messages."
    )
    return [
        {"role": "system", "content": system},
        {"role": "user", "content": user_content},
    ]


async def _stage3_synthesize(
    user_msg: str,
    tool_result: str,
    context_chat_id: Optional[int],
) -> str:
    """Stage 3: Compile tool result into final user-facing answer."""
    session_context = _session_context_str(context_chat_id)
    logger.info(
        f"Stage 3 synthesize: user_msg: {user_msg}, tool_result: {tool_result}, session_context: {session_context}"
    )
    messages = _build_synthesis_messages(user_msg, tool_result, session_context)
    content = await generate_text_from_messages(
        messages=messages,
        max_tokens=1024,
        temperature=0.3,
    )
    logger.info(f"Stage 3 synthesize: content: {content}")
    return (content or "").strip() or "I have nothing more to add."


async def run_session_agent(
    session_id: str,
    context_chat_id: Optional[int],
    message: str,
    chat_history: List[dict],
) -> tuple[str, Optional[dict]]:
    """
    Run the 3-stage session agent: intent -> fetch -> synthesize.
    Returns (assistant_content, referenced_message_dict or None).
    """
    assert Config.LLM_SERVER_URL, "LLM_SERVER_URL must be set (validated at startup)"

    tool_metadata: dict = {}
    ctx = SessionToolContext(session_id=session_id, context_chat_id=context_chat_id)

    logger.info(f"Session {session_id}: Stage 0-1 NLP/intent extraction")
    if getattr(Config, "NLP_PIPELINE_ENABLED", False):
        from backend.session_pipeline.models.pipeline import SessionPipelineRequest
        from backend.session_pipeline.services.factory import get_pipeline

        pipeline = get_pipeline()
        req = SessionPipelineRequest(
            session_id=session_id,
            user_text=message,
            linked_chat_id=context_chat_id,
            chat_history=chat_history,
        )
        p_res = await pipeline.run(req)

        # Adapt to SessionIntent for _stage2_fetch
        person_name = None
        if p_res.entities.primary_person:
            # Prefer DB matched name, fallback to normalized explicit name
            pm = p_res.entities.primary_person.matched
            if pm and pm.display_name:
                person_name = pm.display_name
            else:
                person_name = p_res.entities.primary_person.normalized_text

        time_amount = None
        time_unit = None
        if p_res.time_range.primary_range:
            time_amount = p_res.time_range.primary_range.amount
            time_unit = p_res.time_range.primary_range.unit

        intent = SessionIntent(
            person_name=person_name,
            limit=p_res.intent.limit,
            time_amount=time_amount,
            time_unit=time_unit, # type: ignore
            query_type=p_res.intent.query_type.value, # type: ignore
            search_query=p_res.intent.search_query,
        )
        logger.info(
            f"Session {session_id}: NLP Pipeline complete. Adapted intent: "
            f"person={intent.person_name!r} type={intent.query_type}"
        )
    else:
        logger.info(f"Session {session_id}: Stage 1 intent extraction (legacy LLM)")
        intent = await _stage1_intent(message, chat_history)
        logger.info(f"Session {session_id}: Stage 1 intent extraction complete")

    logger.info(
        f"Session {session_id}: Stage 2 fetch (name={intent.person_name!r}, limit={intent.limit})"
    )
    tool_result = await _stage2_fetch(intent, ctx, tool_metadata, user_message=message)
    logger.info(f"Session {session_id}: Stage 2 fetch complete")
    logger.info(f"Session {session_id}: Stage 3 synthesize")
    content = await _stage3_synthesize(message, tool_result, context_chat_id)
    logger.info(f"Session {session_id}: Stage 3 synthesize complete")
    referenced = tool_metadata.get("referenced_message")
    return content, referenced
