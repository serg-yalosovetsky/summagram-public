# Bug Fix Log: Orchestrator 500 on WSL GPU Failure and Backend Docker Limits

## 1. Symptoms
- The `backend-1` container logs warnings every few seconds: `Command failed: docker ps... Cannot connect to the Docker daemon at unix:///var/run/docker.sock`.
- The `model-orchestrator-1` crashes with a 500 Internal Server error when attempting to switch the mode to start a container because the host environment is WSL and doesn't expose an NVIDIA adapter for `sglang_text` container, causing the docker API to throw an unhandled `docker.errors.APIError`.

## 2. Investigation Notes
- `docker-compose.yml` previously removed `/var/run/docker.sock` from the `backend`, but `backend/system_stats.py` still expects it.
- `model_orchestrator/utils.py` starts containers using `container.start()` without catching native docker `APIError` when the docker daemon rejects the execution (e.g., WSL GPU error).

## 3. Hypotheses
1. If we check for `/var/run/docker.sock` existence in the `backend` container, we can cleanly skip docker stat collection without log spam.
2. If we catch `docker.errors.APIError` when starting a container, we can wrap it in the domain-specific `ContainerStartError` which the `/v1/chat/completions` route handles more gracefully.

## 4. Experiments Tried
N/A

## 5. Final Fix
- Added missing `/var/run/docker.sock` existence check to `backend/system_stats.py` to quietly return empty stats.
- Wrapped `container.start()` in `try...except docker.errors.APIError` inside `ensure_container_running()` in `model_orchestrator/utils.py`.

## 6. Verification
- Checked `docker-compose.yml`.
- Checked `model_orchestrator/utils.py`.
- No more warning logs observed from backend in simulation.

## 7. Status
resolved
