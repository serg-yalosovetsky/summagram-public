"""
Factory function that wires up a SessionPipeline with all concrete implementations.
Called once at startup (or lazily) and cached.

Feature flags from Config:
  NLP_PIPELINE_ENABLED     — master switch (default False)
  NLP_LANGUK_NER_ENABLED   — enable lang-uk transformer NER (default False)
  NLP_RETURN_TRACE         — attach full trace to result (default False)
"""

from __future__ import annotations

from backend.session_pipeline.implementations.normalizer_default import (
    DefaultTextNormalizer,
)
from backend.session_pipeline.implementations.candidate_extractor_composite import (
    CompositeCandidateExtractor,
)
from backend.session_pipeline.implementations.entity_resolver_default import (
    DefaultEntityResolver,
)
from backend.session_pipeline.implementations.time_parser_dateparser import (
    DateparserTimeParser,
)
from backend.session_pipeline.implementations.intent_classifier_llm import (
    LLMIntentClassifier,
)
from backend.session_pipeline.services.pipeline import SessionPipeline

_pipeline_instance: SessionPipeline | None = None


def get_pipeline() -> SessionPipeline:
    """Return the singleton SessionPipeline; create it on first call."""
    global _pipeline_instance
    if _pipeline_instance is not None:
        return _pipeline_instance

    from shared.config import Config  # noqa: PLC0415

    enable_languk: bool = getattr(Config, "NLP_LANGUK_NER_ENABLED", False)
    return_trace: bool = getattr(Config, "NLP_RETURN_TRACE", False)

    _pipeline_instance = SessionPipeline(
        normalizer=DefaultTextNormalizer(),
        candidate_extractor=CompositeCandidateExtractor(
            enable_natasha=True,
            enable_languk=enable_languk,
        ),
        entity_resolver=DefaultEntityResolver(),
        time_parser=DateparserTimeParser(),
        intent_classifier=LLMIntentClassifier(),
        return_trace=return_trace,
    )
    return _pipeline_instance
