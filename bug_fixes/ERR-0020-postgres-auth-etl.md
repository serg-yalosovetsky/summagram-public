# ERR-0020: Postgres password authentication failed for ETL service

### Symptoms
The `etl` service repeatedly crashed on startup with `asyncpg.exceptions.InvalidPasswordError: password authentication failed for user "summagram"`. The `postgres` container logs showed matching `FATAL: password authentication failed` messages.

### Investigation Notes
*   **Facts:** The `docker-compose.yml` configures `POSTGRES_PASSWORD` to a secure string (`fYfz...`). The `POSTGRES_DSN` in both `docker-compose.yml` and Python files specifies the URL-encoded version of this password.
*   We tested the connection directly inside the postgres container using `psql`.
*   The secure password failed authentication. However, the old default password (`postgres`) succeeded.
*   This indicates the `postgres_data` volume was initialized previously with the password `postgres`. Updating `POSTGRES_PASSWORD` in `docker-compose.yml` does not alter the password of an already-initialized PostgreSQL cluster.

### Hypotheses Considered
1. **Change DSNs back to `postgres`:** This would fix the connection but leave the system with a weak hardcoded password.
    *   *Rejected:* Violates the security principle "No hardcoded credentials/secrets—ever."
2. **Recreate the Postgres volume:** Run `docker compose down -v` to wipe data and recreate with the new password.
    *   *Rejected:* Could cause data loss if there's important state in the database.
3. **ALTER USER password via SQL:** Connect to the running container with the old password and explicitly set the new password.
    *   *Accepted:* Safe, retains data, and aligns the database state with the `docker-compose.yml` configuration.

### Final Fix + Why it Works
*   Executed `ALTER USER summagram WITH PASSWORD 'fYfzQ9qdv2qLYYyD3jOF0z7yc2PyFVIFj57LrJI+J50=';` via `docker exec`.
*   This explicitly changes the postgres user's password inside the existing database to match the new secure credential expected by the `etl` and `backend` services.

### Verification
*   Commands run: `docker restart summagram-etl-1` and checking logs.
*   Expected Output: The `etl` container successfully initializes the DB connection and starts the server.
*   Actual Result: Passed.

### Status
Resolved.
