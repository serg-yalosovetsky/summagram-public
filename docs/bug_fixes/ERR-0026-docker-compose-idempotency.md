# ERR-0026: Docker Compose Idempotency

## Symptoms
When running `./run.sh`, the database container fails to start with the error `Error response from daemon: failed to set up container networking: driver failed programming external connectivity on endpoint summagram_new-postgres-1 ... Bind for 0.0.0.0:8432 failed: port is already allocated`. 

## Investigation
By running `docker ps -a`, we observed that a container named `summagram-postgres-1` (belonging to the older `summagram` compose project) was already running and bound to port 8432. Since `stop.sh` only called `docker compose -p summagram_new down`, it didn't clean up containers from the old run, resulting in a port conflict. Also, `run.sh` wasn't proactively cleaning up old network bindings or old compose projects.

## Resolution
1. Updated `stop.sh` to additionally run `docker compose -p summagram down` and `docker rm -f summagram-postgres-1 ...` to ensure all lingering containers from the old stack are destroyed.
2. Updated `run.sh` to call `./stop.sh` at the very beginning to ensure the environment is clean before starting the new stack, making it fully idempotent.

## Verification
Ran `./stop.sh` and confirmed the old containers were removed. Checked `docker ps -a` and verified no extra postgres or old stack containers existed. 

## Status
Resolved
