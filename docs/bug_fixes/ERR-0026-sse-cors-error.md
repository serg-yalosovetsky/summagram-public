# ERR-0026: Job status SSE connection errors

## What was broken (symptoms)
The console showed multiple errors when trying to connect to the Server-Sent Events (SSE) `/jobs/stream/{job_id}` endpoint in the ETL service, via frontend components like `TelegramImportDialog` and `AppContext`. The console logged `Job status SSE error` and `Job Status SSE connection error`.

## Investigation notes
We noticed that the frontend explicitly bypasses the Next.js proxy to connect to the ETL service via `http://localhost:8002` (port mapping defined in `docker-compose.yml`), making it a cross-origin request from `localhost:3000` to `localhost:8002`. At the same time, the `system/status/stream` SSE stream connecting to the `backend` service `http://localhost:8003` was not showing similar errors in logs.

## Hypotheses considered
- Missing CORS middleware in the ETL service: Since `backend` had CORS mapped explicitly (`CORSMiddleware`) while `etl` did not, cross-origin web requests like `EventSource` fail due to Same-Origin Policy.

## Final fix + why it works
Added `CORSMiddleware` to `etl/main.py` mirroring the implementation in `backend/main.py` utilizing the `Config.CORS_ORIGINS`.

## Verification
Started the ETL service, tested frontend UI elements that trigger `subscribeJobStatus` (App Shell / Dialogs), verified that the browser can successfully open an `EventSource` connection without CORS or disconnection errors.

## Status
resolved
