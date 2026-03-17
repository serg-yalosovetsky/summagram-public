# ERR-0044: ModuleNotFoundError — rapidfuzz, dateparser, transformers missing in Docker

## Status: RESOLVED

## Symptoms

After ERR-0043 fix (pymorphy3 + natasha added), the next build still returns HTTP 500:

```
ERROR | LLM call failed, circuit-breaker activated:
  Pipeline stage 'entities' failed: No module named 'rapidfuzz'

ModuleNotFoundError: No module named 'rapidfuzz'
  File ".../entity_resolver_default.py", line 134, in _fuzzy_match
    from rapidfuzz import process, fuzz
```

## Root Cause

Full audit of `backend/session_pipeline/implementations/*.py` revealed **five** lazily-imported third-party packages, of which only `pymorphy3` and `natasha` were added in ERR-0043. The remaining three were still absent from `backend/requirements.txt`:

| Package | Used in | Purpose |
|---|---|---|
| `rapidfuzz` | `entity_resolver_default.py:134` | Fuzzy contact name matching |
| `dateparser` | `time_parser_dateparser.py:67` | NLP date/time parsing (RU/UK) |
| `transformers` | `candidate_extractor_languk.py:48` | Ukrainian NER (feature-flagged, default off) |

All three were present in the local `.venv` but absent from the Docker image requirements file.

## Fix

Added to `backend/requirements.txt` alongside pymorphy3/natasha:

```diff
 pymorphy3
 natasha
+rapidfuzz
+dateparser
+transformers  # lang-uk Ukrainian NER (feature-flagged, NLP_LANGUK_NER_ENABLED=false by default)
```

Note on `transformers`: it pulls in `torch` as a transitive dependency (~2GB CPU build). The lang-uk NER model is never downloaded unless `NLP_LANGUK_NER_ENABLED=true` — the package itself is still needed so the import doesn't fail if the flag is toggled on.

## Verification

```bash
docker compose build backend
docker compose up -d backend
# Send a session message — should return 200
# Logs should NOT contain any "No module named 'X'" errors
```

## Date
2026-03-07
