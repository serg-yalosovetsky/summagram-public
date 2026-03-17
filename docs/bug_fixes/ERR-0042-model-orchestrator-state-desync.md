# ERR-0042: Model Orchestrator State Desync on Timeout

## Symptoms
- `model-orchestrator` logs show `Mode switch failed: Timeout (120s)` for `sglang_text`.
- Followed by `Error proxying to http://summagram_new_sglang_vision:30000/v1/chat/completions: [Errno -2] Name or service not known`.
- Subsequent vision requests return HTTP 502 Bad Gateway instantly.

## Investigation Notes
- Model orchestrator stops the `vision` container when preparing the `text` container.
- If the `text` container takes longer than `health_timeout` (120s) to become ready (e.g. because of CUDA graph capture), `wait_for_ready` raises `ModelReadyTimeoutError`.
- Because the exception is raised before `state.current_mode` is updated, `state.current_mode` remains `"vision"`.
- When the next `vision` request arrives, `ensure_mode("vision")` sees `state.current_mode == "vision"` and incorrectly assumes the container is running, bypassing start.
- `ProxyMiddleware` attempts to route the request to `summagram_new_sglang_vision`, which is stopped, leading to a DNS resolution failure.

## Hypotheses Considered
- DNS configuration issue in Docker Compose: Rejected, since the container works initially, and fails only after a mode switch timeout.
- SGLang crash: Rejected, as `docker logs` shows it gracefully exited upon SIGTERM (issued by `ensure_container_running`), and `sglang_text` is still capturing the CUDA graph.

## Final Fix
1. Increase `health_timeout` in `config.py` from 120s to 600s to accommodate CUDA graph capture.
2. Ensure that if `wait_for_ready` fails or any exception occurs during `_do_switch_mode`, `state.current_mode` is set to `None` to prevent state desynchronization.

## Verification
- Run `tests_run.sh` to ensure no regressions.
- Send a vision request, then a text request, and verify that the timeout does not happen, or if it does, `state.current_mode` is properly reset.

## Status
Resolved
