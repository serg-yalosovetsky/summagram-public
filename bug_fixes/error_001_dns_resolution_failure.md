# Error #1: Model container DNS resolution failure (502 Bad Gateway)

## Symptoms

```
model-orchestrator-1 | ERROR:orchestrator:Error proxying to http://summagram_new_sglang_text:30000/v1/chat/completions: [Errno -2] Name or service not known
model-orchestrator-1 | INFO: 172.20.0.5:42856 - "POST /v1/chat/completions HTTP/1.1" 502 Bad Gateway
```

Backend receives `openai.InternalServerError: Bad Gateway` and returns 500 to the frontend.

## Analysis

### Error chain

1. User sends message → backend `POST /session/{id}/messages`
2. Backend calls `run_session_agent()` → `_stage1_intent()` → `generate_json()`
3. `generate_json()` uses OpenAI client pointed at `http://model-orchestrator:8000/v1`
4. Model orchestrator route handler sets `request.state.proxy_url = http://summagram_new_sglang_text:30000/v1/chat/completions`
5. `ProxyMiddleware._stream_proxy()` opens httpx connection to that URL
6. DNS lookup for `summagram_new_sglang_text` fails — container not on network
7. Middleware catches exception, returns 502 Bad Gateway
8. Backend's OpenAI client raises `openai.InternalServerError`

### Root cause

The `sglang_text` service in `docker-compose.yml` uses `profiles: ["models"]`, meaning it does **NOT** start with `docker compose up`. The model orchestrator is supposed to manage this container via Docker SDK.

`ensure_container_running()` in `utils.py` tries to:
1. Find container by name (`summagram_new_sglang_text`)
2. Create it via Docker SDK if not found
3. Start it if not running

The problem: when the container is created via Docker SDK, it may **fail to start** (e.g., GPU not available, image not pulled, OOM) or **not get attached to the correct Docker network**, resulting in DNS being unresolvable from the orchestrator's container.

### Files involved

| File | Role |
|------|------|
| `model_orchestrator/config.py` | Defines `TEXT_URL = http://summagram_new_sglang_text:30000` |
| `model_orchestrator/utils.py` | `ensure_container_running()` — creates/starts containers |
| `model_orchestrator/services.py` | `wait_for_ready()` — polls but doesn't raise on timeout |
| `model_orchestrator/middleware.py` | `_stream_proxy()` — where DNS error actually occurs |
| `model_orchestrator/main.py` | Lifespan startup — calls `ensure_container_running` + `wait_for_ready` |
| `model_orchestrator/router.py` | Sets `proxy_url` to `cfg.url` |

## Proposal

1. **Add container status verification** after `ensure_container_running()` — check container is actually running and on the correct network
2. **Add retry logic** to `create_container()` — pull image if missing, retry on transient Docker errors
3. **Verify network attachment** — after creation, inspect container networks and confirm it's on the orchestrator's network
4. **Improve error propagation** — if container can't be started, surface the Docker error to the caller rather than silently continuing

## What worked

- Added post-start status verification: if `container.status != "running"`, raises `RuntimeError` with the actual status
- Added network logging: after successful start, logs `networks: [...]` so DNS issues are immediately visible
- Both changes in `utils.py` `ensure_container_running()`

## What didn't work

- N/A
