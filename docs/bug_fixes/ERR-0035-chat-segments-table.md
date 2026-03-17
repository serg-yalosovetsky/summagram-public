# ERR-0034: chat_segments table not found

## What was broken (symptoms)
When analyzing a Telegram chat, an error occurred: `relation "chat_segments" does not exist`. The backend failed to execute `DELETE FROM chat_segments WHERE chat_id = $1`.

## Investigation notes (facts, logs, repro steps)
The error indicates that the `chat_segments` table was missing from the PostgreSQL database. We inspected the migrations in `etl/migrations/` and found that the migration `etl_2026_03_06t14_33_01_069504.py` creating this table exists but was never applied.

## Hypotheses considered (and rejected)
- The ORM mapping might be incorrect: Rejected, table definition exists.
- The `postgres` container might be down: Rejected, the logs showed a postgres error.

## Experiments tried (what worked / what didn’t)
- N/A.

## Final fix + why it works
Run `piccolo migrations forwards etl` inside the `etl` container to apply pending database migrations. This ensures the schema in PostgreSQL is up to date with the ORM models.

## Verification (tests, commands, expected output)
- Ran `docker compose exec -T etl piccolo migrations forwards etl`
- Expected output indicates migrations applied successfully without errors.

## Status
resolved
