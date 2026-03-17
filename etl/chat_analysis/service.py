"""
Main orchestration service for segment-based chat analysis.

Pipeline:
  1. Fetch messages from raw_documents (source of truth)
  2. Build segments (time-gap / token-budget / count-based)
  3. Per-segment LLM extraction → save to chat_segment_analysis
  4. Aggregate chat-level summary → update chats table
  5. Normalize event candidates → upsert unified_events
  6. Per-participant contact profile → update contacts table
"""
from __future__ import annotations

from collections import defaultdict
from typing import Any

from loguru import logger

from etl.chat_analysis.llm_client import ChatAnalysisLlmClient
from etl.chat_analysis.models import (
    ChatAggregateAnalysis,
    ChatParticipant,
    ChatSegmentAnalysis,
    ContactAggregateAnalysis,
)
from etl.chat_analysis.prompts import (
    build_chat_aggregate_prompt,
    build_contact_aggregate_prompt,
    build_segment_prompt,
)
from etl.chat_analysis.segmenter import build_chat_segments
from etl.chat_analysis.token_budget import BudgetConfig, TokenBudget


# Default budget — conservative for 8192-context models
DEFAULT_BUDGET = TokenBudget(BudgetConfig(
    max_context_tokens=8192,
    output_tokens=600,
    safety_margin=300,
))


def _normalize_event_candidates(
    segment_results: list[ChatSegmentAnalysis],
) -> list[dict[str, Any]]:
    """Deduplicate event candidates across segments by (title, start_time) key."""
    normalized: list[dict[str, Any]] = []
    seen: set[tuple[str, str | None]] = set()

    for segment in segment_results:
        for event in segment.events:
            key = (
                event.title.strip().lower(),
                event.start_time.isoformat() if event.start_time else None,
            )
            if key in seen:
                continue
            seen.add(key)
            normalized.append(event.model_dump(mode="json"))

    return normalized


def _compute_contact_summary_deterministic(
    contact: ChatParticipant,
    segment_results: list[ChatSegmentAnalysis],
) -> ContactAggregateAnalysis:
    """
    Fallback deterministic contact profile built from segment data.

    Used when LLM call for contact is impractical (too few segments, no
    relevant data, or budget exceeded). This is always a valid starting point.
    """
    topic_counter: dict[str, int] = defaultdict(int)
    interest_counter: dict[str, int] = defaultdict(int)
    relation_votes: dict[str, float] = defaultdict(float)

    for seg in segment_results:
        mentioned = any(
            p.display_name == contact.display_name or p.source_id == contact.source_id
            for p in seg.people
        )
        if not mentioned:
            continue
        for t in seg.topics:
            topic_counter[t.label] += 1
        for i in seg.interests:
            interest_counter[i.label] += 1
        for r in seg.relationship_signals:
            if contact.display_name in (r.from_person, r.to_person):
                relation_votes[r.relation_type] += r.weight

    recurring_topics = [
        k for k, _ in sorted(topic_counter.items(), key=lambda x: x[1], reverse=True)[:8]
    ]
    interests = [
        k for k, _ in sorted(interest_counter.items(), key=lambda x: x[1], reverse=True)[:8]
    ]
    relation_to_me = (
        max(relation_votes.items(), key=lambda x: x[1])[0]
        if relation_votes
        else "unknown"
    )

    desc_parts: list[str] = []
    if recurring_topics:
        desc_parts.append(f"Теми спілкування: {', '.join(recurring_topics[:5])}.")
    if interests:
        desc_parts.append(f"Інтереси: {', '.join(interests[:5])}.")
    description = " ".join(desc_parts) or "Недостатньо даних для профілю."

    return ContactAggregateAnalysis(
        contact_id=contact.source_id,
        display_name=contact.display_name,
        description=description,
        interests=interests,
        relation_to_me=relation_to_me,  # type: ignore[arg-type]
        recurring_topics=recurring_topics,
        confidence=0.6 if recurring_topics or interests else 0.2,
    )


