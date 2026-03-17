import os
import asyncio
import base64
import logging
import json
import shutil
import tempfile
import torch

from shared.config import Config
from backend.prompts import Prompts
from backend.models import (
    AudioTranscriptionResponse,
    ImageAnalysisResult,
    ImageAnalysisResponse,
    PDFAnalysisResponse,
    VideoAnalysisRequest,
    VideoAnalysisResult,
)
from backend.video_utils import (
    resize_image_smart,
    extract_audio,
    extract_keyframes_scene_detection,
    extract_keyframes_fixed_fps,
)

from backend.import_check import check_optional_imports

check_optional_imports()
import ollama  # noqa: E402
import kreuzberg  # noqa: E402
from openai import AsyncOpenAI  # noqa: E402

logger = logging.getLogger(__name__)


def encode_image_base64(image_path: str) -> str:
    with open(image_path, "rb") as image_file:
        return base64.b64encode(image_file.read()).decode("utf-8")


class LocalInferenceService:
    _instance = None
    _embed_model = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(LocalInferenceService, cls).__new__(cls)
        return cls._instance

    @property
    def vision_client(self):
        return AsyncOpenAI(
            base_url=Config.VISION_SERVER_URL, api_key="sk-no-key-required"
        )

    @property
    def audio_client(self):
        return AsyncOpenAI(
            base_url=Config.AUDIO_SERVER_URL, api_key="sk-no-key-required"
        )

    def shutdown(self):
        logger.info("LocalInferenceService shutdown complete.")

    async def generate_text(
        self,
        prompt: str,
        system_prompt: str = "",
        max_tokens: int = 2048,
        temperature: float = 0.3,
    ) -> str:
        from backend.sglang_client import generate_text as sglang_generate_text

        return await sglang_generate_text(
            prompt=prompt,
            system_prompt=system_prompt,
            max_tokens=max_tokens,
            temperature=temperature,
        )

    async def generate_json(
        self,
        prompt: str,
        json_schema: dict,
        system_prompt: str = "",
        max_tokens: int = 2048,
        temperature: float = 0.1,
    ) -> str:
        from backend.sglang_client import generate_json as sglang_generate_json

        return await sglang_generate_json(
            prompt=prompt,
            json_schema=json_schema,
            system_prompt=system_prompt,
            max_tokens=max_tokens,
            temperature=temperature,
        )

    async def stream_generate_text(
        self,
        prompt: str,
        system_prompt: str = "",
        max_tokens: int = 2048,
        temperature: float = 0.7,
    ):
        from backend.sglang_client import stream_generate_text as sglang_stream

        async for chunk in sglang_stream(
            prompt=prompt,
            system_prompt=system_prompt,
            max_tokens=max_tokens,
            temperature=temperature,
        ):
            yield chunk

    async def generate_text_from_messages(
        self, messages: list, max_tokens: int = 2048, temperature: float = 0.3
    ) -> str:
        from backend.sglang_client import generate_text_from_messages as sglang_messages

        return await sglang_messages(
            messages=messages, max_tokens=max_tokens, temperature=temperature
        )

    async def stream_generate_text_from_messages(
        self, messages: list, max_tokens: int = 2048, temperature: float = 0.7
    ):
        from backend.sglang_client import (
            stream_generate_text_from_messages as sglang_stream_messages,
        )

        async for chunk in sglang_stream_messages(
            messages=messages, max_tokens=max_tokens, temperature=temperature
        ):
            yield chunk

    _IMAGE_TYPE_VALID = frozenset({"selfie", "meme", "generic", "document"})
    _OCR_EMPTY_MARKERS = frozenset({"[NO_TEXT]", "", "none", "n/a"})

    def _normalize_image_type(self, raw: str) -> str:
        raw = raw.strip().lower()
        first = (raw.split()[0] or "") if raw else ""
        if first in self._IMAGE_TYPE_VALID:
            return first
        for v in self._IMAGE_TYPE_VALID:
            if v in raw:
                return v
        return "generic"

    def _clean_ocr_text(self, raw: str) -> str:
        text = raw.strip()
        if (
            not text
            or text.upper() == "[NO_TEXT]"
            or text.lower() in self._OCR_EMPTY_MARKERS
        ):
            return ""
        return text

    def _parse_structured_analysis(self, json_str: str) -> ImageAnalysisResult | None:
        try:
            data = json.loads(json_str)
            return ImageAnalysisResult(**data)
        except Exception as e:
            logger.error(
                "Failed to parse structured analysis: %s | Raw: %s", e, json_str
            )
            return None

    async def _analyze_image_openai(
        self, image_path: str, prompt: str | None = None
    ) -> str:
        if prompt is None:
            prompt = Prompts.IMAGE_ANALYSIS_TEMPLATE

        logger.info(f"Analyzing image (OpenAI API): {image_path}")
        base64_image = await asyncio.to_thread(encode_image_base64, image_path)

        messages = [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {
                        "type": "image_url",
                        "image_url": {"url": f"data:image/jpeg;base64,{base64_image}"},
                    },
                ],
            }
        ]

        try:
            response = await self.vision_client.chat.completions.create(
                model="default",
                messages=messages,  # type: ignore
                max_tokens=600,
                temperature=0.4,
            )
            return response.choices[0].message.content or ""
        except Exception as e:
            logger.error(f"Error calling vision API: {e}")
            raise e

    async def _get_ocr_text_if_needed(self, image_path: str, image_type: str) -> str:
        if not any(t in image_type for t in ["meme", "document", "text"]):
            return ""
        raw = await self._analyze_image_openai(image_path, Prompts.STAGE_3_OCR)
        text = self._clean_ocr_text(raw)
        logger.info("Extracted OCR text length: %s", len(text))
        return text

    async def analyze_image(
        self, image_path: str, prompt: str | None = None
    ) -> ImageAnalysisResponse:
        image_path = await asyncio.to_thread(resize_image_smart, image_path)

        raw_type = await self._analyze_image_openai(
            image_path, Prompts.STAGE_1_CLASSIFY
        )
        image_type = self._normalize_image_type(raw_type)
        logger.info("Image classification: %s", image_type)

        description = await self._analyze_image_openai(
            image_path, Prompts.STAGE_2_DESCRIBE
        )
        logger.info("Image description length: %s", len(description))

        ocr_text = await self._get_ocr_text_if_needed(image_path, image_type)

        synthesis_prompt = Prompts.STAGE_4_SYNTHESIS.format(
            ocr_text=ocr_text,
            description=description,
            image_type=image_type,
        )
        structured_json_str = await self.generate_json(
            prompt=synthesis_prompt,
            json_schema=ImageAnalysisResult.model_json_schema(),
            system_prompt="You are a professional image analysis synthesizer.",
            max_tokens=512,
        )
        structured_analysis = self._parse_structured_analysis(structured_json_str)

        return ImageAnalysisResponse(
            description=description,
            structured_analysis=structured_analysis,
        )

    async def analyze_video(self, request: VideoAnalysisRequest) -> VideoAnalysisResult:
        video_path = request.video_path
        if not os.path.exists(video_path):
            raise FileNotFoundError(f"Video not found: {video_path}")

        temp_dir = tempfile.mkdtemp(prefix="video_analysis_")
        audio_path = os.path.join(temp_dir, "audio.mp3")
        keyframes_dir = os.path.join(temp_dir, "keyframes")
        os.makedirs(keyframes_dir, exist_ok=True)

        try:
            logger.info(f"Starting video analysis for {video_path}")

            # Extract audio
            audio_success = await asyncio.to_thread(
                extract_audio, video_path, audio_path
            )

            # Sample visual keyframes
            if request.use_scene_detection:
                keyframes = await asyncio.to_thread(
                    extract_keyframes_scene_detection, video_path, keyframes_dir
                )
            else:
                keyframes = await asyncio.to_thread(
                    extract_keyframes_fixed_fps,
                    video_path,
                    keyframes_dir,
                    request.adaptive_fps,
                )

            max_frames = 10
            stride = max(1, len(keyframes) // max_frames)

            keyframes_list = list(keyframes)
            sampled_keyframes = keyframes_list[::stride][:max_frames]

            transcript_task = (
                self.transcribe_audio(audio_path)
                if audio_success
                else asyncio.sleep(0, result=None)
            )

            async def describe_frame(kf_path):
                resized_path = await asyncio.to_thread(resize_image_smart, kf_path)
                desc = await self._analyze_image_openai(
                    resized_path, Prompts.VIDEO_FRAME_DESCRIBE
                )
                return desc

            results_list = await asyncio.gather(
                transcript_task, *[describe_frame(kf) for kf in sampled_keyframes]
            )

            transcript_res = results_list[0]
            visual_descriptions = results_list[1:]

            visual_logs = ""
            for i, desc in enumerate(visual_descriptions):
                visual_logs += f"Sequence {i + 1}: {desc}\n"

            transcript_text = (
                transcript_res.transcript
                if transcript_res
                else "No audio transcription available."
            )

            logger.info("🎬 Fusion Stage 1: Creating chronology...")
            timeline_prompt = Prompts.VIDEO_FUSION_STEP_1_TIMELINE.format(
                visual_logs=visual_logs, transcript=transcript_text
            )
            chronology = await self.generate_text(
                prompt=timeline_prompt, max_tokens=1000
            )

            logger.info("🎬 Fusion Stage 2: Synthesizing final JSON...")
            final_prompt = Prompts.VIDEO_FUSION_STEP_2_SUMMARY.format(
                chronology=chronology
            )

            structured_json_str = await self.generate_json(
                prompt=final_prompt,
                json_schema=VideoAnalysisResult.model_json_schema(),
            )

            try:
                data = json.loads(structured_json_str)
                if not data.get("transcript"):
                    data["transcript"] = transcript_text
                result = VideoAnalysisResult(**data)
            except Exception as e:
                logger.error(
                    f"Failed to parse video fusion: {e} | Raw: {structured_json_str}"
                )
                result = VideoAnalysisResult(
                    summary=f"Video summary (failed fusion): {chronology[:300]}...",
                    transcript=transcript_text,
                    segments=[],
                )

            return result

        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

    async def transcribe_audio(self, audio_path: str) -> AudioTranscriptionResponse:
        logger.info(f"Transcribing audio: {audio_path}")

        try:
            with open(audio_path, "rb") as audio_file:
                response = await self.audio_client.audio.transcriptions.create(
                    model="whisper-1", file=audio_file, response_format="verbose_json"
                )

            raw_text = response.text or ""
            # Fallbacks if metadata missing in some server implementations
            language = getattr(response, "language", "en")
            duration = getattr(response, "duration", 0.0)

            # Simple cleanup if long enough
            cleaned_text = None
            if len(raw_text.split()) > 5:
                try:
                    cleanup_prompt = Prompts.TRANSCRIPT_CLEANUP.format(text=raw_text)
                    cleaned_text = await self.generate_text(
                        prompt=cleanup_prompt,
                        max_tokens=len(raw_text) * 2 + 100,
                        temperature=0.3,
                    )
                    cleaned_text = cleaned_text.strip()
                    if not cleaned_text:
                        cleaned_text = raw_text
                except Exception as e:
                    logger.error(f"Failed to clean transcript: {e}")
                    cleaned_text = raw_text
            else:
                cleaned_text = raw_text

            translation = None
            if language.lower() not in ["ru", "uk", "russian", "ukrainian"]:
                try:
                    translation_prompt = Prompts.AUDIO_TRANSLATION.format(
                        text=cleaned_text
                    )
                    translation = await self.generate_text(
                        prompt=translation_prompt,
                        max_tokens=int(len(cleaned_text) * 2 + 100),
                        temperature=0.3,
                    )
                    translation = translation.strip()
                except Exception as e:
                    logger.error(f"Failed to translate transcript: {e}")

            return AudioTranscriptionResponse(
                transcript=raw_text,
                language=language,
                duration=duration,
                language_probability=1.0,
                transcription_confidence=1.0,
                cleaned_transcript=cleaned_text,
                translation=translation,
            )
        except Exception as e:
            logger.error(f"Failed to transcribe audio via API: {e}")
            raise e

    async def analyze_pdf_with_kreuzberg(self, pdf_path: str) -> PDFAnalysisResponse:
        logger.info(f"Analyzing document with kreuzberg: {pdf_path}")
        try:
            result = await kreuzberg.extract_file(pdf_path)
            metadata = dict(result.metadata) if result.metadata else {}
            tables = [
                vars(t) if hasattr(t, "__dict__") else t for t in (result.tables or [])
            ]
            images = [
                vars(i) if hasattr(i, "__dict__") else i for i in (result.images or [])
            ]
            page_count = result.get_page_count()

            return PDFAnalysisResponse(
                text=result.content,
                metadata=metadata,
                tables=tables,
                images=images,
                page_count=page_count,
            )
        except Exception as e:
            logger.error(f"Failed to analyze document with kreuzberg: {e}")
            raise e

    async def analyze_image_with_llava(
        self, image_path: str, prompt: str | None = None
    ) -> str:
        if prompt is None:
            prompt = Prompts.IMAGE_ANALYSIS_TEMPLATE

        logger.info(f"Analyzing image with {Config.OLLAMA_VISION_MODEL}: {image_path}")
        try:
            result = await asyncio.to_thread(
                ollama.chat,
                model=Config.OLLAMA_VISION_MODEL,
                messages=[{"role": "user", "content": prompt, "images": [image_path]}],
            )
            return result["message"]["content"]
        except Exception as e:
            logger.error(
                f"Failed to analyze image with {Config.OLLAMA_VISION_MODEL}: {e}"
            )
            raise e

    def initialize_embedding_model(self):
        if self._embed_model is not None:
            return

        from llama_index.embeddings.huggingface import HuggingFaceEmbedding

        logger.info(f"Initializing Embedding Model: {Config.EMBEDDING_MODEL}")

        device = "cpu"
        try:
            if torch.cuda.is_available():
                device = "cuda"
        except ImportError:
            pass

        self._embed_model = HuggingFaceEmbedding(
            model_name=Config.EMBEDDING_MODEL,
            cache_folder="/app/models_cache",
            device=device,
        )

    async def get_embeddings(self, texts: list[str]) -> list[list[float]]:
        if self._embed_model is None:
            await asyncio.to_thread(self.initialize_embedding_model)

        result = await asyncio.to_thread(
            self._embed_model.get_text_embedding_batch, texts
        )
        return result
