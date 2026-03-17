"""
SGLang client for text LLM inference.
Uses the same schema as session_agent: LLM_SERVER_URL, LLM_MODEL, OpenAI-compatible API.
"""

import logging
from typing import AsyncIterator

from shared.config import Config

logger = logging.getLogger(__name__)


def _build_messages(prompt: str, system_prompt: str = "") -> list[dict]:
    """Build OpenAI-format messages from prompt and optional system_prompt."""
    messages: list[dict] = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    messages.append({"role": "user", "content": prompt})
    return messages


async def generate_text(
    prompt: str,
    system_prompt: str = "",
    max_tokens: int = 2048,
    temperature: float = 0.3,
) -> str:
    """
    Generate free-form text via SGLang OpenAI-compatible API.
    Same schema as session_agent: LLM_SERVER_URL, LLM_MODEL.
    """
    from openai import AsyncOpenAI

    api_base = Config.LLM_SERVER_URL
    if not api_base:
        raise RuntimeError("LLM_SERVER_URL must be set (validated at startup)")

    client = AsyncOpenAI(base_url=api_base, api_key="dummy", timeout=60.0)
    messages = _build_messages(prompt, system_prompt)

    logger.info(
        f"SGLang generate_text | max_tokens={max_tokens}, temperature={temperature}"
    )
    response = await client.chat.completions.create(
        model=Config.LLM_MODEL or "default",
        messages=messages,
        max_tokens=max_tokens,
        temperature=temperature,
    )
    content = (response.choices[0].message.content or "").strip()
    logger.info(f"SGLang generate_text complete. Output length: {len(content)}")
    return content


async def generate_json(
    prompt: str,
    json_schema: dict,
    system_prompt: str = "",
    max_tokens: int = 2048,
    temperature: float = 0.1,
) -> str:
    """
    Generate a single JSON object conforming to json_schema via SGLang structured outputs.
    Returns the raw JSON string. Caller should parse with model_validate_json() or json.loads().
    """
    from openai import AsyncOpenAI

    api_base = Config.LLM_SERVER_URL
    if not api_base:
        raise RuntimeError("LLM_SERVER_URL must be set (validated at startup)")

    client = AsyncOpenAI(base_url=api_base, api_key="dummy", timeout=30.0)
    messages = _build_messages(prompt, system_prompt)

    logger.info(
        f"SGLang generate_json | max_tokens={max_tokens}, temperature={temperature}"
    )
    response = await client.chat.completions.create(
        model=Config.LLM_MODEL or "default",
        messages=messages,
        max_tokens=max_tokens,
        temperature=temperature,
        response_format={
            "type": "json_schema",
            "json_schema": {
                "name": "schema",
                "schema": json_schema,
            },
        },
    )
    content = (response.choices[0].message.content or "").strip()
    logger.info(f"SGLang generate_json complete. Output length: {len(content)}")
    return content


async def stream_generate_text(
    prompt: str,
    system_prompt: str = "",
    max_tokens: int = 2048,
    temperature: float = 0.7,
) -> AsyncIterator[str]:
    """
    Generate text streamingly via SGLang OpenAI-compatible API.
    Yields content deltas.
    """
    messages = _build_messages(prompt, system_prompt)
    async for chunk in _stream_messages(messages, max_tokens, temperature):
        yield chunk


def _messages_to_api(messages: list) -> list[dict]:
    """Convert ChatMessage or dict to OpenAI API format."""
    out = []
    for m in messages:
        if hasattr(m, "role") and hasattr(m, "content"):
            out.append({"role": m.role, "content": m.content or ""})
        elif isinstance(m, dict):
            out.append({"role": m.get("role", "user"), "content": m.get("content", "")})
        else:
            out.append({"role": "user", "content": str(m)})
    return out


async def generate_text_from_messages(
    messages: list,
    max_tokens: int = 2048,
    temperature: float = 0.3,
) -> str:
    """
    Generate text from a list of messages (for chat completions with multi-turn history).
    """
    from openai import AsyncOpenAI

    api_base = Config.LLM_SERVER_URL
    if not api_base:
        raise RuntimeError("LLM_SERVER_URL must be set (validated at startup)")

    client = AsyncOpenAI(base_url=api_base, api_key="dummy", timeout=60.0)
    api_messages = _messages_to_api(messages)

    logger.info(
        f"SGLang generate_text_from_messages | max_tokens={max_tokens}, temperature={temperature}"
    )
    response = await client.chat.completions.create(
        model=Config.LLM_MODEL or "default",
        messages=api_messages,
        max_tokens=max_tokens,
        temperature=temperature,
    )
    content = (response.choices[0].message.content or "").strip()
    logger.info(
        f"SGLang generate_text_from_messages complete. Output length: {len(content)}"
    )
    return content


async def _stream_messages(
    messages: list[dict],
    max_tokens: int = 2048,
    temperature: float = 0.7,
) -> AsyncIterator[str]:
    """Internal: stream from API messages."""
    from openai import AsyncOpenAI

    api_base = Config.LLM_SERVER_URL
    if not api_base:
        raise RuntimeError("LLM_SERVER_URL must be set (validated at startup)")

    client = AsyncOpenAI(base_url=api_base, api_key="dummy", timeout=60.0)

    stream = await client.chat.completions.create(
        model=Config.LLM_MODEL or "default",
        messages=messages,
        max_tokens=max_tokens,
        temperature=temperature,
        stream=True,
    )

    async for chunk in stream:
        if chunk.choices and chunk.choices[0].delta.content:
            yield chunk.choices[0].delta.content


async def stream_generate_text_from_messages(
    messages: list,
    max_tokens: int = 2048,
    temperature: float = 0.7,
) -> AsyncIterator[str]:
    """
    Stream text from a list of messages (for chat completions with multi-turn history).
    """
    api_messages = _messages_to_api(messages)
    async for chunk in _stream_messages(api_messages, max_tokens, temperature):
        yield chunk
