# ERR-0039: `search_from_person` returns no messages for short semantic queries

## Symptoms
When a user asks "что мне задала алиса" (what did Alisa assign me), the orchestrator identifies the intent as `search_from_person` with `person_name: Аліса` and `search_query: задала`. However, the system incorrectly responds "No messages found from that person." (or "I found your replies but not the original question").

## Investigation
- In `backend/session_tools.py`, `_handle_search_from_person` parses the query "задала" and calls `make_retrieval_plan(query="задала", ...)`.
- In `backend/retrieval.py`, `make_retrieval_plan` counts the words (`words = 1`) and hits the heuristic `words <= 3`.
- This heuristic forces the retrieval plan to use **only** `RetrievalMode(mode="lexical")`.
- The `lexical` mode executes a strict substring search (`ILIKE '%задала%'`). Since the person likely gave the task without using the exact word "задала", no messages are returned.
- Furthermore, if a query triggers `is_task_q` (e.g., contains "task" or "homework"), it *also* forces `lexical` mode, which is counterproductive for semantic concepts.

## Proposed Fix
Update the heuristics in `backend/retrieval.py:make_retrieval_plan`:
1. Use `hybrid` mode instead of `lexical` for `is_task_q` (task questions).
2. Use `hybrid` mode instead of `lexical` for short queries (`words <= 3`).
Because `hybrid` executes both lexical AND vector search and merges the results via Reciprocal Rank Fusion, it gracefully handles both exact matches and semantic meaning without missing documents.

## Verification
- Validate the changes with existing tests via `pytest backend/tests/test_search_from_person.py` and `pytest backend/tests/test_retrieval.py` (if it exists).
- Ensure manual retrieval plans for short queries now output `hybrid` mode.
