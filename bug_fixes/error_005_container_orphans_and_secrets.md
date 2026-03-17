# Error #5: Model orchestrator orphans modal containers and secrets are leaked in logs

## Symptoms
Running `docker compose -p summagram_new down` succeeds for the base compose services, but hangs and leaves the `summagram_new_default` network in use:
`! Network summagram_new_default Resource is still in use 0.0s`.
This happens because `summagram_new_sglang_text` was spun up dynamically via the docker socket rather than compose directly, so compose does not remove it. The dangling container still maps to the compose network.
On the next `up`, the remaining orphan container interferes with properly checking model statuses because it might be half-broken.

Furthermore, upon inspection of docker logs, we noticed that `safe_config` dictionary comprehension in the `lifespan` dumps of the `backend` and `etl` services printed plain-text values of keys containing `_HASH`, `_PHONE`, `_KEY` and other sensitive environment variables.

## Analysis
- `docker-py` dynamically manages containers created by `ContainerCreateParams.from_model_config()`. To prevent compose artifacts, the manager of these dynamic lifecycle bounds (`model_orchestrator`) must explicitly clean them up on its application shutdown cycle (`lifespan` yield).
- To fix the logging of secrets, we should use a specialized configuration output formatter that recognizes keys with known secret suffixes/prefixes and safely replaces their value with `***MASKED***`.

## Fix
1. Modified `model_orchestrator/utils.py` by adding `cleanup_containers()` logic to traverse over `MODEL_CONFIGS`, attempt to get the exact container instances by reference, and then issue `.stop(timeout=5)` and `.remove(force=True)`.
2. Appended `cleanup_containers()` to `model_orchestrator/main.py`'s `lifespan` exit trap.
3. Expanded `shared/config.py` with `@classmethod get_safe_dict(cls)` that masks str values if their upper key has `KEY`, `HASH`, `SECRET`, `TOKEN`, `PASSWORD`, or `PHONE`. Adjusted `backend/main.py` and `etl/main.py` to use it instead of doing list comprehensions locally. 

## Verification
Checked git diffs to ensure `get_safe_dict` handles secrets safely, no longer dumping sensitive logs. `docker compose down` will now trigger the FastAPI `lifespan` completion in `model_orchestrator` which sweeps the generated containers via docker API cleanly before dying.

## Status
Resolved
