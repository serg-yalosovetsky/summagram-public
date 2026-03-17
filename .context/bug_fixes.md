# Bug Fixes Log

error 10:
description: Model orchestrator failed healthcheck because 'curl' was missing in its Dockerfile. (Ref: docs/bug_fixes/ERR-0010-orchestrator-unhealthy.md)
proposal: Install curl via apt-get in python:3.12-slim image and fix CRLF line endings in run.sh
successful: yes
error:

error 1:
description: Model orchestrator cannot resolve `summagram_new_sglang_text` DNS. (Ref: docs/bug_fixes/ERR-0001-dns-resolution.md)
proposal: Add post-start verification in `ensure_container_running()` — raise `ContainerStartError`
successful: yes
error:

error 2:
description: `wait_for_ready()` silently times out. (Ref: docs/bug_fixes/ERR-0002-wait-for-ready-timeout.md)
proposal: Make `wait_for_ready` raise `ModelReadyTimeoutError` on timeout.
successful: yes
error:

error 3:
description: `sendSessionMessage()` fails with ECONNRESET. (Ref: docs/bug_fixes/ERR-0003-session-message-econnreset.md)
proposal: Add explicit timeouts to client, increase Next proxy timeout, add circuit-breaker.
successful: no
error: `ECONNRESET` / `socket hang up` on `http://backend:8000/session/{id}/messages`

error 8:
description: sglang_text container fails to start with "Not enough memory". (Ref: docs/bug_fixes/ERR-0008-sglang-oom.md)
proposal: Increase mem-fraction-static to 0.90 and reduce max_total_tokens to 4096.
successful: no
error: Pending verification

error 4:
description: Orchestrator `switch_mode` times out. (Ref: docs/bug_fixes/ERR-0004-switch-mode-timeout.md)
proposal: Increase health_timeout to 600s and handle OpenAI 503 via ModelNotReadyError.
successful: yes
error:

error 5:
description: Model orchestrator orphans modal containers and logs leaked secrets. (Ref: docs/bug_fixes/ERR-0005-orphan-containers-secrets.md)
proposal: Added `cleanup_containers()` on shutdown and `Config.get_safe_dict()` for safe logging.
successful: yes
error:

error 11:
description: Orchestrator crashes with 500 when WSL GPU lacks adapters and backend docker stats fail. (Ref: docs/bug_fixes/ERR-0011-wsl-gpu-orchestrator.md)
proposal: Ignore missing docker.sock in backend stats and catch ContainerStartError for APIError on start.
successful: yes
error:

error 12:
description: Next.js dev overlay triggers on backend 500 error due to WSL GPU unavailability. (Ref: docs/bug_fixes/ERR-0012-frontend-console-error.md)
proposal: Catch `openai.APIStatusError` in backend to return 503 HTTP instead of 500, and use `console.warn` string in frontend instead of logging the Error object.
successful: yes
error:

error 13:
description: Model orchestrator crashes starting sglang containers because WSL has no GPU adapters. (Ref: docs/bug_fixes/ERR-0013-docker-wsl-gpu.md)
proposal: Add USE_GPU env var to conditionally omit gpu device requests.
successful: yes
error:

error 14:
description: Jaeger container fails to start referencing undefined debug exporter. (Ref: docs/bug_fixes/ERR-0014-jaeger-exporter-config.md)
proposal: Define debug exporter in jaeger-config.yaml
successful: yes
error:

error 15:
description: Model assumes persona of user in summarize/synthesize stage because prompt lacks persona grounding. (Ref: bug_fixes/ERR-0015-session-synthesis-persona.md)
proposal: Add explicit instruction in SESSION_SYNTHESIS_PROMPT and session_agent.py defining the assistant's role and distinguishing the user ("Me") from the contact.
successful: pending
error:

error 16:
description: Multiple `/warm` calls race and return 503 "GPU busy"; circuit breaker trips on first transient error. (Ref: bug_fixes/ERR-0016-gpu-busy-race.md)
proposal: Shared-Task singleflight in orchestrator, threshold-based circuit breaker with expanded transient detection, config alignment (max_running_requests=1).
successful: yes
error:

error 17:
description: Docker compose build fails with "postgres_data: permission denied" when loading build context. (Ref: docs/bug_fixes/ERR-0017-docker-postgres-permission.md)
proposal: Create a root .dockerignore file to exclude postgres_data and other non-essential data directories from the build context.
successful: yes
error:

