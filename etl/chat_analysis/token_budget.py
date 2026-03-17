"""
Conservative character-based token budget.

We deliberately avoid `transformers` here — it is not installed in the ETL
container. A 2.5 chars/token divisor is pessimistic (real Cyrillic is ~2-3
chars/token depending on model), which means we always under-estimate the
available budget. That is the right direction for safety.

Actual budget:
  max_context=8192, output_tokens=600, safety_margin=300 → max_input≈7292
  Per-segment ceiling: 2200 chars/token-estimate (enforced in segmenter)
"""
from __future__ import annotations

import json
from dataclasses import dataclass


_CHARS_PER_TOKEN_ESTIMATE: float = 2.5   # pessimistic for mixed CIS/Latin/emoji


@dataclass(slots=True)
class BudgetConfig:
    max_context_tokens: int = 8192
    output_tokens: int = 600
    safety_margin: int = 300


class TokenBudget:
    """Estimate token counts without a real tokenizer."""

    def __init__(self, config: BudgetConfig | None = None) -> None:
        self.config = config or BudgetConfig()

    @property
    def max_input_tokens(self) -> int:
        return (
            self.config.max_context_tokens
            - self.config.output_tokens
            - self.config.safety_margin
        )

    def count_text_tokens(self, text: str) -> int:
        """Estimate tokens from raw text length."""
        return max(1, int(len(text) / _CHARS_PER_TOKEN_ESTIMATE))

    def count_chat_tokens(self, messages: list[dict]) -> int:
        """
        Estimate tokens from a ChatML message list.
        Accounts for role markers (≈8 tokens overhead per message).
        """
        total = 0
        for msg in messages:
            role = msg.get("role", "")
            content = msg.get("content", "")
            if isinstance(content, str):
                total += self.count_text_tokens(content)
            else:
                # content may be stringified JSON
                total += self.count_text_tokens(json.dumps(content))
            total += 8  # role markers + template overhead
        total += 3  # generation prompt overhead
        return total

    def fits_chat(self, messages: list[dict]) -> bool:
        """Return True if the message list fits within the input budget."""
        return self.count_chat_tokens(messages) <= self.max_input_tokens
