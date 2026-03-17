---
trigger: always_on
---

# Antigravity Coding Rules (v1)

Goal: production code that is easy to reason about, fails loudly, and is testable.

---

## 0) Truth-first (no confident nonsense) 🧠
- If you are unsure, say so explicitly and propose a concrete way to verify (run tests, inspect types, grep code, read docs).
- Do not invent APIs, config keys, or behavior. Prefer “I checked in code / types / tests” over guesses.

## 1) Fail fast; never hide errors ⚠️
- No `except: pass`, no swallowing exceptions, no silent fallbacks that mask broken states.
- Errors must be:
  1) **visible** (proper exception/HTTP status + log),
  2) **diagnosable** (context, identifiers),
  3) **safe** (no partial writes; keep invariants intact).

## 2) Preconditions & readiness checks ✅
- On service startup, validate all required conditions to run:
  - configuration is present & valid,
  - critical dependencies are reachable (DB/Redis/queue/external APIs if required),
  - schema/migrations state is compatible (when applicable).
- Prefer separate health/readiness concepts (liveness vs readiness).

## 3) Imports at the top (with rare, justified exceptions)
- Imports go at the top of the file.
- Exceptions (local imports) allowed only when justified:
  - heavy dependency that hurts startup time/memory,
  - circular import,
  - optional dependency behind a feature flag.
- If using local import: add a short comment explaining why.

## 4) Type hints everywhere 🧩
- All functions/methods must be annotated (args + return).
- Avoid `Any` unless truly necessary; if used, explain why.
- For complex data shapes: use typed objects, not ad-hoc dicts.

## 5) Pydantic for structured data (no weird nested dicts) 📦
- All boundary data must be modeled:
  - API request/response payloads,
  - events/messages,
  - config/settings,
  - DTOs between layers.
- Prefer Pydantic models over “bags of dict” for anything non-trivial.

## 6) Testing is mandatory (self-check) 🧪
- Write tests for changes:
  - unit tests for logic (fast, isolated, no network),
  - integration tests for real dependencies (DB/Redis/queue) where needed.
- Every bug fix requires a test that fails before the fix and passes after.
- Prefer deterministic tests; no flaky time-based sleeps if avoidable.

---

## 7) Clear architecture boundaries
- Controllers/routers: I/O + validation + mapping only.
- Business logic: services/use-cases (no HTTP concerns).
- Persistence: repositories/DAOs.
- External integrations: dedicated clients/adapters.
- Avoid mixing layers in one function.

## 8) Error contracts & mapping
- Use explicit domain exceptions (typed) for business errors.
- Map exceptions to consistent API error responses (code + message).
- Never leak secrets, tokens, raw SQL, or PII in error messages/logs.

## 9) Logging & observability 🔍
- No `print` in production code.
- Prefer structured logs (key=value fields).
- Include request/job correlation IDs when available.
- Log at the right level:
  - INFO for normal state transitions,
  - WARNING for recoverable issues,
  - ERROR for failures,
  - DEBUG for deep diagnostics.

## 10) Security by default 🛡️
- No hardcoded credentials/secrets—ever.
- Parameterize SQL; never string-concatenate user input into queries.
- Validate and sanitize any user-controlled input.
- Be careful with subprocess/shell: avoid it; if unavoidable, never build shell strings.

## 11) Async & performance sanity
- In async code: never block the event loop with heavy sync I/O.
- Avoid N+1 queries; think about indexes and query plans.
- Cache only with a correctness story (invalidation/TTL).

## 12) Minimal diffs; deliberate refactors ✂️
- Make the smallest change that solves the problem.
- Avoid “drive-by refactors” unless they clearly reduce risk/complexity.
- If a refactor is needed, do it in a separate commit/PR when possible.

## 13) Definition of Done ✅
- Code compiles/starts locally.
- Formatter + linter + type check pass.
- Relevant unit/integration tests pass.
- Docs/comments updated where behavior changed.