error 18:
description: Change Postgres port to 8432. (Ref: docs/bug_fixes/ERR-0018-postgres-port.md)
proposal: Update docker-compose and python testing strings mapping localhost:5432 to localhost:8432.
successful: yes
error:

error 19:
description: etl container crashes with ModuleNotFoundError for asyncpg. (Ref: bug_fixes/ERR-0019-etl-asyncpg-missing.md)
proposal: Add asyncpg to etl/requirements.txt and rebuild docker image.
successful: yes
error:

error 20:
description: ETL startup crashes with InvalidPasswordError because Postgres volume retained the old default password. (Ref: bug_fixes/ERR-0020-postgres-auth-etl.md)
proposal: Execute ALTER USER summagram WITH PASSWORD inside the running container to sync password with docker-compose.
successful: yes
error:

error 21:
description: backend container crashes with ModuleNotFoundError for asyncpg because it imports etl.database. (Ref: docs/bug_fixes/ERR-0021-backend-asyncpg-missing.md)
proposal: Add asyncpg to backend/requirements.txt and rebuild backend docker image.
successful: yes
error:

error 22:
description: etl indexing crashes with 6 validation errors for TelegramNodeMetadata missing required fields. (Ref: docs/bug_fixes/ERR-0022-telegram-node-metadata.md)
proposal: Add missing required fields (ts_unix_ms, ts_iso, content_norm, char_count, approx_token_count, ingested_at_unix_ms) and rename reply_to_id to reply_to_message_id in transform_telegram_docs_to_nodes.
successful: yes
error:

error 23:
description: Model orchestrator times out waiting for sglang_text because CUDA graph capture takes 165s. (Ref: bug_fixes/ERR-0023-cuda-graph-capture-timeout.md)
proposal: Add --disable-cuda-graph to _sglang_cmd configuration for the text model in model_orchestrator/config.py.
successful: pending
error:

error 24:
description: GPU analytics show "CUDA not available" because torch.cuda lacks GPU access in the backend WSL container. (Ref: bug_fixes/ERR-0024-nvidia-smi-analytics.md)
proposal: Replace torch.cuda with subprocess call to nvidia-smi to query GPU name and memory stats in backend/service.py.
successful: yes
error:

error 25:
description: etl container crashes querying database and cannot connect to backend because JSON extracted values return TEXT rather than int, and BACKEND_URL was missing from docker-compose. (Ref: docs/bug_fixes/ERR-0025-etl-database-datatype.md)
proposal: Cast int variables to str() when matching against JSON metadata text extraction in etl/database.py, and add BACKEND_URL=http://backend:8000 to etl env in docker-compose.yml.
successful: yes
error:

error 26:
description: Postgres container fails to start due to port 8432 being bound by a lingering `summagram-postgres-1` container from the old compose project name. (Ref: docs/bug_fixes/ERR-0026-docker-compose-idempotency.md)
proposal: Update stop.sh to explicitly stop the old 'summagram' compose project and containers, and make run.sh call stop.sh before starting to ensure idempotency.
successful: yes
error:

error 27:
description: Piccolo Migrations failed because tables already existed and `uv run` overrode test DSN. (Ref: bug_fixes/ERR-0027-piccolo-migration-uv-env.md)
proposal: Explicitly run --fake migrations to sync state and remove the `uv run piccolo` subprocess call from `init_db()`. 
successful: yes
error:

error 29:
description: Need a separate script to run automatic migrations since they were removed from runtime startup in ERR-0028. (Ref: docs/bug_fixes/ERR-0029-automigrate-script.md)
proposal: Created `automigrate.sh` at project root that changes into the `etl/` directory and explicitly runs `uv run piccolo migrations forwards all` with the necessary env vars.
successful: yes
error:

error 28:
description: etl container crashes with FileNotFoundError for 'uv' when running database migrations via init_db(). (Ref: docs/bug_fixes/ERR-0028-uv-not-found-etl-migration.md)
proposal: Remove the subprocess.run call for 'uv run piccolo migrations' from etl/db/core.py per ERR-0027 explicitly.
successful: yes
error:

error 30:
description: Docker API error starting container summagram_new_sglang_vision due to port 30001 conflict. (Ref: bug_fixes/ERR-0030-docker-port-conflict-vision.md)
proposal: Remove unnecessary host port bindings from sglang_text, sglang_vision, and whisper_server in docker-compose.yml.
successful: yes
error:

