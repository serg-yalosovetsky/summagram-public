# ERR-0024: GPU Analytics Display "CUDA not available"

## Symptoms
The frontend analytics view constantly displays "CUDA not available" under GPU Memory. The underlying API response from the backend had `cuda_available: false` because `torch.cuda.is_available()` returns false in the Docker container where the backend service runs. The user needs basic GPU memory statistics using `nvidia-smi` even if the backend itself is not configured to do tensor operations via PyTorch.

## Investigation Notes
- `torch.cuda.is_available()` does not function correctly without actual adapters properly initialised or when torch is running without deep GPU permissions in WSL.
- `nvidia-smi` is generally available to gather general GPU metrics like total, used, and free memory natively via subprocess.
- The `get_system_status` logic in `backend/service.py` was exclusively relying on PyTorch's `cuda` package.

## Hypotheses Considered
1. **Debug Torch / Container runtime**: We could try to make `torch.cuda` work by installing the correct dependencies or fixing container devices mapping. (Rejected: too heavy, not needed just for basic telemetry).
2. **Subprocess to `nvidia-smi`**: We can explicitly invoke `nvidia-smi` with `--query-gpu` flags to read the `cuda_available` flag and parse memory metrics. (Selected).

## Final Fix
Updated `backend/service.py` `get_system_status()` to attempt invoking `nvidia-smi --query-gpu=name,memory.total,memory.used,memory.free --format=csv,noheader,nounits` via `subprocess.run()`. It successfully populates `cuda_available`, `gpu_name`, `memory_total_mb`, `memory_allocated_mb`, `memory_reserved_mb`, and `memory_free_mb` if the command succeeds. It falls back to `torch.cuda` if the command is unavailable.

## Verification
- Added the feature to `backend/service.py`.
- The user can verify by looking at the analytics page or the `/health` / `/status` endpoint manually.

## Status
resolved
