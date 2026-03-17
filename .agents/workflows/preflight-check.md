---
description: Run fast safety checks (config → lint/format → types → tests). Fail loudly, report precisely.
---

// turbo
1. Repo snapshot (so we know what we’re validating)
   git status --porcelain
   git rev-parse --show-toplevel

2. Detect project tooling (don’t guess)
   ls
   test -f pyproject.toml && sed -n '1,220p' pyproject.toml || true
   test -f requirements.txt && sed -n '1,120p' requirements.txt || true
   test -f requirements-dev.txt && sed -n '1,120p' requirements-dev.txt || true

// turbo
3. Sanity check Python + importability (fast fail)
   python -V
   python -m compileall -q .

// turbo
4. Lint (ruff) — fail fast on style/bugs
   ruff --version
   ruff check .

// turbo
5. Format check (no auto-format in preflight)
   ruff format --check .

6. Type check (if configured; otherwise explain what’s missing)
   mypy --version
   mypy .

// turbo
7. Tests (unit first; keep signal high)
   pytest -q

8. Report
   echo "Preflight done. If anything failed: summarize root cause + exact failing command + next fix step."