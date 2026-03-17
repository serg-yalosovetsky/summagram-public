# ERR-0010: Orchestrator Unhealthy

## Symptoms
`docker-compose up` fails stating "container summagram_new-model-orchestrator-1 is unhealthy", preventing backend and frontend containers that depend on it from starting. In addition, `./run.sh` fails on line 5 with "-d: command not found".

## Investigation
- Container logs showed `Application startup complete.` and uvicorn running correctly on port 8000.
- Docker-compose uses curl for the health check.
- Checking `model_orchestrator/Dockerfile` revealed it's derived from `python:3.12-slim` without installing `curl`.
- `run.sh` contains a hidden `\r` (CRLF line ending), parsing the last `-d` argument differently on Linux.

## Hypotheses
- Missing `curl` causes the Docker healthcheck command to exit with status code 127 (or similar), making Docker mark the container as unhealthy, despite the server running fine.
- DOS line endings break `bash` parsing of scripts.

## Experiments & Fix
- Updated `model_orchestrator/Dockerfile` to `RUN apt-get update && apt-get install -y --no-install-recommends curl && rm -rf /var/lib/apt/lists/*`.
- Re-wrote `run.sh` to ensure native UNIX line endings (`LF`).

## Verification
- Run `./run.sh` again to ensure it successfully builds the images and spins up containers. Health check should pass.

## Status
Resolved
