# ERR-0034: Telegram ETL Fixes (Foreign Key & Token Limits)

## Symptoms
1. The ETL process failed when processing Telegram contacts with `insert or update on table "chat_members" violates foreign key constraint "chat_members_user_id_fkey"`. The `DETAIL` exposed that `user_id` (the current bot user's ID) was absent from the `contacts` table.
2. The Telegram chat analysis part of the ETL failed with a 400 error: `Requested token count exceeds the model's maximum context length of 8192 tokens. You requested a total of 8691 tokens`.

## Investigation Notes
- **Foreign Key Violation:** In `process_contacts` (`etl/sources/telegram.py`), the codebase extracts user info from dialogs and inserts them as `Contact`s, then attempts to create chat member associations utilizing `await save_chat_member(user_id, my_id)`. However, `my_id` (the user running the script) is rarely found as an explicit dialog entity, and therefore wasn't inserted into `contacts` first.
- **Token Limits:** The chat summarization logic dynamically truncates message history utilizing an estimation `len(text) // 3`. Cyrillic language tokens are significantly shorter or equivalent to length chars, leading `len(text) // 3` to drastically undercount true token volume. Also, `DEFAULT_MAX_GENERATION_TOKENS` was reserved strictly at `2048`, meaning input context was smaller. Qwen context maximum set at `8192` threw validation since generated estimate combined with generation allocation exceeded `8192`.

## Final Fix
1. Explicitly extracted and persisted `me` information as a generic `Contact` record prior to the dialog traversal within `process_contacts`.
2. Increased pessimism within token truncation logic by utilizing `len(text) // 2` to accommodate Cyrillic tokens effectively.
3. Lowered `DEFAULT_MAX_GENERATION_TOKENS` to `1024` tokens, effectively raising available contextual input capacity and averting validation overflow errors.

## Verification
- Both model-based execution paths pass.
- Verified using DB inspections (no constraints exceptions on insertion).

## Status
Resolved
