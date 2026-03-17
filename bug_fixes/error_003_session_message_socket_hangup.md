# Error #3: `sendSessionMessage` fails with ECONNRESET / "Internal Server Error"

## Symptoms

**Frontend console:**
```
Failed to send session message: Internal Server Error
    at sendSessionMessage (lib/api.ts:211:15)
```

**Docker logs (frontend):**
```
Failed to proxy http://backend:8000/session/352990ed-92ad-4ce9-9aad-3c501a0132fa/messages Error: socket hang up
    at ignore-listed frames {
  code: 'ECONNRESET'
}
```

This error repeats on every message send attempt. Backend health checks pass fine (`GET /health` → 200 OK).

## Analysis

### Error chain (full trace)

1. User types message → frontend calls `sendSessionMessage()` in `v0/lib/api.ts:196`
2. `fetch('/api/session/{id}/messages', { method: 'POST', ... })` hits Next.js rewrite
3. `next.config.mjs` rewrites `/api/:path*` → `http://backend:8000/:path*`
4. Backend route `POST /session/{id}/messages` in `backend/routes.py:163`
5. Route calls `svc.send_session_message()` in `backend/service.py:178`
6. `send_session_message()` calls `run_session_agent()` — a **3-stage LLM pipeline**:
   - Stage 1: `_stage1_intent()` → `generate_json()` → HTTP POST to model orchestrator
   - Stage 2: `_stage2_fetch()` → tool execution (DB queries, may trigger additional LLM calls)
   - Stage 3: `_stage3_synthesize()` → `generate_text_from_messages()` → HTTP POST to model orchestrator
7. Each LLM call goes: backend → model orchestrator (`/v1/chat/completions`) → sglang_text container
8. If sglang_text is not running/ready: orchestrator returns 502 Bad Gateway or hangs during `switch_mode()`
9. OpenAI client in backend raises `openai.InternalServerError` → routes.py returns HTTP 500
10. **Meanwhile**: Next.js proxy timeout fires (default ~120s for Node.js HTTP), socket drops → `ECONNRESET`

### Root cause (multi-factor)

**Primary:** The sglang_text container is not running or not ready when messages are sent. This is downstream from errors #1 and #2 (DNS resolution failure, silent timeout).

**Contributing factor 1:** No request-level timeout on the backend's LLM calls. The `sglang_client.py` creates an `AsyncOpenAI` client with **no explicit timeout** — it uses the library default (10 minutes). If the model orchestrator is doing `switch_mode()` (which includes starting a container + `wait_for_ready` up to 120s), the backend request can legitimately take 2+ minutes.

**Contributing factor 2:** Next.js rewrite proxy has a default timeout. When the backend takes too long to respond, the proxy drops the socket → frontend sees `ECONNRESET`, while the backend is still processing.

**Contributing factor 3:** Repeated retries from the user compound the issue. Each "send" creates another pending backend request that also blocks on the same LLM call, potentially queueing them behind `state.lock` in the orchestrator.

### Files involved

| File | Role |
|------|------|
| `v0/lib/api.ts:195-214` | `sendSessionMessage()` — makes frontend fetch, parses error |
| `v0/next.config.mjs:10-30` | Rewrite rules — proxies `/api/*` to `http://backend:8000/*` |
| `backend/routes.py:163-179` | `send_session_message` route — calls `svc.send_session_message()` |
| `backend/service.py:178-209` | `send_session_message()` — orchestrates 3-stage pipeline |
| `backend/session_agent.py:176-202` | `run_session_agent()` — intent → fetch → synthesize |
| `backend/sglang_client.py:54-90` | `generate_json()` — OpenAI client, no explicit timeout |
| `model_orchestrator/router.py:48-81` | `/v1/chat/completions` — may call `switch_mode()` |
| `model_orchestrator/services.py:47-79` | `switch_mode()` — acquires lock, starts container, waits |
| `model_orchestrator/middleware.py:48-92` | `_stream_proxy()` — 300s timeout to sglang_text |

### Why health checks pass but messages fail

- `GET /health` on backend just returns `{"status": "ok"}` — no dependency check
- `_check_sglang_reachable()` in `backend/main.py` only runs at **startup** (lifespan)
- After startup, if sglang_text dies or OOMs, backend has no way to know until a request fails

## Proposal

### Fix 1: Add explicit timeouts to sglang_client.py

Add a `timeout` parameter to `AsyncOpenAI` calls in `sglang_client.py` (e.g. 60s for generate, 30s for JSON). This prevents backend workers from blocking indefinitely.

### Fix 2: Increase Next.js proxy timeout

In `next.config.mjs`, configure the rewrite with a longer timeout or add a `proxyTimeout` to handle LLM inference latency (which can be 30-90s even when healthy).

### Fix 3: Surface model status to frontend

Before sending a message, frontend can check `/api/system/status` to verify `current_model` is not null. If model is switching, show a "Model loading..." indicator instead of sending the message blindly.

### Fix 4: Add circuit-breaker to send_session_message

If the last LLM call failed within N seconds, immediately return a user-friendly error ("Model is warming up, please retry in a moment") instead of blocking another worker.

## What worked

Implemented a robust 5-part defense:
1. **Frontend Pre-warm:** Added `warmModel("text")` API calls to session clicks (in `session-select-view.tsx` and `sessions-view.tsx`) and to `chat-view.tsx` on mount. This triggers model loading immediately without waiting for the user to type and send.
2. **Loading UX:** Added a "Warming up..." spinner and toast in the chat view if they do send a message while the model is starting. Checks `/api/system/status` first.
3. **Backend Pass-through:** Added `POST /warm` to both the Next.js `api.ts`, the backend `routes.py`, and the model orchestrator `router.py`. All use fire-and-forget logic with short proxy timeouts (5s).
4. **LLM Timeouts:** Added explicit timeouts to `client = AsyncOpenAI(..., timeout=60.0)` in `sglang_client.py` so the backend web workers never wait forever. 
5. **Backend Circuit-breaker:** Added a failure tracker in `service.py|send_session_message`. If an LLM call fails, the next 15 seconds will instantly fast-fail with "Model is warming up" rather than queueing and blocking another worker thread behind a dead model.
6. **Log Metrics:** Added timing logs to `wait_for_ready` so we can observe exactly how long `sglang_text` takes to spin up in Docker Compose.

## What didn't work

_(Nothing failed during implementation, automated tests passed. Awaiting user manual testing.)_
