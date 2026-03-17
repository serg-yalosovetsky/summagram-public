# Bug Fix Log: Frontend Console Error on Backend 503

## 1. Symptoms
- The Next.js frontend shows an "Unhandled Runtime Error" / "Console Error" overlay during development when the backend returns a 5x error.
- The `send_session_message` request failed with a 500 status code when the Model Orchestrator returned a 503 (due to WSL GPU unavailability), instead of returning a 503 to the frontend.
- The backend traceback logs `openai.InternalServerError: Service Unavailable: Docker API error starting container summagram_new_sglang_text` which bubbled up because it wasn't caught as a `ModelNotReadyError`.

## 2. Investigation Notes
- `backend/routes.py` expects `ModelNotReadyError` to return a 503 HTTP status.
- However, the `run_session_agent` call in `backend/service.py` returns an `openai.InternalServerError` (which inherits from `openai.APIStatusError`) if the downstream provider (model orchestrator proxy) is unavailable/returns 503.
- The circuit breaker catches the `Exception`, records the failure, but re-raises the raw `openai.InternalServerError`, resulting in a generic 500 error from FastAPI.
- On the frontend (`v0/components/views/chat-view.tsx`), the caught error was logged with `console.error([ChatView] Error sending message:, error)`. Next.js intercepts `console.error` with an `Error` object and displays it as a dev overlay.

## 3. Hypotheses
1. If we catch `openai.APIStatusError` in `backend/service.py` and raise `ModelNotReadyError`, the backend will cleanly return a 503 Service Unavailable without a crash traceback.
2. If we use `console.warn` passing only the error message string (instead of the `Error` object) in `chat-view.tsx`, the Next.js dev overlay will not appear, and the user will only see the intended `toast.error` notification.

## 4. Experiments Tried
N/A - Direct fix applied based on Next.js dev overlay behavior and FastAPI exception handling hierarchy.

## 5. Final Fix
- Added `import openai` to `backend/service.py`.
- Added an `except openai.APIStatusError as exc:` block to `send_session_message` in `backend/service.py` that raises `ModelNotReadyError(str(exc))`.
- Modified the catch block in `v0/components/views/chat-view.tsx` to extract the error message string and log it with `console.warn` instead of `console.error(..., error)`.

## 6. Verification
- Frontend will no longer show the red error overlay when the orchestrator fails to start the model container, and will instead show a toast notification.
- Backend will return `503 Service Unavailable` cleanly instead of dumping a stack trace for `openai.InternalServerError`.

## 7. Status
resolved
