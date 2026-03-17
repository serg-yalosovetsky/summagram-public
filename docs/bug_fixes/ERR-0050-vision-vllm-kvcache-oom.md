# ERR-0050: vision-vllm KV Cache Out of Memory

## Symptoms
The `vision-vllm` service fails to start with the following ValueError:
`ValueError: To serve at least one request with the models's max seq len (4096), (0.44 GiB KV cache is needed, which is larger than the available KV cache memory (0.31 GiB). Based on the available memory, the estimated maximum model length is 2912. Try increasing gpu_memory_utilization or decreasing max_model_len when initializing the engine.`

## Investigation Notes
- The vLLM engine pre-allocates KV cache based on `gpu_memory_utilization` and `max_model_len`.
- For `vision-vllm`, we have constrained `gpu_memory_utilization` to `0.25` (approx `2 GiB` on an 8 GiB GPU) to allow it to bootstrap and then go to sleep without conflicting with `text-vllm`.
- With only `0.25` memory utilization and the model weights loaded into memory, there is only `0.31 GiB` left for the KV cache.
- The requested `max_model_len` of `4096` requires `0.44 GiB` for the KV cache, which exceeds the available `0.31 GiB`.

## Hypotheses Considered
1. **Increase `gpu_memory_utilization`:** This could fix the KV cache issue but risks an overall Out of Memory error or clashes with the `text-vllm` footprint, especially during concurrent initialization windows.
2. **Decrease `max_model_len`:** Lowering `max_model_len` reduces the KV cache requirement. The error message suggests a max length of `2912` fits exactly in `0.31 GiB`. Lowering it safely below this (to `2048`) will reserve enough KV cache to run reliably under the tight `0.25` limit.

## Experiments Tried
- Decreased `--max-model-len` to `2048` in the `vision-vllm` command of `docker-compose.yml`.

## Final Fix
Changed the `vision-vllm` command line argument from `--max-model-len 4096` to `--max-model-len 2048`.

## Verification
- Container successfully allocates KV cache without `ValueError`.
- Container reports ready and responds to healthchecks.

## Status
resolved
