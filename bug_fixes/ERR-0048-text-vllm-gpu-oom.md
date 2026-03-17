# ERR-0048: text-vllm GPU OOM — `Free memory < desired GPU utilization`

## Status: RESOLVED

## Symptoms
`text-vllm-1` (Qwen2.5-Coder-7B-Instruct-AWQ) exits with code 1:
```
ValueError: Free memory on device cuda:0 (6.87/8.0 GiB) on startup is less than
desired GPU memory utilization (0.9, 7.2 GiB).
Decrease GPU memory utilization or reduce GPU memory used by other processes.
```

## Root Cause
- vllm default `--gpu-memory-utilization` is `0.9` → 0.9 × 8 GiB = **7.2 GiB reserved**.
- `.env` has `VLLM_GPU_UTILIZATION=0.7` but this variable is **not wired** into the docker-compose `command:` for either vllm service.
- Both `text-vllm` and `vision-vllm` start simultaneously and both try to claim 90% of GPU memory.
- At the time text-vllm initializes, `vision-vllm` or the OS has already consumed some VRAM, leaving only **6.87 GiB** free — below the 7.2 GiB threshold.

## Fix
Explicitly pass `--gpu-memory-utilization 0.7` in the `text-vllm` command inside `docker-compose.yml`.  
This matches the user's intent expressed via `VLLM_GPU_UTILIZATION=0.7` in `.env`.  
0.7 × 8 GiB = 5.6 GiB — comfortably below 6.87 GiB of available VRAM.

Same flag added to `vision-vllm` for consistency and to prevent OOM races.

## Verification
- `docker compose up text-vllm` starts without ValueError.
- `nvidia-smi` shows VRAM usage ≤ 5.6 GiB per model process.

## References
- `docker-compose.yml` text-vllm service, line 188–206
- `.env`: `VLLM_GPU_UTILIZATION=0.7` (declared but unused until this fix)
- vllm source: `vllm/v1/worker/utils.py:227`
