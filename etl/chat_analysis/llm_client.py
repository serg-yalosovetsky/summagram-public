"""
LLM client adapter for chat analysis.

Wraps the existing /generate backend endpoint to produce structured JSON
objects validated by Pydantic response models.

The backend speaks the same ChatML format as the Prompts module: the client
builds a ChatML prompt string from the message list and POSTs it to /generate.
"""
from __future__ import annotations

import json
import re
from typing import TypeVar

import httpx
from loguru import logger
from pydantic import BaseModel, ValidationError
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_fixed

from shared.config import Config


T = TypeVar("T", bound=BaseModel)

# Maximum tokens for segment-level extraction
SEGMENT_OUTPUT_TOKENS: int = 2048
# Maximum tokens for chat/contact aggregate
AGGREGATE_OUTPUT_TOKENS: int = 2048


def _get_backend_url(path: str) -> str:
    base = Config.BACKEND_URL.rstrip("/")
    return f"{base}/{path.lstrip('/')}"


def _build_chatml_prompt(messages: list[dict]) -> str:
    """Convert a ChatML message list to a raw prompt string."""
    prompt = ""
    for msg in messages:
        role = msg.get("role", "user")
        content = msg.get("content", "")
        prompt += f"<|im_start|>{role}\n{content}<|im_end|>\n"
    prompt += "<|im_start|>assistant\n"
    return prompt


def _extract_json(text: str) -> str | None:
    """Extract the first JSON object from model output."""
    # 1. Try markdown code block
    match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
    if match:
        return match.group(1)
    # 2. Try bare JSON object
    match = re.search(r"(\{.*\})", text, re.DOTALL)
    if match:
        return match.group(1)
    return None


class ChatAnalysisLlmClient:
    """Adapter over the backend /generate endpoint for structured JSON extraction."""

    def __init__(
        self,
        model_name: str = "unknown",
        model_version: str | None = None,
        segment_output_tokens: int = SEGMENT_OUTPUT_TOKENS,
        aggregate_output_tokens: int = AGGREGATE_OUTPUT_TOKENS,
        temperature: float = 0.1,
        timeout: float = 120.0,
    ) -> None:
        self.model_name = model_name
        self.model_version = model_version
        self.segment_output_tokens = segment_output_tokens
        self.aggregate_output_tokens = aggregate_output_tokens
        self.temperature = temperature
        self.timeout = timeout

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_fixed(2),
        retry=retry_if_exception_type(httpx.RequestError),
        reraise=True,
    )
    async def _call_generate(self, prompt: str, max_tokens: int) -> str:
        """POST to /generate and return raw text."""
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            resp = await client.post(
                _get_backend_url("generate"),
                json={
                    "prompt": prompt,
                    "max_tokens": max_tokens,
                    "temperature": self.temperature,
                },
            )
            resp.raise_for_status()
            return resp.json().get("text", "")

    async def generate_json(
        self,
        *,
        messages: list[dict],
        response_model: type[T],
        max_tokens: int,
    ) -> T:
        """
        Build a ChatML prompt from *messages*, call /generate, parse JSON,
        validate with *response_model*, and return the validated instance.

        Raises:
            ValueError: if the model output contains no parseable JSON.
            ValidationError: if JSON does not match the response_model schema.
        """
        prompt = _build_chatml_prompt(messages)
        raw_text = await self._call_generate(prompt, max_tokens)

        json_str = _extract_json(raw_text)
        if not json_str:
            raise ValueError(
                f"LLM output contained no JSON object. "
                f"First 200 chars: {raw_text[:200]!r}"
            )

        try:
            data = json.loads(json_str)
        except json.JSONDecodeError as exc:
            raise ValueError(
                f"LLM output JSON is malformed: {exc}. "
                f"JSON string: {json_str[:300]!r}"
            ) from exc

        return response_model.model_validate(data)
