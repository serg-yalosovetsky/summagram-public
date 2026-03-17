# Error #2: `wait_for_ready()` silently times out, mode set prematurely

## Symptoms

```
model-orchestrator-1 | WARNING:orchestrator:Timeout (120s) waiting for http://summagram_new_sglang_text:30000 to be ready.
model-orchestrator-1 | INFO:orchestrator:Startup complete — text mode active.
```

Despite timeout, the orchestrator reports "text mode active" and starts accepting proxy requests to a dead host.

## Analysis

### Code path

In `main.py` lifespan:

```python
await wait_for_ready(cfg.url, endpoint=cfg.health_endpoint, timeout=cfg.health_timeout)
state.current_mode = "text"  # <-- always executes, even after timeout!
logger.info("Startup complete — text mode active.")
```

In `services.py` `wait_for_ready()`:

```python
async def wait_for_ready(url, endpoint="/v1/models", timeout=120):
    # ... polls endpoint ...
    while time < timeout:
        try:
            resp = await client.get(full_url, timeout=2.0)
            if resp.status_code == 200:
                return  # success
        except Exception:
            pass
        await asyncio.sleep(2)
    logger.warning(f"Timeout ({timeout}s) waiting for {url} to be ready.")
    # <-- returns None, no exception raised!
```

### Root cause

`wait_for_ready()` is designed as a "best effort" poller. On timeout it logs a WARNING and **returns normally**. The lifespan code assumes `wait_for_ready` returning means the service is ready.

This means:
- `state.current_mode = "text"` is always set after `wait_for_ready` returns
- The `except Exception as e:` block in lifespan NEVER catches the timeout case
- All subsequent requests are proxied to a dead host
- `switch_mode()` in `services.py` skips switching because `state.current_mode == target_mode` is already `True`

### Consequence chain

1. `wait_for_ready` times out → returns normally
2. `state.current_mode = "text"` set
3. Request arrives → `chat_completions()` checks `state.current_mode == "text"` → skips `switch_mode()`
4. Sets `proxy_url = http://summagram_new_sglang_text:30000/v1/chat/completions`
5. Middleware tries to connect → DNS fails → 502

## Proposal

**Option A (recommended):** Make `wait_for_ready` raise `TimeoutError` on timeout:

```python
async def wait_for_ready(url, endpoint="/v1/models", timeout=120):
    # ... same polling loop ...
    raise TimeoutError(f"Timeout ({timeout}s) waiting for {url} to be ready.")
```

This way the lifespan's `except Exception` catches it and leaves `current_mode = None`, which triggers `switch_mode()` on first request.

**Option B:** Check return value — change `wait_for_ready` to return `bool` and check it in lifespan.

## What worked

- Changed `wait_for_ready()` to raise `TimeoutError` instead of `logger.warning()` — single-line change in `services.py`
- This ensures the lifespan's `except Exception` catches timeout and leaves `current_mode = None`
- When `current_mode` is `None`, the router's `chat_completions()` handler calls `switch_mode()` on next request, properly retrying container startup

## What didn't work

- N/A
