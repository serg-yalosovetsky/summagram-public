# Bug Analysis: Excessive Polling of Job Status endpoints

## Symptoms
The backend and ETL service logs show a continuous and rapid stream of GET requests hitting `/jobs/{job_id}` (on the ETL service) and `/tasks/status/{job_id}` (on the backend service) while a job is in progress.

## Investigation Notes
1. **Frontend (`v0/components/app-shell/app-context.tsx`)**: There is an effect that sets up a `setInterval` to poll `fetchJobStatus(activeJobId)` every 1.5 seconds.
2. **Frontend (`v0/components/views/telegram-import-dialog.tsx`)**: In `startSync()`, it submits the job and then calls its own local `pollStatus(job_id)`. This function uses `setTimeout(() => pollStatus(id), 1500)` recursively, creating a second concurrent polling loop for the same endpoint (`/etl/jobs/{job_id}`).
3. **ETL Service (`etl/manager.py`)**: Inside `_seal_and_wait(job_id)`, there is a `while True:` loop checking `/tasks/status/{job_id}` every `TASK_POLL_INTERVAL` (2.0 seconds).
   
As a result:
- The frontend makes 2 requests to `/etl/jobs/(id)` every 1.5 seconds (or more if the dialog is re-opened without clearing state).
- The ETL service polls the backend every 2.0 seconds.

## Hypotheses Considered
The excessive logging and network traffic are caused by redundant polling logic in the React frontend, where global state (`app-context.tsx`) and local component state (`telegram-import-dialog.tsx`) both attempt to manage the synchronization status of the same job independently without coordination.

## Final Fix & Verification
- Added `/tasks/status/stream/{job_id}` SSE endpoint to `backend/routes.py`.
- Updated `etl/manager.py` to use `httpx.stream` to read the backend SSE instead of polling.
- Added `/jobs/stream/{job_id}` SSE endpoint to `etl/router.py`.
- Replaced `setInterval` polling in `v0/components/app-shell/app-context.tsx` with a persistent `EventSource` subscription.
- Replaced recursive `setTimeout` polling in `v0/components/views/telegram-import-dialog.tsx` with the same `EventSource` subscription hook.
- Verification: Running a sync job now shows a single pair of long-lived GET requests instead of hundreds of repeated ones.

## Status
resolved
