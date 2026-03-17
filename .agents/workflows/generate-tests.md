---
description: Generate/extend pytest tests for changed code, then run them until green. Prefer Pydantic DTOs and typed APIs.
---

// turbo
1. Define scope (changed files first; don’t boil the ocean)
   git status --porcelain
   git diff --name-only

2. Read target code and identify testable units
   - For each changed Python module: list public functions/classes, side effects, external deps.
   - Classify tests:
     - unit: pure logic (fast)
     - integration: DB/Redis/HTTP (slower, minimal)

3. Create/update tests
   - Place unit tests under: tests/unit/test_<module>.py
   - Place integration tests under: tests/integration/test_<feature>.py
   - Naming:
     - test_<behavior>_<expected_result>
   - Rules:
     - no weird nested dicts for payloads: use Pydantic models/fixtures
     - all new functions must have type hints; tests should respect contracts
     - no sleeps; use deterministic time controls/mocking

4. Add fixtures & fakes (avoid real network in unit tests)
   - Use dependency injection and monkeypatch/mocks for clients
   - Prefer factories/fixtures over copy-pasted payloads

// turbo
5. Run unit tests
   pytest -q tests/unit

6. If red → iterate
   - Fix tests OR fix code (whichever violates the contract)
   - Add regression test if it’s a bugfix

7. Run full suite (or explain why it’s skipped)
   pytest -q

8. Optional: save log artifact (if tee exists)
   mkdir -p .agent/artifacts || true
   pytest -q | tee .agent/artifacts/pytest.log || true