# Error 0015: Session Synthesis Persona Leakage

## Symptoms
When a user asks questions about their chat history (e.g. "what did Alisa assign me"), the LLM reads the extracted chat history and adopts the persona of the user (`[Me]`) in the chat logs. Instead of answering the question from the perspective of an external assistant analyzing a log, the LLM translates one of the user's messages and presents it as its own answer.

## Investigation Notes
- **Stage 1 (Intent)**: Correctly identifies `person_name='Аліса'`, `query_type='person_chat'`.
- **Stage 2 (Fetch)**: Correctly retrieves messages between `Me` and `Аліса`. The log displays the messages with prefixes `[Me]: ... [Аліса]: ...`.
- **Stage 3 (Synthesis)**: Receives the fetched DB raw data and the original user query.
- The `user_content` instructions in `backend/session_agent.py` state: "Respond in natural, human-like conversational language".
- `Prompts.SESSION_SYNTHESIS_PROMPT` states "You are a helpful assistant. {session_context}... Compile a helpful, concise answer."
- **Root Cause**: The prompt lacks explicit grounding that the model is analyzing a third-party chat between "the user (Me)" and the "contact (Аліса)". When instructed to "answer the user's question" and "use conversational language", and given a large block of text written by "Me", the LLM simply mimics the "Me" persona.

## Hypotheses
- Enhancing the system prompt and instructions in `_build_synthesis_messages` and `SESSION_SYNTHESIS_PROMPT` to explicitly define the roles (e.g., "The chat logs have messages from 'Me' (the current user) and other people. You are an AI assistant analyzing this log. Do not pretend to be the user or the person they are chatting with.") will prevent the persona leakage.

## Experiments & Fix Plan
- Update `Prompts.SESSION_SYNTHESIS_PROMPT` to clarify the roles.
- Update `user_content` instructions in `backend/session_agent.py` to strongly discourage role-playing.

## Status
Pending
