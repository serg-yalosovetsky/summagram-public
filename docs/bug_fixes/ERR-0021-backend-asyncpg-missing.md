# ERR-0021: Backend crashes with ModuleNotFoundError for asyncpg

## Symptoms
`backend-1` container fails to start with the following error:
```
backend-1             |   File "/app/backend/service.py", line 53, in <module>
backend-1             |     from etl.database import (
backend-1             |   File "/app/etl/database.py", line 1, in <module>
backend-1             |     import asyncpg
backend-1             | ModuleNotFoundError: No module named 'asyncpg'
```

## Investigation
The `backend` service imports `etl.database` in `backend/service.py`. The `etl/database.py` file imports `asyncpg`. While `asyncpg` was added to `etl/requirements.txt` in ERR-0019, it was not added to `backend/requirements.txt`. Since `backend` also needs to run code that imports `asyncpg`, it must be present in the backend's environment.

## Hypotheses
The `backend` Docker image lacks the `asyncpg` dependency.

## Experiments / Fix
Added `asyncpg` to `backend/requirements.txt`.

## Verification
Rebuild the `backend` Docker image and restart the container:
```bash
docker compose build backend
docker compose up -d backend
docker compose logs -f backend
```
Expect the container to start successfully and Uvicorn to run without `ModuleNotFoundError`.

## Status
Resolved.
