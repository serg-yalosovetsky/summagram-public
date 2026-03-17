# ERR-0018: Change Postgres Port to 8432

### Symptoms
The user requested shifting the Postgres port on the host machine to 8432 to prevent conflicts or adhere to a different standard, as the default port 5432 might already be occupied.

### Investigation Notes
*   **Facts:** Postgres runs via docker, exposing `5432:5432`.
*   Several python test files use a fallback fallback port configuration connecting to `localhost:5432`.
*   Internal service communication in docker uses `postgres:5432`.

### Hypotheses Considered
1.  **Change everything to 8432:** This implies changing Postgres' internal bind port.
    *   *Rejected:* Unnecessary for local port binding mapping. We can just keep the internal postgres port at 5432 and expose it over 8432 on the host system.
2.  **Change host mapping only:** Alter `docker-compose.yml` to `8432:5432` and update the local python connection strings from `localhost:5432` to `localhost:8432`.
    *   *Accepted:* Safe and correct method. Kept internal docker connections at `postgres:5432`.

### Final Fix + Why it Works
*   Updated `docker-compose.yml` port map from `"5432:5432"` to `"8432:5432"`.
*   Updated local python fallback strings in `shared/config.py`, `backend/tests/conftest.py`, `etl/database.py`, and `etl/tests/conftest.py` from `localhost:5432` to `localhost:8432`.
This effectively forces host-side connections (tests, manual tools) to use the new `8432` port while Docker-internal networking remains undisturbed, satisfying the user's objective without breaking internal links.

### Verification
*   Commands run: `git diff docker-compose.yml` and reviewing updated configurations via script.
*   Expected Output: Successfully shifted `localhost:5432` -> `localhost:8432` strings.
*   Actual Result: Passed.

### Status
Resolved.
