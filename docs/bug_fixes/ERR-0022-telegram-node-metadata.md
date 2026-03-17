# ERR-0022: TelegramNodeMetadata Validation Errors

## Symptoms
The `etl-1` container fails during indexing with `6 validation errors for TelegramNodeMetadata` stemming from `Field required [type=missing]`. The error logs explicitly indicate that fields like `ts_unix_ms`, `ts_iso`, `content_norm`, `char_count`, `approx_token_count`, and `ingested_at_unix_ms` are missing.

## Investigation Notes
- Upon inspecting `etl/processing/telegram_etl.py` where `TelegramNodeMetadata` is instantiated in `transform_telegram_docs_to_nodes()`, the parameters passed did not match the current Pydantic schema defined in `etl/models.py`.
- Specifically, the code was passing `timestamp=doc.timestamp.isoformat()` instead of `ts_iso` and missed `ts_unix_ms` entirely. It also passed `reply_to_id` instead of `reply_to_message_id` and left out required content descriptors such as `content_norm`, `char_count`, and `approx_token_count`. Also missing was `ingested_at_unix_ms`.

## Hypotheses Considered
1. The `TelegramNodeMetadata` schema was updated recently with new fields, but the code in `transform_telegram_docs_to_nodes` was not synchronized with these changes. 

## Experiments Tried
- N/A (direct code review verified the mismatch).

## Final Fix
- Update `transform_telegram_docs_to_nodes` in `etl/processing/telegram_etl.py` to properly map properties from the `doc` object to the required `TelegramNodeMetadata` constructor fields:
  - Extract Unix timestamp `ts_unix_ms` and ISO time `ts_iso` from `doc.timestamp`.
  - Calculate `content_norm`, `char_count`, and `approx_token_count` from `safe_content`.
  - Provide `ingested_at_unix_ms` using `datetime.now(timezone.utc)`.
  - Map `meta.reply_to_msg_id` to `reply_to_message_id`.

## Verification
- Run tests involving `find_chats_by_contact_name` or run `pytest etl/tests/test_find_chat_by_name.py`.
- View `etl-1` logs to ensure indexing finishes without Pydantic validation errors.

## Status
resolved
