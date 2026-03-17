# ERR-0046: TypeError in make_retrieval_plan()

## Symptoms
Running tests for `backend/session_tools.py` yields `TypeError: make_retrieval_plan() got an unexpected keyword argument 'mode'`.

## Investigation Notes
The `backend/session_tools.py` file was recently heavily refactored following a pipeline architecture (Normalizer -> ChatResolver -> PolicyBuilder -> Execution). The `RetrievalPolicyBuilder` now explicitly determines whether to use lexical, vector, or hybrid retrieval. The `SearchFromPersonService._retrieve` method passes `mode=policy.mode` to `make_retrieval_plan`. However, `make_retrieval_plan` in `backend/retrieval.py` lacks this parameter and calculates mode heuristically.

## Hypotheses
The refactoring assumed `make_retrieval_plan` was a thin wrapper that can take an explicit mode, bypassing internal heuristics. Since it doesn't, we get a TypeError.

## Final Fix
Pending

## Verification
Run `pytest backend/tests/test_search_from_person.py` and ensure they pass.

## Status
Pending
