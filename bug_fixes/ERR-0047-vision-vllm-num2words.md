# ERR-0047: vision-vllm ImportError — `num2words` missing

## Status: RESOLVED

## Symptoms
`vision-vllm-1` exits with code 1 immediately on startup:
```
ImportError: Package `num2words` is required to run SmolVLM processor.
Install it with `pip install num2words`.
```
Container keeps restarting (`restart: unless-stopped`).

## Root Cause
`.env` sets `HF_MODEL_MEDIA=HuggingFaceTB/SmolVLM2-2.2B-Instruct`.  
The `transformers` `SmolVLMProcessor.__init__` has a hard import guard:
```python
# transformers/models/smolvlm/processing_smolvlm.py:174
raise ImportError("Package `num2words` is required ...")
```
The `vllm/vllm-openai:latest` Docker image does **not** include `num2words`.

## Hypotheses considered
1. Switch `HF_MODEL_MEDIA` to a model that has no extra deps (e.g. `Qwen/Qwen2.5-VL-3B-Instruct`) — rejected, user wants SmolVLM2.
2. Build a custom Docker image based on `vllm/vllm-openai` with `num2words` installed — valid, but heavyweight.
3. Override `entrypoint` in docker-compose to install `num2words` before launching the vllm server — **chosen** (minimal, zero image build required).

## Fix
In `docker-compose.yml`, `vision-vllm` service:
- Add `entrypoint: /bin/bash -c "pip install -q num2words && python -m vllm.entrypoints.openai.api_server $$@" --`
- Or equivalently: use a shell wrapper in `command:` with the appropriate approach.

Simplest approach: override `entrypoint` to install `num2words` then delegate to original entrypoint script.

```yaml
entrypoint: >
  /bin/bash -c "pip install -q num2words && exec vllm serve $@" --
```

Also added `--gpu-memory-utilization 0.7` to the vllm serve args to stay within available VRAM.

## Verification
- `docker compose up vision-vllm` no longer exits with ImportError.
- `curl http://localhost:8000/v1/models` returns 200 with SmolVLM2 listed.

## References
- `docker-compose.yml` vision-vllm service, lines 208–228
- transformers source: `processing_smolvlm.py:174`
