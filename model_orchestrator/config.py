"""Model orchestrator configuration.

All env-variable lookups and URL definitions live here.
SGLang / Docker specifics have been removed; the orchestrator now controls
three always-running vLLM processes via HTTP sleep/wake endpoints.
"""

import os

# ---------------------------------------------------------------------------
# Environment variables
# ---------------------------------------------------------------------------

TEXT_VLLM_URL: str = os.getenv("TEXT_VLLM_URL", "http://text-vllm:8000")
VISION_VLLM_URL: str = os.getenv("VISION_VLLM_URL", "http://vision-vllm:8000")
WHISPER_DEFAULT_URL: str = "http://audio-whisper:8000"


def _resolve_whisper_url(default: str = WHISPER_DEFAULT_URL) -> str:
    return os.getenv(
        "AUDIO_WHISPER_URL",
        os.getenv("WHISPER_URL", os.getenv("AUDIO_URL", default)),
    )


# AUDIO_WHISPER_URL matches docker-compose; fall back to WHISPER_URL/AUDIO_URL for legacy setups.
WHISPER_BACKEND_URL: str = _resolve_whisper_url()

AUDIO_VLLM_URL: str = os.getenv("AUDIO_VLLM_URL", WHISPER_BACKEND_URL)

VLLM_API_KEY: str = os.getenv("VLLM_API_KEY", "local-dev-key")

# Modes that expose vLLM dev control endpoints: /sleep, /wake_up, /is_sleeping.
SLEEP_ENDPOINT_MODES: set[str] = {
    mode.strip()
    for mode in os.getenv("SLEEP_ENDPOINT_MODES", "text,vision").split(",")
    if mode.strip()
}

# ---------------------------------------------------------------------------
# Mode → base URL registry  (imported by services.py and router.py)
# ---------------------------------------------------------------------------

MODE_URLS: dict[str, str] = {
    "text": TEXT_VLLM_URL,
    "vision": VISION_VLLM_URL,
    "audio": AUDIO_VLLM_URL,
}

# ---------------------------------------------------------------------------
# Whisper / ASR — separate path for /v1/audio/transcriptions (NOT vLLM sleep/wake)
# ---------------------------------------------------------------------------
