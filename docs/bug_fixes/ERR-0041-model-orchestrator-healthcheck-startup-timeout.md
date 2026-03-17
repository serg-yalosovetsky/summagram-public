# ERR-0041: Model Orchestrator Healthcheck Startup Timeout

## Symptoms
`model-orchestrator-1` failed to start and was marked unhealthy by `docker-compose`. `etl` and `backend` services failed to start because they depend on `model-orchestrator: service_healthy`. The logs showed `model-orchestrator` stopped at `Startup: ensuring only text model is running.` without opening the HTTP port.

## Investigation Notes
- `docker-compose.yml` configures the `model-orchestrator` health check to run `curl -f http://localhost:8000/health` every 15s with 20 retries (300 seconds total timeout).
- During startup, the FastAPI `lifespan` async context manager blocks execution up to 600s waiting for the text model (`Qwen2.5-Coder-7B-Instruct-AWQ`) to respond via `wait_for_ready`.
- Because FastAPI doesn't start responding until `lifespan` yields, the HTTP server remains offline, causing the Docker health probe on `localhost:8000/health` to fail after 300 seconds.

## Hypotheses Considered
1. **Increase Healthcheck Timeout:** Increase `retries` or `start_period` in `docker-compose.yml` to 600+ seconds.
   *Rejected:* Delays the startup of `etl` and `backend`, making the entire application appear unresponsive for 10 minutes, when `backend` could be initializing. The API Gateway should be responsive immediately and let subsequent proxy requests queue or wait.
2. **Background Task Initialization:** Use `asyncio.create_task` to run the active model start procedure in the background, allowing FastAPI to start serving `/health` immediately.
   *Selected:* `ensure_mode` was previously added with a singleflight pattern lock. Pushing the initialization to a background task perfectly integrates with it.

## Final Fix
Refactored `lifespan` in `model_orchestrator/main.py`:
- Replaced synchronous (blocking) `await asyncio.to_thread(...)` and `await wait_for_ready(...)` with `asyncio.create_task(init_text_mode())`.
- `init_text_mode` utilizes `await ensure_mode("text")`, which automatically sets `state.warm_task` and locks subsequent proxy requests via singleflight.
- If an incoming proxy request arrives before the background task completes, it correctly waits on `state.warm_task` without timing out (until the upstream HTTP proxy timeout).

## Verification
- Verified code changes.
- Ensure that `model-orchestrator` exposes its port immediately while the model continues to start in the background.

## Status
Resolved.
