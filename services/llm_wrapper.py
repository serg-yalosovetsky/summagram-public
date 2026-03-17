from typing import Any, Sequence
from llama_index.core.llms import (
    CustomLLM,
    CompletionResponse,
    CompletionResponseGen,
    LLMMetadata,
    ChatMessage,
    ChatResponse,
)
from llama_index.core.llms.callbacks import llm_completion_callback, llm_chat_callback
from services.inference import LocalInferenceService
from shared.config import Config
import asyncio


class LocalVLLM(CustomLLM):
    """
    Custom LLM wrapper pointing to our Orchestrator / SGLang.
    """

    context_window: int = Config.MAX_CONTEXT_LEN
    num_output: int = 2048
    model_name: str = Config.HF_MODEL_TEXT

    _service: LocalInferenceService = None

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._service = LocalInferenceService()

    @property
    def metadata(self) -> LLMMetadata:
        """Get LLM metadata."""
        return LLMMetadata(
            context_window=self.context_window,
            num_output=self.num_output,
            model_name=self.model_name,
        )

    @llm_completion_callback()
    def complete(self, prompt: str, **kwargs: Any) -> CompletionResponse:
        response = asyncio.run(self._service.text_llm.acomplete(prompt, **kwargs))
        return response

    @llm_completion_callback()
    async def acomplete(self, prompt: str, **kwargs: Any) -> CompletionResponse:
        return await self._service.text_llm.acomplete(prompt, **kwargs)

    def stream_complete(self, prompt: str, **kwargs: Any) -> CompletionResponseGen:
        response = self.complete(prompt, **kwargs)
        yield response

    async def astream_complete(
        self, prompt: str, **kwargs: Any
    ) -> CompletionResponseGen:
        async for chunk in await self._service.text_llm.astream_complete(
            prompt, **kwargs
        ):
            yield chunk

    @llm_chat_callback()
    def chat(self, messages: Sequence[ChatMessage], **kwargs: Any) -> ChatResponse:
        return asyncio.run(self._service.text_llm.achat(messages, **kwargs))

    @llm_chat_callback()
    async def achat(
        self, messages: Sequence[ChatMessage], **kwargs: Any
    ) -> ChatResponse:
        return await self._service.text_llm.achat(messages, **kwargs)
