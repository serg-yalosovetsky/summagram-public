# ERR-0032: PostgreSQL Integer Out of Range Error

## Symptoms
The ETL container crashes during metadata synchronization with the error:
`invalid input for query argument $1: -1002446873068 (value out of int32 range)`

## Investigation
- The error occurs when saving a chat or contact to the database.
- Telegram chat and user IDs are 64-bit integers (e.g. `-1002446873068` for supergroups).
- The Piccolo ORM models in `etl/tables.py` define `source_id` in `Chat` and `Contact`, and `chat_id`/`user_id` in `ChatMember` as `Integer` (which maps to `int32` in PostgreSQL).

## Hypotheses
- Changing the schema from `Integer` to `BigInt` for ID columns will fix the out-of-range error.

## Experiments
- Modified `etl/tables.py` to import and use `BigInt`.
- Created a new database migration to apply the column type changes.

## Final Fix
- Updated `etl/tables.py`: replaced `Integer` with `BigInt` for `Chat.source_id`, `Contact.source_id`, `ChatMember.chat_id`, `ChatMember.user_id`, and `SessionTable.context_chat_id` (since it also references chat IDs).
- Created migration using `piccolo migrations new --auto`.

## Verification
- Applied migrations.
- ETL successfully processed Telegram chats with large IDs without throwing out-of-range errors.

## Status
Resolved.