error 31:
description: ETL indexing fails with "TelegramNodeMetadata object has no field 'media'". (Ref: bug_fixes/ERR-0031-telegram-node-metadata-media.md)
proposal: Add `media: Optional[TelegramMediaMetadata] = None` to `TelegramNodeMetadata` in `etl/models.py`.
successful: yes
error:

error 32:
description: ETL fails with "invalid input for query argument $1: ... (value out of int32 range)" for Telegram chat IDs. (Ref: bug_fixes/ERR-0032-postgres-int-out-of-range.md)
proposal: Change `source_id`, `chat_id`, `user_id`, and `context_chat_id` from `Integer` to `BigInt` in `etl/tables.py` and run migration.
successful: yes
error:

error 33:
description: Token count exceeds the model's maximum context length of 8192 tokens during chat analysis. (Ref: bug_fixes/ERR-0033-token-count-exceeds-limit.md)
proposal: Decrease `MAX_CONTEXT_TOKENS` from 16384 to 8192 in `etl/sources/telegram.py`.
successful: yes
error:

error 33:
description: GPU VRAM shows 0 and UI Container list does not scroll because nvidia-smi 'graphics-apps' fails on WSL and 'compute-apps' returns [N/A], while the frontend wrapper lacks min-h-0. (Ref: docs/bug_fixes/ERR-0033-vram-wsl-scroll.md)
proposal: Gracefully handle [N/A] in _nvidia_procs, suppress graphics-apps query errors, and add 'min-h-0' to main-content.tsx layout.
successful: yes
error:


error 34:
description: Telegram ETL crashes with contacts foreign key constraint and analyze context token limit exceedance. (Ref: bug_fixes/ERR-0034-telegram-etl-fixes.md)
proposal: Explicitly persist `me` as Contact prior to looping dialogs, reduce generation constraint from 2048 to 1024, and utilize `/ 2` divider for string lengths to estimate tokens more pesimistically.
successful: yes
error:

error 35:
description: `relation "chat_segments" does not exist` when analyzing chat. (Ref: docs/bug_fixes/ERR-0035-chat-segments-table.md)
proposal: Run Piccolo ORM migrations to ensure `chat_segments` table exists in PostgreSQL.
successful: yes
error:

error 36:
description: Model orchestrator times out starting vision node due to Not enough memory (mem-fraction-static 0.2). (Ref: docs/bug_fixes/ERR-0036-orchestrator-vision-timeout.md)
proposal: Increase mem-fraction-static to 0.85 and max-running-requests to 1 for summagram_new_sglang_vision in docker-compose.yml.
successful: yes
error:

error 37:
description: Excessive GET requests in logs due to redundant and rapid polling. (Ref: docs/bug_fixes/ERR-0037-excessive-polling.md)
proposal: Remove redundant local polling loops and replace with explicit `EventSource` (SSE) streaming endpoints `/jobs/stream/{job_id}` in ETL and `/tasks/status/stream/{job_id}` in backend.
successful: yes
error:
error 36:
description: `replace_chat_segments` deleted elements instead of upserting, destroying `chat_segment_analysis` records due to cascade. (Ref: docs/bug_fixes/ERR-0036-chat-segments-cascade.md)
proposal: Refactor to UPSERT pattern to keep IDs stable, and add unique constraint to `chat_segments(chat_id, segment_no)`.
successful: yes
error:


error 0026:
description: Job status SSE connection errors on frontend
proposal: Add CORSMiddleware to ETL service main.py to allow cross-origin requests
successful: yes
error: 


error 38:
description: ImportError: cannot import name 'search_messages_from_others' from 'etl.db.chats' in backend/retrieval.py. (Ref: docs/bug_fixes/ERR-0038-search-messages-from-others-import.md)
proposal: Change the import of `search_messages_from_others` and `get_recent_messages` in `backend/retrieval.py` to use `etl.db.raw_documents`.
successful: yes
error: 


error 39:
description: `search_from_person` returns no messages for short semantic queries like "задала". (Ref: docs/bug_fixes/ERR-0039-search-messages-from-others-query.md)
proposal: Update `make_retrieval_plan` in `backend/retrieval.py` to use `hybrid` mode for short queries and task questions instead of forcing `lexical`.
successful: yes
error: 

