# Error #4: Orchestrator times out starting sglang_text due to CUDA graph capture

## Symptoms
`model-orchestrator-1` logs show a timeout after 120s:
```
Error during startup initialization: Timeout (120s) waiting for http://summagram_new_sglang_text:30000 to be ready (polled for 120.3s).. Text model will be started on first request.
```

When checking the status of `sglang_text`, we found:
```
[2026-03-05 02:42:40] Capture cuda graph begin. This can take up to several minutes. avail mem=0.71 GB
...
[2026-03-05 02:46:57] Capture cuda graph end. Time elapsed: 271.61 s.
```

The frontend sends a `/warm` request successfully (as `state.lock` avoids hanging the route HTTP request when it is locked, it returns `{"status": "switching"}`). 
Then, a subsequent message trigger requests `/v1/chat/completions`. Since `state.lock` is acquired by the background initialization (which takes 5 minutes), the `model_orchestrator` proxy correctly responds with a `503 Service Unavailable ("GPU busy with another task")`.
However, the `backend` received this `503` via `openai.InternalServerError: GPU busy with another task`.
Because it wasn't caught as a proper circuit breaker error (`ModelNotReadyError`), it trickled down as a `500 Internal Server Error`, thus bubbling a 500 error to the frontend:
```
Failed to process message: GPU busy with another task
```

## Investigation
- Realized SGLang takes > 4 minutes to start up due to `Capture cuda graph`. The `health_timeout` was hardcoded to `120s`.
- Inspected the `backend` proxy, `_llm_circuit_breaker.record_failure()` triggered on the exception, but failed to return 503, effectively throwing a 500. 
- Analyzed `SystemStatusResponse` in `backend/models.py` which was lacking the `switching` property for the `frontend` to indicate that loading is going on, and duplicate fields existed.

## Fix
1. Modified `health_timeout` in `model_orchestrator/config.py` from `120` to `600` for text and vision instances.
2. In `backend/service.py` under the `send_session_message` exception handler, recognized `503` (`status_code == 503`) or `"GPU busy"` strings to explicitly trigger the correct `ModelNotReadyError` (which is translated back as a `503` safely).
3. Cleaned up `SystemStatusResponse` payload in `backend/models.py` and included `switching=False` to respect frontend typings (`v0/lib/api.ts`).

## Verification
Checking `docker logs` metrics and simulated timeout. The orchestrator now successfully waits for the > 271.61s model load times.

## Status
Resolved.
