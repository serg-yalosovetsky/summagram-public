"""
Session NLP Pipeline orchestrator.
Runs stages 0–4 in order, wraps each stage exception with context,
returns a SessionPipelineResult for use in session_agent.
"""

from __future__ import annotations

from loguru import logger

from backend.session_pipeline.models.pipeline import (
    SessionPipelineRequest,
    SessionPipelineResult,
    SessionPipelineTrace,
)
from backend.session_pipeline.interfaces.protocols import (
    TextNormalizer,
    CandidateExtractor,
    EntityResolver,
    TimeParser,
    IntentClassifier,
)


class PipelineError(RuntimeError):
    """Raised when a pipeline stage fails unrecoverably."""

    def __init__(self, stage: str, cause: Exception) -> None:
        super().__init__(f"Pipeline stage '{stage}' failed: {cause}")
        self.stage = stage
        self.cause = cause


class SessionPipeline:
    """
    Orchestrates the 5 pre-LLM stages:
      0. normalize → 1. candidates → 2. entities → 3. time → 4. intent

    Usage:
        result = await pipeline.run(request)
        # result.entities.primary_person gives you the resolved contact
        # result.intent.query_type tells you what tool to call
    """

    def __init__(
        self,
        *,
        normalizer: TextNormalizer,
        candidate_extractor: CandidateExtractor,
        entity_resolver: EntityResolver,
        time_parser: TimeParser,
        intent_classifier: IntentClassifier,
        return_trace: bool = False,
    ) -> None:
        self._normalizer = normalizer
        self._candidate_extractor = candidate_extractor
        self._entity_resolver = entity_resolver
        self._time_parser = time_parser
        self._intent_classifier = intent_classifier
        self._return_trace = return_trace

    async def run(self, request: SessionPipelineRequest) -> SessionPipelineResult:
        session_id = request.session_id
        text = request.user_text

        # Stage 0 — Normalize
        try:
            normalized = await self._normalizer.normalize(text)
        except Exception as exc:
            raise PipelineError("normalize", exc) from exc
        logger.debug(f"[{session_id}] NLP stage 0: lang={normalized.detected_language}")

        # Stage 1 — Candidates
        try:
            candidates = await self._candidate_extractor.extract(normalized)
        except Exception as exc:
            raise PipelineError("candidates", exc) from exc
        logger.debug(
            f"[{session_id}] NLP stage 1: {len(candidates.candidates)} candidates"
        )

        # Stage 2 — Entity resolution
        try:
            entities = await self._entity_resolver.resolve(normalized, candidates)
        except Exception as exc:
            raise PipelineError("entities", exc) from exc
        if entities.primary_person:
            logger.info(
                f"[{session_id}] NLP stage 2: person={entities.primary_person.normalized_text!r}"
                f" matched={entities.primary_person.matched is not None}"
            )

        # Stage 3 — Time parsing
        try:
            time_range = await self._time_parser.parse(normalized)
        except Exception as exc:
            raise PipelineError("time", exc) from exc
        if time_range.primary_range:
            logger.debug(
                f"[{session_id}] NLP stage 3: time={time_range.primary_range.raw_text!r}"
            )

        # Stage 4 — Intent classification (LLM)
        try:
            intent = await self._intent_classifier.classify(
                normalized, entities, time_range
            )
        except Exception as exc:
            raise PipelineError("intent", exc) from exc
        logger.info(
            f"[{session_id}] NLP stage 4: query_type={intent.query_type}"
            f" search_query={intent.search_query!r}"
        )

        trace = None
        if self._return_trace:
            trace = SessionPipelineTrace(
                normalized=normalized,
                candidates=candidates,
                entities=entities,
                time_range=time_range,
                intent=intent,
            )

        return SessionPipelineResult(
            entities=entities,
            time_range=time_range,
            intent=intent,
            trace=trace,
        )
