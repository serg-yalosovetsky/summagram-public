---
trigger: always_on
---

## Bug Fix Protocol (mandatory)

When an error/bug appears (runtime error, failing test, broken behavior):

### 1) Analyze → then Plan (always in this order)
- First: analyze what is wrong (symptoms, scope, likely root cause, evidence).
- Then: make a concrete plan (steps + how each step will be validated).

No “blind fixing”. Every change must be linked to a hypothesis and a verification step.

### 2) Maintain a global bug index (brief)
- Create/keep: `.context/bug_fixes.md`
- For every new error, append a brief entry in this exact format:

error #:
description:
proposal:
successful:
error:

Rules:
- Write briefly (1–3 lines per field).
- `successful:` must be `yes/no`.
- If `successful: no`, fill `error:` with the remaining failure or blocker.
- Each entry must reference the detailed file in `bug_fixes/` (see below).

### 3) One bug = one file with full history (detailed)
- Create a folder near `docs/`:
  - `bug_fixes/`
- Each error lives in its own file:
  - `bug_fixes/ERR-0001-short-title.md`
  - `bug_fixes/ERR-0002-...md`
- Every file must contain the full history:
  - what was broken (symptoms)
  - investigation notes (facts, logs, repro steps)
  - hypotheses considered (and rejected)
  - experiments tried (what worked / what didn’t)
  - final fix + why it works
  - verification (tests, commands, expected output)
  - status (resolved / mitigated / unresolved)

No closing an error without:
- updated `.context/bug_fixes.md` entry
- a detailed `bug_fixes/ERR-XXXX-*.md` file
- an explicit verification record (tests/commands).