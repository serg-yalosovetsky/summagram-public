# Error 0036: Orchestrator Vision Timeout

## Symptoms
The `model-orchestrator-1` logs showed a failure during mode switch:
`Mode switch failed: Timeout (120s) waiting for http://summagram_new_sglang_vision:30000 (polled for 120.1s).`
followed by a 503 Service Unavailable when the AI attempted to route a completion request.

## Investigation
- Checked `summagram_new_sglang_vision` logs, which showed a startup crash: 
  `RuntimeError: Not enough memory. Please try to increase --mem-fraction-static. Current value: self.server_args.mem_fraction_static=0.2`.
- Checked `docker-compose.yml` and found `sglang_vision` was using `--mem-fraction-static "0.2"`.
- Since the architecture uses single-flight modes where text and vision containers do not run their models concurrently (text node was gracefully shut down prior to vision boot), the entire GPU is available for the vision node.

## Hypotheses
- The visual model needs a larger fraction of available memory for the KV cache pool than 20% on an 8GB VRAM GPU.
- Reducing concurrent requests and increasing allocated memory fraction solves similar OOMs in `sglang_text` (`0.85`, `running-requests=1`).

## Experiments Tried
- N/A (applied the fix directly based on `sglang_text` pattern).

## Final Fix
Increased memory allocation parameter and decreased max concurrent requests for `summagram_new_sglang_vision` in `docker-compose.yml`:
- Added `--max-running-requests "1"`
- Updated `--mem-fraction-static` from `"0.2"` to `"0.85"`.

## Verification
- Restarting orchestrator and container successfully boots `summagram_new_sglang_vision` without `Not enough memory` error. Model switch succeeds.

## Status
Resolved
