# ERR-0027: Piccolo Migrations Failed Due to Existing Tables and uv Env Override

## Symptoms
When running the test suite or starting the app, database migrations would hang and eventually fail. Attempting to run `uv run piccolo migrations forwards all` manually resulted in `relation "download_ranges" already exists`.

## Investigation Notes
- Piccolo ORM was integrated to replace the manual `INIT_SCRIPT`.
- The initial migrations contained the `CREATE TABLE` commands. Because the tables already existed physically in the Postgres database, running them anew caused SQL syntax errors.
- We also noticed tests were deadlocking on the db connection. This was traced down to `init_db()` issuing a `subprocess.run(["uv", "run", "piccolo", ...])`. The invocation via `uv run` was silently reading the local `.env` and overriding the `POSTGRES_DSN` environment variable intended for the test suite, executing migrations against the production database instead of the test database.

## Final Fix
1. Removed the embedded `subprocess.run` call from `init_db()`. Migrations are an explicit deployment step rather than part of the application runtime startup. 
2. Ran `uv run piccolo migrations forwards all --fake` on the existing databases so Piccolo correctly logs the schemas as migrated without attempting to re-execute `CREATE TABLE`.

## Verification
- `uv run piccolo migrations check` confirms all initial migrations read `RAN = True`.
- Explicit call via `subprocess` the `uv run` process is eliminated, allowing tests to run unobstructed against test databases.
