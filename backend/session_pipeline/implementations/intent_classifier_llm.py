"""
Stage 4: Slim LLM intent classifier.
Receives pre-resolved entities and time range as structured context.
Only classifies query_type + extracts topical search_query (keywords only).
Does NOT extract person names — that is done by entity_resolver.
"""

from __future__ import annotations

from loguru import logger

from backend.prompts import Prompts
from backend.session_pipeline.models.common import QueryType
from backend.session_pipeline.models.stage0_normalize import NormalizedText
from backend.session_pipeline.models.stage2_entities import EntityResolutionResult
from backend.session_pipeline.models.stage3_time import TimeParseResult
from backend.session_pipeline.models.stage4_intent import QueryIntent


class LLMIntentClassifier:
    """
    Calls generate_json with a slim prompt that only needs to classify query_type.
    Falls back to last_any on parse error (fail-safe, logs warning).
    """

    async def classify(
        self,
        text: NormalizedText,
        entities: EntityResolutionResult,
        time_range: TimeParseResult,
    ) -> QueryIntent:
        from backend.sglang_client import generate_json  # noqa: PLC0415

        person_name = (
            entities.primary_person.normalized_text if entities.primary_person else None
        )
        time_info = (
            f"time: {time_range.primary_range.raw_text!r}"
            if time_range.primary_range
            else "no time range"
        )

        user_prompt = (
            f"User text: {text.raw_text!r}\n"
            f"Resolved person: {person_name!r}\n"
            f"Time: {time_info}\n"
            f"Language: {text.detected_language.value}\n"
            "\nClassify. Output JSON only."
        )

        schema = QueryIntent.model_json_schema()
        try:
            raw = await generate_json(
                prompt=user_prompt,
                json_schema=schema,
                system_prompt=Prompts.INTENT_SLIM,
                max_tokens=200,
                temperature=0.0,
            )
            logger.debug(f"[NLP intent] raw LLM output: {raw}")
            intent = QueryIntent.model_validate_json(raw)
            # Guard: person name must not leak into search_query
            if intent.search_query and person_name:
                if person_name.lower() in (intent.search_query or "").lower():
                    intent.search_query = (
                        intent.search_query.replace(person_name, "").strip() or None
                    )
                    intent.reasoning_notes.append(
                        "stripped person name from search_query"
                    )
            return intent
        except Exception as exc:
            logger.warning(f"[NLP intent] classifier failed, falling back: {exc}")
            return QueryIntent(
                query_type=QueryType.LAST_ANY,
                reasoning_notes=[f"fallback due to error: {exc}"],
            )
