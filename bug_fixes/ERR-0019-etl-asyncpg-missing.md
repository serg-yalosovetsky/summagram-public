# ERR-0019: ETL container fails with ModuleNotFoundError: No module named 'asyncpg'

## Symptoms
The `etl` container fails to start, crashing repeatedly with `ModuleNotFoundError: No module named 'asyncpg'` in `/app/etl/database.py`.

## Investigation Notes
- Container `etl-1` was restarting in a crash loop.
- Stack trace points to `import asyncpg` in `etl/database.py`.
- Checked `etl/requirements.txt` and verified that `asyncpg` was missing from the dependencies.
- This occurred after migrating the database from SQLite to PostgreSQL, where `asyncpg` was introduced to the ETL codebase but not added to the package requirements.

## Hypotheses Considered
1. **Missing dependency in requirements.txt (Accepted)**: The `asyncpg` package wasn't added to `etl/requirements.txt` during the PostgreSQL migration.

## Experiments Tried
- Viewed `etl/requirements.txt` which confirmed the package was missing.

## Final Fix
Added `asyncpg` to `./etl/requirements.txt` and rebuilt the ETL Docker container.

## Verification
- Run `docker compose build etl && docker compose up -d etl`
- Check logs `docker compose logs -f etl` to ensure it successfully starts up and listens on its port without the `asyncpg` error.

## Status
Resolved
