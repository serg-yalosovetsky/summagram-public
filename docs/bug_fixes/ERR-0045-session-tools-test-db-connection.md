# ERR-0045: Pytest fails with ConnectionRefusedError due to eager DB fixture in conftest.py

## Symptoms
Running tests for pure logic modules like `pytest backend/tests/test_session_tools.py` fails entirely at the suite setup phase with a `ConnectionRefusedError: [Errno 111] Connect call failed ('127.0.0.1', 8432)`. The test runner throws an error for every isolated unit test and exits with status code 1.

## Investigation Notes
- `test_session_tools.py` contains pure unit tests testing logic classes (`QueryNormalizer` and `RetrievalPolicyBuilder`). It does not need a database.
- Running `docker ps` confirmed that the `localhost` Docker containers (including PostgreSQL on 8432) are currently stopped.
- Examining `backend/tests/conftest.py` revealed a `scope="session", autouse=True` fixture `mock_db_path`. This fixture eagerly attempts to connect to `postgresql://summagram...` to drop/recreate a test database, unconditionally executing on suite startup. 

## Hypotheses Considered
1. Leave `conftest.py` as-is and just boot up `docker compose up -d postgres` prior to any `pytest` run. Valid, but violates test isolation principles where pure unit testing shouldn't require heavy DB infrastructures running.
2. Remove `autouse=True` from the DB fixture and inject it explicitly into tests that need it. Valid, but requires refactoring the entire test suite which relies on implicit DB setup right now.
3. Catch the connection exception in the DB fixture, log a warning, and skip test DB instantiation gracefully. Pure logic tests aren't halted, and actual DB-dependent tests simply fail later indicating DB missing. (Selected path).

## Experiments Tried
- Formulated the plan to wrap `asyncpg.connect` in a `try/except OSError` wrapper within `conftest.py`.

## Final Fix & Rationale
We are implementing the try-except wrapper. It maintains the current test ecosystem workflow where `conftest.py` provides global environment resets, but allows isolated unit tests to finish quickly even if Postgres is not spun up yet. 

## Verification
- Execution of `pytest backend/tests/test_session_tools.py` passes immediately without the DB container active.

## Status
mitigated
