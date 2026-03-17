# ERR-0016: 503 "GPU Busy" Race Conditions

## Status: resolved

## Symptoms
- Multiple `/warm` calls during startup race and return 503 "GPU busy"
- Backend circuit breaker trips on first transient 503, blocking all LLM requests for 15s
- `max_running_requests=4` in config.py inconsistent with docker-compose.yml (1)

## Investigation
- SGLang is running and `/v1/models` responds correctly
- Orchestrator warm endpoint immediately returned 503 if lock was held (no singleflight)
- Backend `LLMCircuitBreaker` tripped on ANY exception including transient 503
- `config.py` had `max_running_requests=4` vs docker-compose `1`

## Hypotheses Considered
1. SGLang not starting → rejected (model endpoint responds)
2. Warm race condition → confirmed (multiple callers, no coalescing)
3. Circuit breaker too aggressive → confirmed (trips on first failure)
4. Config mismatch → confirmed (4 vs 1)

## Final Fix

### 1. Shared-Task singleflight (orchestrator)
- `models.py`: Replaced `warm_event: asyncio.Event` with `warm_task: Optional[asyncio.Task]` + `inference_sem: asyncio.Semaphore(1)`
- `services.py`: New `ensure_mode()` creates a shared `asyncio.Task` wrapping `_do_switch_mode()`. All concurrent callers await the same Task.
- `router.py`: Simplified — all routes call `ensure_mode()` directly. All warmup errors return 503 (not 500). No manual lock checking.

### 2. Circuit breaker threshold + expanded transient detection (backend)
- `service.py`: `LLMCircuitBreaker` now requires 3 consecutive non-transient failures before tripping
- Added `record_success()` (resets counter)
- Expanded `is_transient()`: 503, 429, timeouts, connection errors → transient (don't count)
- 500, other errors → non-transient (count toward breaker)

### 3. Config alignment
- `config.py`: `max_running_requests=4` → `1` (matches docker-compose; safe for 8GB VRAM)

## Verification
- 10 circuit breaker unit tests passed (threshold, reset, cooldown, is_transient for 503/429/timeout/connection/500/generic)
- Orchestrator state verified: warm_task + inference_sem correctly initialized
- Code review confirms ensure_mode singleflight semantics
