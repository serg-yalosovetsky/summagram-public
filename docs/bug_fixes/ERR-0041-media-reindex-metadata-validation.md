# ERR-0041: MediaReindexSource fails to validate Telegram metadata

## Symptoms
The `etl-1` service logs `10 validation errors for TelegramNodeMetadata` during media document reindexing. The error indicates missing fields such as `source_id`, `ts_unix_ms`, `author`, `original_text`, etc.

## Investigation
- `MediaReindexSource` fetches from `raw_documents`.
- The `metadata` stored in `raw_documents` uses the `TelegramMetadata` schema from initial ingestion, containing basic info like `sender_name`, `chat_id`, and optionally nested `media`.
- `MediaReindexSource._validate_metadata` tries to parse this dictionary using `TelegramNodeMetadata`, which is a downstream schema specifically designed for the ChromaDB vector database with enriched semantic information.
- Because the raw dictionary lacks these downstream fields, validation fails, and `metadata` is parsed as `None`, skipping media enqueueing entirely.

## Experiments & Hypotheses
- Hypothesis: Replacing `TelegramNodeMetadata` with `TelegramMetadata` in `_validate_metadata` will correctly parse the raw dictionary into the nested structure allowing access to `metadata.media.type` and `metadata.media.path`.

## Final Fix
- Modified `etl/sources/media_reindex_source.py`:
  - Imported `TelegramMetadata` instead of `TelegramNodeMetadata`.
  - Updated type annotations for `_validate_metadata` and `_enqueue_media_if_exists`.
  - Used `TelegramMetadata.model_validate` for unpacking.

## Verification
- Verified validation locally by running tests in `etl/tests`.
- Ensuring that standard properties such as `metadata.media` are safely accessible.

## Status
Resolved