async def analyze_chat(
    *,
    chat_id: int,
    llm_client: ChatAnalysisLlmClient,
    budget: TokenBudget = DEFAULT_BUDGET,
) -> ChatAggregateAnalysis:
    """
    Run the full segment-based chat analysis pipeline for one chat.

    Must be called after raw_documents and chat_members are already populated
    for this chat (i.e., after the ETL fetch phase completes).

    Args:
        chat_id: The chat source_id to analyze.
        llm_client: Configured LLM client (wraps /generate endpoint).
        budget: Token budget configuration.

    Returns:
        ChatAggregateAnalysis persisted to the chats table.
    """
    # Import here to avoid circular imports at module load time
    # (etl.chat_analysis.service ← etl.db.chat_analysis ← etl.db.core)
    from etl.db.chat_analysis import (  # local import: circular avoidance
        get_chat_members_with_contacts,
        get_raw_docs_for_chat,
        replace_chat_segments,
        save_segment_analysis,
    )
    from etl.db.chats import get_chat, save_chat, save_contact  # local import: circular avoidance

    # ---- 0. Verify chat exists ----
    chat = await get_chat(chat_id)
    if chat is None:
        raise ValueError(f"Chat {chat_id} not found in DB.")

    title = chat.title or ""
    is_private = bool(chat.is_private)

    # ---- 1. Fetch messages ----
    messages = await get_raw_docs_for_chat(chat_id)
    if not messages:
        logger.warning("analyze_chat: no messages for chat {}", chat_id)
        result = ChatAggregateAnalysis(
            chat_id=chat_id,
            title=title,
            description="Немає індексованих повідомлень.",
            tags=[],
            importance_score=0.0,
            confidence=0.1,
        )
        await save_chat({
            "source_id": chat_id,
            "description": result.description,
            "tags": "[]",
        })
        return result

    participants = await get_chat_members_with_contacts(chat_id)

    # ---- 2. Segment ----
    segments = build_chat_segments(
        chat_id=chat_id,
        messages=messages,
        budget=budget,
        max_msgs=40,
        max_input_tokens=min(2200, budget.max_input_tokens),
        time_gap_hours=18,
        min_msgs=8,
    )

    segment_id_to_db_id = await replace_chat_segments(chat_id, segments)

    # ---- 3. Analyze each segment ----
    segment_results: list[ChatSegmentAnalysis] = []
    for segment in segments:
        prompt = build_segment_prompt(
            title=title,
            is_private=is_private,
            participants=participants,
            segment=segment,
        )

        if not budget.fits_chat(prompt):
            logger.warning(
                "analyze_chat: segment {} for chat {} exceeds budget ({} tokens), skipping.",
                segment.segment_id,
                chat_id,
                budget.count_chat_tokens(prompt),
            )
            continue

        try:
            analysis = await llm_client.generate_json(
                messages=prompt,
                response_model=ChatSegmentAnalysis,
                max_tokens=llm_client.segment_output_tokens,
            )
        except Exception as exc:
            logger.error(
                "analyze_chat: segment {} analysis failed: {}",
                segment.segment_id,
                exc,
            )
            continue

        segment_results.append(analysis)

        db_id = segment_id_to_db_id.get(segment.segment_id)
        if db_id is not None:
            await save_segment_analysis(
                segment_db_id=db_id,
                model_name=llm_client.model_name,
                model_version=llm_client.model_version,
                analysis=analysis,
            )

    if not segment_results:
        logger.warning("analyze_chat: no segment results for chat {}", chat_id)
        result = ChatAggregateAnalysis(
            chat_id=chat_id,
            title=title,
            description="Аналіз сегментів не дав результатів.",
            tags=[],
            importance_score=0.1,
            confidence=0.1,
        )
        await save_chat({
            "source_id": chat_id,
            "description": result.description,
            "tags": "[]",
        })
        return result

    # ---- 4. Aggregate chat ----
    aggregate_prompt = build_chat_aggregate_prompt(
        chat_id=chat_id,
        title=title,
        is_private=is_private,
        segment_results=segment_results,
    )

    try:
        aggregate = await llm_client.generate_json(
            messages=aggregate_prompt,
            response_model=ChatAggregateAnalysis,
            max_tokens=llm_client.aggregate_output_tokens,
        )
    except Exception as exc:
        logger.error("analyze_chat: aggregate generation failed for chat {}: {}", chat_id, exc)
        # Fallback: make a minimal aggregate from segment data
        import json as _json
        from collections import Counter as _Counter
        tc: _Counter[str] = _Counter()
        for s in segment_results:
            for t in s.topics:
                tc[t.label] += 1
        dominant = [k for k, _ in tc.most_common(8)]
        aggregate = ChatAggregateAnalysis(
            chat_id=chat_id,
            title=title,
            description=" ".join(s.summary for s in segment_results[:3]),
            tags=dominant[:5],
            dominant_topics=dominant,
            detected_event_count=sum(len(s.events) for s in segment_results),
            importance_score=max((s.importance_score for s in segment_results), default=0.0),
            confidence=0.4,
        )

    import json as _json
    await save_chat({
        "source_id": chat_id,
        "description": aggregate.description,
        "tags": _json.dumps(aggregate.tags, ensure_ascii=False),
    })

    # ---- 5. Normalize events → unified_events ----
    normalized_events = _normalize_event_candidates(segment_results)
    if normalized_events:
        from etl.db.chat_analysis import upsert_unified_events  # local import: circular avoidance
        await upsert_unified_events(chat_id, normalized_events)

    # ---- 6. Update contact profiles ----
    for participant in participants:
        if participant.is_self:
            continue

        # Deterministic fallback (no extra LLM call per contact for now)
        contact_profile = _compute_contact_summary_deterministic(
            participant, segment_results
        )

        if contact_profile.interests or contact_profile.recurring_topics:
            await save_contact({
                "source_id": participant.source_id,
                "description": contact_profile.description,
                "interests": _json.dumps(contact_profile.interests, ensure_ascii=False),
            })
            logger.debug(
                "analyze_chat: updated contact {} profile",
                participant.display_name,
            )

    logger.info(
        "analyze_chat: done. chat={} segments={} events={}",
        chat_id,
        len(segment_results),
        len(normalized_events),
    )
    return aggregate
