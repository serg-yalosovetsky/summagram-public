# ERR-0022: SGLang CUDA Graph Capture Timeout

## Symptoms
The backend `model-orchestrator` service crashes with a timeout waiting for the `sglang_text` container to start, emitting the following log: "Error during startup initialization: Timeout (120s) waiting for http://summagram_new_sglang_text:30000".

## Investigation Notes
- Model orchestrator's configured health check timeout for the text model is 120s.
- `docker logs summagram_new_sglang_text` show that capturing the CUDA graph alone takes `~165s`.
- As a result, the container takes too long to respond to the health check, breaking the orchestrator's startup logic.

## Hypotheses Considered
1. **Increase the orchestrator timeout**: We could increase `health_timeout` for the text model to >200s. 
2. **Disable CUDA graph capture**: Disable generating the CUDA graph on SGLang startup, significantly accelerating startup and bypassing the timeout, with a minor hit on throughput that is acceptable for single batch inferences.

## Final Fix
Add the `--disable-cuda-graph` argument to the `_sglang_cmd` configuration in `model_orchestrator/config.py` for the text model. This bypasses the massive delay during startup.

## Verification
1. Restart the orchestrator and the text model container.
2. Confirm that the `summagram_new_sglang_text` container initializes immediately without building the 165s CUDA Graph.
3. Confirm `model-orchestrator` logs no longer time out.

## Status
pending
