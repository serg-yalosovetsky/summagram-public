# ERR-0049: text-vllm ValueError — No available memory for cache blocks

## Status: MITIGATED

## Symptoms
`text-vllm-1` (Qwen2.5-Coder-7B-Instruct-AWQ) exits with Error 1 in core.py:
```
ValueError: No available memory for the cache blocks. Try increasing `gpu_memory_utilization` when initializing the engine.
```

## Root Cause
- The user limited `text-vllm` to `--gpu-memory-utilization 0.7` in an attempt to fit both `text` and `vision` into an 8GB GPU.
- `0.7 * 8192 MiB = 5734 MiB`.
- The `Qwen2.5-Coder-7B-Instruct-AWQ` weights alone take ~5.2 GiB.
- vLLM (by default) reserves large memory pools for CUDA Graph capture to accelerate decoding.
- With CUDA Graph overhead on top of the 5.2 GiB weights, the remaining footprint is smaller than the required space for the KV Cache configuration (`max_model_len=8192`), causing initialization to fail instantly.

## Mathematical Impossibility Note
The user's setup expects `text-vllm` (0.7 utilization) and `vision-vllm` (0.25 utilization) to boot simultaneously before the `model-orchestrator` can place the idle container into Sleep Mode.
However, if `vision-vllm` is using `Qwen2.5-VL-3B-Instruct` (which requires 5.6 GB of weights natively, or 3.32 GB when using AWQ), it fundamentally CANNOT fit into the 0.25 footprint (2.0 GB).
Even if it did, `text-vllm` (requires 5.2 GB minimum) + `vision-vllm` (requires >3.3 GB minimum) = **>8.5 GiB**, exceeding the 8GB GPU's hardware limits during the simultaneous pre-allocation boot phase.

## Fix
1. Added `--enforce-eager` to the `text-vllm` command in `docker-compose.yml`. This disables CUDA Graph memory capture, reducing model memory overhead down closely to its bare 5.2 GiB baseline. This allows it to boot successfully on `0.7` utilization with around ~500 MiB free for the KV Cache.
2. Added `--enforce-eager` to the `vision-vllm` command for consistency.
**Warning**: `vision-vllm` will likely still encounter Native PyTorch CUDA Out Of Memory or `ValueError: No memory for cache blocks` upon starting up, because 8GB VRAM cannot hold both models simultaneously. Consider switching the vision model to a 2B parameter AWQ model, or running inference sequentially.

## Verification
- When run individually, `text-vllm` boots up and exposes its HTTP endpoints properly with `gpu_memory_utilization` at 0.7 and eager execution.

## References
- vllm Github discussions regarding `enforce_eager`.
- `text-vllm` logs: `Available KV cache memory: 0.52 GiB` with enforce_eager.
