import logging
from llama_index.llms.openai_like import OpenAILike
from shared.config import Config

logger = logging.getLogger(__name__)


class LocalInferenceService:
    _instance = None
    _text_llm: OpenAILike = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(LocalInferenceService, cls).__new__(cls)
        return cls._instance

    @property
    def text_llm(self):
        if self._text_llm is None:
            self._text_llm = OpenAILike(
                api_base=f"{Config.ORCHESTRATOR_URL}/v1",
                model=Config.HF_MODEL_TEXT,
                api_key="sk-no-key-required",
                max_tokens=2048,
                timeout=300.0,
            )
        return self._text_llm

    async def generate_text(
        self,
        prompt: str,
        system_prompt: str = None,
        max_tokens: int = 2048,
        temperature: float = 0.7,
    ) -> str:
        """
        Generates text using the remote SGLang / orchestrator container.
        """
        response = await self.text_llm.acomplete(prompt)
        return response.text

    async def stream_generate_text(
        self, prompt: str, max_tokens: int = 2048, temperature: float = 0.7
    ):
        """
        Generates text streamingly using the remote SGLang.
        """
        llm = OpenAILike(
            api_base=f"{Config.ORCHESTRATOR_URL}/v1",
            model=Config.HF_MODEL_TEXT,
            api_key="sk-no-key-required",
            max_tokens=max_tokens,
            temperature=temperature,
            timeout=300.0,
        )
        response_gen = await llm.astream_complete(prompt)
        async for chunk in response_gen:
            if chunk.delta:
                yield chunk.delta

    def analyze_image(
        self, image_path: str, prompt: str = "Describe this image in detail."
    ) -> str:
        """
        Analyzes an image using the vision model running in SGLang via orchestrator.
        Note: OpenAILike doesn't officially wrap structured vision messages perfectly out of the box for all scenarios,
        so we might use httpx directly if needed, but doing async httpx.
        """
        import httpx
        import base64

        def encode_image(img_path):
            with open(img_path, "rb") as image_file:
                return base64.b64encode(image_file.read()).decode("utf-8")

        base64_image = encode_image(image_path)

        payload = {
            "model": "openai/clip-vit-base-patch32",
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/jpeg;base64,{base64_image}"
                            },
                        },
                    ],
                }
            ],
            "max_tokens": 500,
        }

        # Uses the orchestrator base directly
        try:
            # SGLang vision API usually available at Chat completions
            response = httpx.post(
                f"{Config.ORCHESTRATOR_URL}/v1/chat/completions",
                json=payload,
                timeout=60.0,
            )
            response.raise_for_status()
            data = response.json()
            return data["choices"][0]["message"]["content"]
        except Exception as e:
            logger.error(f"Failed to analyze image via SGLang: {e}")
            return "Image analysis failed."
