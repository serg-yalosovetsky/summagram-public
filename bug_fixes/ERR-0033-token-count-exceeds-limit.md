# ERR-0033: Token count exceeds max context length

## Symptoms
The backend API `/generate` returned a 400 Bad Request with the message: "Requested token count exceeds the model's maximum context length of 8192 tokens." The `etl` container logged a 500 error because the backend service threw an exception during `analyze_chat` in `etl/sources/telegram.py`.

## Investigation Notes
- Stack trace showed `routes:generate_text:306` failing after `etl/sources/telegram.py` dispatched the prompt.
- Inspected `etl/sources/telegram.py` and found `MAX_CONTEXT_TOKENS` was hardcoded to `16384`.
- The language model currently deployed has a context limit of `8192`.

## Hypotheses Considered
The token limit in the python code defining the truncation strategy does not match the actual language model's maximum limit. By decreasing `MAX_CONTEXT_TOKENS` to `8192`, truncation will happen earlier and the prompt will fit inside the context window.

## Final Fix
Changed `MAX_CONTEXT_TOKENS` in `etl/sources/telegram.py` from `16384` to `8192`.

## Verification
- Restart the ETL service and confirm that `analyze_chat` no longer crashes with an HTTP 400 for long chats.

## Status
resolved
