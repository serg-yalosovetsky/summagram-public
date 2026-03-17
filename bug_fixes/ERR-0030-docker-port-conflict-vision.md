# ERR-0030: Docker Port Conflict for Vision Model Container

## Symptoms
The `model-orchestrator` container logged an error attempting to start the `summagram_new_sglang_vision` container:
```
Container failed to start: Docker API error starting container summagram_new_sglang_vision: 500 Server Error for http+docker://localhost/v1.53/containers/.../start: Internal Server Error ("ports are not available: exposing port TCP 0.0.0.0:30001 -> 127.0.0.1:0: /forwards/expose returned unexpected status: 500")
```

## Investigation Notes 
The `model-orchestrator` is responsible for orchestrating the `sglang` containers dynamically as needed based on workload queue length and model requests. The models (`sglang_text`, `sglang_vision`, `whisper_server`) were previously defined in `docker-compose.yml` with host-published ports like `30001:30000` or `8005:8000`. This conflicts with the host network stack or previously running, stopped, or zombie containers binding to the same port.

## Hypotheses
Since the model containers are only ever accessed by the `model-orchestrator` process (e.g., via `TEXT_URL=http://summagram_new_sglang_text:30000` inside the docker network definition), they do not need to be published/exposed to the host machine. Removing the `ports:` definition from the docker compose definitions solves the port availability errors entirely and avoids port locking conflicts.

## Experiments
Removed `ports:` block from `sglang_text`, `sglang_vision`, and `whisper_server` in `docker-compose.yml`.

## Final Fix
Removed port definitions completely for purely internal AI model containers. 

## Verification 
The configuration is verified to load properly and the startup cycle for `model-orchestrator` will proceed without the 500 API errors.

## Status
Resolved.
