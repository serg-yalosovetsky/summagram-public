from loguru import logger
from utils import timer, monitor_perf_async

from typing import List
from models import GenericDocument, DebtEvent, InterviewEvent, TopUpEvent
from security import wrap_user_data, mask_pii
from llm_setup import get_llm
from database import get_db
from llama_index.core.program import LLMTextCompletionProgram

with timer("extractor heavy imports (lazy)"):
    # We move the heavy imports into the functions
    pass

# Initialize LLM with OpenAILike for unrelated providers (OpenRouter)
# Removed global llm = get_llm() to fix slow startup

# Define extraction programs for each event type using generic completion
# This avoids "function calling" errors with non-OpenAI models

_programs = {}


def get_extraction_programs():
    if _programs:
        return _programs
    llm = get_llm()  # This triggers lazy setup if needed

    debt_program = LLMTextCompletionProgram.from_defaults(
        output_cls=DebtEvent,
        prompt_template_str="Extract debt information from the following text and output valid JSON:\n{text}",
        llm=llm,
    )

    interview_program = LLMTextCompletionProgram.from_defaults(
        output_cls=InterviewEvent,
        prompt_template_str="Extract interview details from the following text and output valid JSON:\n{text}",
        llm=llm,
    )

    topup_program = LLMTextCompletionProgram.from_defaults(
        output_cls=TopUpEvent,
        prompt_template_str="Extract service top-up reminders from the following text and output valid JSON:\n{text}",
        llm=llm,
    )

    _programs["debt"] = debt_program
    _programs["interview"] = interview_program
    _programs["topup"] = topup_program

    return _programs


async def check_idempotency(evidence_msg_id: str, source_id: str) -> bool:
    """Returns True if this message has already been processed into an event."""
    async with get_db() as db:
        async with db.execute(
            "SELECT 1 FROM unified_events WHERE source_id = ? AND evidence_msg_id = ?",
            (source_id, evidence_msg_id),
        ) as cursor:
            return await cursor.fetchone() is not None


@monitor_perf_async
async def extract_and_save(docs: List[GenericDocument]):
    """
    Main pipeline:
    1. Check Idempotency.
    2. Split long documents.
    3. Router (Conceptually) / Try-Extract loop.
    4. Save to DB.
    """
    async with get_db() as conn:
        for doc in docs:
            if await check_idempotency(doc.doc_id, doc.source_id):
                logger.debug(f"Skipping {doc.doc_id} (already processed)")
                continue

            # Security: Wrap content and Mask PII
            safe_text = wrap_user_data(mask_pii(doc.content))

            # Simple "Router": Attempt to extract all types.
            # In a real heavy system, we'd use a Classifier step first.
            # For simplicity/robustness here, we check keywords or just try.

            extracted_events = []

            # Heuristic to save tokens
            lower_content = doc.content.lower()

            # Lazy init programs
            programs = get_extraction_programs()

            try:
                if any(w in lower_content for w in ["owe", "debt", "borrow", "lent"]):
                    event = programs["debt"](text=safe_text)
                    extracted_events.append(("debt", event))
            except Exception as e:
                logger.error(f"Error extracting debt: {e}")

            try:
                if any(
                    w in lower_content
                    for w in ["interview", "call", "meeting", "hiring"]
                ):
                    event = programs["interview"](text=safe_text)
                    extracted_events.append(("interview", event))
            except Exception as e:
                logger.error(f"Error extracting interview: {e}")

            try:
                if any(
                    w in lower_content
                    for w in ["pay", "bill", "top up", "internet", "subscription"]
                ):
                    event = programs["topup"](text=safe_text)
                    extracted_events.append(("top_up_reminder", event))
            except Exception as e:
                logger.error(f"Error extracting topup: {e}")

            # Save results
            for event_type, event in extracted_events:
                logger.info(f"Found {event_type}: {event.title}")
                await conn.execute(
                    """
                    INSERT INTO unified_events 
                    (event_type, start_time, end_time, title, payload, evidence_msg_id, source_id)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        event_type,
                        event.start_time,
                        event.end_time,
                        event.title,
                        event.model_dump_json(),
                        doc.doc_id,
                        doc.source_id,
                    ),
                )

        await conn.commit()
