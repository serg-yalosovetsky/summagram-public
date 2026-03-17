# ERR-0017: Docker Build Context Permission Denied for postgres_data

### Symptoms
When running `docker compose up` or `docker compose build`, the build process fails immediately during the "load build context" step for the `backend` or `etl` services, showing the message:
`error from sender: open ./postgres_data: permission denied`.

### Investigation Notes
*   **Facts:** Docker loads the local directory into the build context based on `context: .` in `docker-compose.yml`.
*   **Logs:** `failed to solve: error from sender: open /home/.../postgres_data: permission denied`
*   **Root Cause:** The `postgres_data` folder was created by a container running as a different UID (the PostgreSQL image default uid). Since it is not ignored via `.dockerignore`, the local Docker daemon on the host tries to read it to bundle it for the context tarball, but fails due to lacking read permissions on that directory.

### Hypotheses Considered
1.  **Change folder permissions on host:** Using `sudo chown` to ensure the host user can read the directory.
    *   *Rejected:* Doesn't solve the core issue that `postgres_data` shouldn't be loaded into the build context in the first place, as it severely slows down builds and unnecessarily bloats context size.
2.  **Add `.dockerignore` file:** Create a root `.dockerignore` to explicitly ignore data folders from the build context.
    *   *Accepted:* Standard, correct solution to prevent context bloat and permission issues.

### Final Fix + Why it Works
Created a root `.dockerignore` file:
```text
**/.git
**/.venv
**/venv
**/node_modules
**/__pycache__
**/*.pyc
**/*.pyo
**/.pytest_cache
postgres_data/
chroma_data/
models_cache/
logs/
storage/
.env
.env.*
v0/.next/
v0/node_modules/
.pytest_cache/
```
By explicitly ignoring `postgres_data` (and others like `chroma_data`, `models_cache`), the Docker Engine immediately skips these folders when walking the directory structure to build the context. This not only avoids the permission denied error but also dramatically speeds up the "load build context" build step.

### Verification
*   Commands run: `docker compose build backend`
*   Expected Output: Successfully steps through image stages without erroring during context load.
*   Actual Result: Passed.

### Status
Resolved.
