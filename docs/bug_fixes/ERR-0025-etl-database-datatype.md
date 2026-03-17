# ERR-0025: ETL Database Datatype and Backend Connectivity

## Symptoms
The ETL process failed with two errors:
1. `invalid input for query argument $1: -1002446873068 (expected str, got int)` in `etl.sources.telegram:fetch:870`.
2. `manager:_seal_and_wait:229 - Failed to seal job ... All connection attempts failed` and `manager:_enrich_from_results:262 - Failed to fetch task results: All connection attempts failed`.

## Investigation Notes
- **Bug 1**: The first error was traced to `get_chat_message_stats(chat_id, my_id)` and `get_chat_history(chat_id)` in `etl/database.py`, which compare integer arguments against `(metadata->>'chat_id')`. Since Postgres JSON extraction (`->>`) yields `TEXT`, `asyncpg` strictly checks that the python-supplied parameter is a string, crashing when it receives an `int`.
- **Bug 2**: The connection error happens when `manager.py` attempts to reach the backend to seal a job (`get_backend_url("")`). By checking the `etl` service configuration in `docker-compose.yml`, it became clear that `BACKEND_URL` was omitted for `etl`. Because `shared/config.py` defaults to `localhost:8003`, the ETL container tried to hit `localhost`, which inside the container corresponds to itself, failing to connect to the actual backend container.

## Hypotheses Considered
1. Casting parameters directly in `etl/database.py` allows Postgres and `asyncpg` to successfully compare equality against text-extracted JSON values.
2. Setting `BACKEND_URL=http://backend:8000` via `docker-compose.yml` ensures the `etl` container connects correctly over Docker's internal network.

## Experiments Tried
- Changed `chat_id` and `my_id` to `str()` when passing sequentially as parameters to execute functions matching `metadata->>'...'`.
- Added `BACKEND_URL=http://backend:8000` environment variable for `etl` in docker-compose.

## Final Fix
Both fixes were applied as stated and confirmed logic.

## Verification
- Code has been updated. Running `docker compose up -d etl` to pick up latest code format and environment files.

## Status
Resolved