error 40:
description: Pydantic rejects instantiation by field names `from_person`, `relation_type` because their aliases are required. (Ref: bug_fixes/ERR-0040-pydantic-alias-population.md)
proposal: Add `model_config = ConfigDict(populate_by_name=True)` to `RelationshipSignalPayload`.
successful: yes
error: 

error 41:
description: model-orchestrator healthcheck times out on startup because lifespan blocks HTTP server from opening port. (Ref: docs/bug_fixes/ERR-0041-model-orchestrator-healthcheck-startup-timeout.md)
proposal: Run initialization in a background task using `asyncio.create_task(init_text_mode())` and `ensure_mode("text")`.
successful: yes
error: 

error 43:
description: POST /session/<id>/messages → 500. ModuleNotFoundError: No module named 'pymorphy3' (and natasha NER warning) because both NLP packages are used in the session pipeline but were never added to backend/requirements.txt. (Ref: bug_fixes/ERR-0043-pymorphy3-natasha-missing.md)
proposal: Add `pymorphy3` and `natasha` to backend/requirements.txt, rebuild backend Docker image.
successful: yes
error:

error 44:
description: After ERR-0043 fix, pipeline still crashes with ModuleNotFoundError for rapidfuzz, then would cascade to dateparser and transformers — all lazily imported in session_pipeline/implementations/ but missing from backend/requirements.txt. (Ref: bug_fixes/ERR-0044-rapidfuzz-dateparser-transformers-missing.md)
proposal: Add rapidfuzz, dateparser, transformers to backend/requirements.txt, rebuild backend Docker image.
successful: yes
error:

error 45:
description: Pytest execution fails with ConnectionRefusedError [Errno 111] because conftest.py eagerly connects to the test database inside a session fixture when Docker isn't running. (Ref: docs/bug_fixes/ERR-0045-session-tools-test-db-connection.md)
proposal: Wrap the asyncpg.connect block in backend/tests/conftest.py with a try/except OSError that softly skips test DB reset if Postgres is unreachable, allowing isolated pure logic unit tests to succeed.
successful: yes
error:

error 46:
description: TypeError: make_retrieval_plan() got an unexpected keyword argument 'mode'. (Ref: docs/bug_fixes/ERR-0046-retrieval-plan-mode-argument.md)
proposal: Add `mode` as an optional parameter to `make_retrieval_plan` to allow explicit mode overrides from the new RetrievalPolicyBuilder.
successful: pending
error:

error 47:
description: vision-vllm crashes with `ImportError: Package 'num2words' is required` because SmolVLM2-2.2B-Instruct processor requires it but `vllm/vllm-openai:latest` image does not include it. (Ref: bug_fixes/ERR-0047-vision-vllm-num2words.md)
proposal: Override vision-vllm entrypoint to `pip install num2words` before launching vllm serve; also add `--gpu-memory-utilization 0.7`.
successful: yes
error:

error 48:
description: text-vllm crashes with `ValueError: Free memory (6.87 GiB) < desired GPU utilization (0.9 → 7.2 GiB)`. VLLM_GPU_UTILIZATION=0.7 was set in .env but never wired into the container command. (Ref: bug_fixes/ERR-0048-text-vllm-gpu-oom.md)
proposal: Add `--gpu-memory-utilization 0.7` to text-vllm command in docker-compose.yml.
successful: yes
error:

error 49:\ndescription: text-vllm ValueError: No available memory for the cache blocks due to CUDA graph pre-allocation pushing memory above the 0.7 utilization threshold. (Ref: bug_fixes/ERR-0049-text-vision-oom.md)\nproposal: Add --enforce-eager to text-vllm (and vision-vllm) in docker-compose.yml to avoid large memory graph capture pre-allocations and fit within 5.6 GB limit.\nsuccessful: yes\nerror:\n

error #: ERR-0047
description: vision-vllm fails to start due to bash word splitting on JSON argument
proposal: Quote $$@ in the docker-compose entrypoint to prevent word splitting
successful: yes
error:

error #: ERR-0050
description: vision-vllm fails to start with "larger than the available KV cache memory" due to max_model_len 4096 being too large for gpu_memory_utilization 0.25
proposal: Decrease --max-model-len to 2048 for vision-vllm to fit in available GPU memory.
successful: yes
error:
