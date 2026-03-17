# ERR-0043: ModuleNotFoundError — pymorphy3 and natasha missing in Docker

## Status: RESOLVED

## Symptoms

Every `POST /session/<id>/messages` returns HTTP 500 with:

```
ERROR | backend.service:send_session_message:309 - LLM call failed, circuit-breaker activated:
  Pipeline stage 'entities' failed: No module named 'pymorphy3'

WARNING | backend.session_pipeline.implementations.candidate_extractor_natasha:extract:94
  - Natasha NER failed: No module named 'natasha'
```

Stack trace ends at:
```
File "/app/backend/session_pipeline/implementations/entity_resolver_default.py", line 38, in _init_morph
    import pymorphy3
ModuleNotFoundError: No module named 'pymorphy3'
```

## Root Cause

The session NLP pipeline (implemented in `backend/session_pipeline/`) requires two NLP libraries:
- `pymorphy3` — Russian/Ukrainian morphological analyser used in `entity_resolver_default.py` to lemmatize entity candidates
- `natasha` — Russian NER library used in `candidate_extractor_natasha.py`

Both were added to the local `.venv` during development but were **never added to `backend/requirements.txt`**, so the Docker image was built without them.

## Investigation

- `entity_resolver_default.py` lazily imports `pymorphy3` inside `_init_morph()` (called inside `asyncio.to_thread`) — fails at first NLP request
- `candidate_extractor_natasha.py` imports `natasha` and catches `ImportError`, downgrading to `WARNING` — but `pymorphy3` is a hard dependency in `entity_resolver_default.py`, so the pipeline always fails
- Local dev environment works because `.venv` has both packages; Docker build skips them

## Fix

Added both packages to `backend/requirements.txt`:

```diff
 num2words
+# NLP pipeline: Russian/Ukrainian morphology & NER
+pymorphy3
+natasha
 # New media processing libraries
```

## Verification

Rebuild the backend Docker image and confirm:
```bash
docker compose build backend
docker compose up backend -d
# Send a session message — should return 200 instead of 500
# Logs should NOT contain "No module named 'pymorphy3'"
```

## Date
2026-03-07
