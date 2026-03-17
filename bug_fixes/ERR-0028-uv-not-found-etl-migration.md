# ERR-0028: ETL Container Crashes on Startup due to missing `uv`
## Symptoms
The `etl` container crashes continuously upon startup with a `FileNotFoundError: [Errno 2] No such file or directory: 'uv'` raised by `subprocess.run()`. This prevents the application from initializing fully.

## Investigation Notes
- The crash originates in `etl/db/core.py`, specifically within the `init_db()` function during the lifespan startup of the FastAPI app.
- The `init_db()` function includes a `subprocess.run(["uv", "run", "piccolo", "migrations", "forwards", "all"])` call intended to execute database migrations on start.
- However, as documented in `ERR-0027`, this was known to cause issues by running migrations against the wrong database environments, and a proposal was previously made to remove it. Furthermore, the `etl/Dockerfile` does not install `uv`, preventing the subprocess from executing successfully.

## Hypotheses Considered
- Add `uv` to the standard Docker image. (Rejected because running `piccolo` migrations as part of runtime startup violates deployment best practices and overlaps with the previous `ERR-0027` fix logic).
- Remove the subprocess call entirely. (Selected, as migrations are meant to be an explicit deployment step).

## Experiments Tried
- Reviewed `ERR-0027` carefully, confirming that the explicit intention was to decouple migrations from the application’s runtime startup logic.

## Final Fix
Removed the embedded `subprocess.run` call from `etl/db/core.py` within `init_db()`. The function now cleanly initializes the `asyncpg.Pool` connection pool without attempting to invoke `uv` or `piccolo`.

## Verification
- Running `docker compose up` starts the `etl` container successfully without throwing `FileNotFoundError`.
- Checking logs confirms `etl-1` initializes and the database connection pool succeeds.

## Status
Resolved
