import os


class Config:
    # Telegram
    # Get these from https://my.telegram.org/apps
    TELEGRAM_API_ID = os.getenv("TELEGRAM_API_ID")
    TELEGRAM_API_HASH = os.getenv("TELEGRAM_API_HASH")
    TELEGRAM_PHONE = os.getenv("TELEGRAM_PHONE")

    # --- AI Configuration ---

    # Embedding Settings
    # Provider: 'local' (HuggingFace), 'openai', 'ollama', 'fastembed'
    EMBEDDING_PROVIDER = os.getenv("EMBEDDING_PROVIDER", "local").lower()
    # Model: "BAAI/bge-small-en-v1.5" (local), "text-embedding-3-small" (openai)
    EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "BAAI/bge-small-en-v1.5")

    # LLM Settings
    # Provider: 'openrouter', 'ollama', 'local'
    LLM_PROVIDER = os.getenv("LLM_PROVIDER", "openrouter").lower()
    LLM_MODEL = os.getenv("LLM_MODEL") or os.getenv(f"{LLM_PROVIDER.upper()}_MODEL")
    if not LLM_MODEL and LLM_PROVIDER in ("local", "ollama", "openai"):
        LLM_MODEL = os.getenv("HF_MODEL_TEXT", "Qwen/Qwen2.5-Coder-7B-Instruct")
    CONTEXT_WINDOW = int(os.getenv("CONTEXT_WINDOW", "60000"))

    # Credentials (Unified)
    # For OpenAI/OpenRouter, use LLM_API_KEY. For Ollama, usually empty.
    LLM_API_KEY = os.getenv("LLM_API_KEY") or os.getenv(
        f"{LLM_PROVIDER.upper()}_API_KEY"
    )
    LLM_API_BASE = os.getenv("LLM_API_BASE") or os.getenv(
        f"{LLM_PROVIDER.upper()}_API_BASE"
    )

    # Fallback defaults
    if not LLM_API_BASE:
        match LLM_PROVIDER:
            case "openrouter":
                LLM_API_BASE = "https://openrouter.ai/api/v1"
            case "groq":
                LLM_API_BASE = "https://api.groq.com/openai/v1"
            case "ollama" | "local":
                LLM_API_BASE = "http://localhost:11434/v1"
                if not LLM_API_KEY:
                    LLM_API_KEY = "ollama"
            case _:
                pass

    # Database
    POSTGRES_DSN = os.getenv(
        "POSTGRES_DSN",
        "postgresql://summagram:fYfzQ9qdv2qLYYyD3jOF0z7yc2PyFVIFj57LrJI%2BJ50%3D@localhost:8432/summagram",
    )
    CHROMA_DB_PATH = os.getenv("CHROMA_DB_PATH", "./chroma_data")
    CHROMA_DB_IP = os.getenv("CHROMA_DB_IP", "localhost")
    CHROMA_DB_PORT = os.getenv("CHROMA_DB_PORT", "8000")

    # Calendar
    CALDAV_URL = os.getenv("CALDAV_URL")
    CALDAV_USERNAME = os.getenv("CALDAV_USERNAME")
    CALDAV_PASSWORD = os.getenv("CALDAV_PASSWORD")

    # Service Links & Orchestration
    ORCHESTRATOR_URL = os.getenv(
        "ORCHESTRATOR_URL", "http://model-orchestrator:8000/v1"
    )
    LLM_SERVER_URL = os.getenv("LLM_SERVER_URL", ORCHESTRATOR_URL)
    VISION_SERVER_URL = os.getenv("VISION_SERVER_URL", ORCHESTRATOR_URL)
    AUDIO_SERVER_URL = os.getenv("AUDIO_SERVER_URL", ORCHESTRATOR_URL)
    ETL_URL = os.getenv("ETL_URL", "http://localhost:8000")
    BACKEND_URL = os.getenv("BACKEND_URL", "http://localhost:8003")
    FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:3000")
    MEDIA_BASE_URL = os.getenv("MEDIA_BASE_URL", "/media")

    VISION_PROVIDER = os.getenv("VISION_PROVIDER", "local").lower()
    OLLAMA_VISION_MODEL = os.getenv("OLLAMA_VISION_MODEL", "llava:7b")

    # App Settings
    DISCOVERY_DAYS = int(os.getenv("DISCOVERY_DAYS", "90"))

    # NLP Preprocessing Pipeline
    # Master switch: enables deterministic NLP pre-processing before LLM intent extraction.
    # The existing 3-stage session agent remains active when this is False.
    NLP_PIPELINE_ENABLED = os.getenv("NLP_PIPELINE_ENABLED", "true").lower() == "true"
    # Enable lang-uk/roberta-large-ner-uk transformer for Ukrainian NER.
    # Requires model download (~1.3GB) and is slower on CPU.
    NLP_LANGUK_NER_ENABLED = os.getenv("NLP_LANGUK_NER_ENABLED", "true").lower() == "true"
    # Attach full pipeline trace to result (useful for debugging).
    NLP_RETURN_TRACE = os.getenv("NLP_RETURN_TRACE", "false").lower() == "true"

    # Local Inference Settings
    VLLM_GPU_UTILIZATION = float(os.getenv("VLLM_GPU_UTILIZATION", "0.7"))
    HF_MODEL_TEXT = os.getenv("HF_MODEL_TEXT", "Qwen/Qwen2.5-Coder-7B-Instruct")
    HF_MODEL_MEDIA = os.getenv("HF_MODEL_MEDIA", "HuggingFaceTB/SmolVLM2-2.2B-Instruct")
    HF_MODEL_AUDIO = os.getenv("HF_MODEL_AUDIO", "openai/whisper-tiny")
    MAX_CONTEXT_LEN = int(os.getenv("MAX_CONTEXT_LEN", "8192"))

    # CORS
    CORS_ORIGINS = [o.strip() for o in os.getenv("CORS_ORIGINS", "*").split(",")]

    # OpenTelemetry
    OTEL_ENABLED = os.getenv("OTEL_ENABLED", "false").lower() == "true"
    OTEL_EXPORTER_OTLP_ENDPOINT = os.getenv(
        "OTEL_EXPORTER_OTLP_ENDPOINT", "http://localhost:4317"
    )

    # Language & Translation
    # Languages that the user understands and does not need translation for (comma-separated)
    SUPPORTED_LANGUAGES = os.getenv("SUPPORTED_LANGUAGES", "ru,en,uk").split(",")
    # Languages for which a translation can be suggested (comma-separated)
    PROPOSE_TRANSLATION_FOR = os.getenv("PROPOSE_TRANSLATION_FOR", "en").split(",")
    # Default language for translations if not the query language
    DEFAULT_TRANSLATION_LANGUAGE = os.getenv("DEFAULT_TRANSLATION_LANGUAGE", "ru")

    @classmethod
    def get_safe_dict(cls) -> dict:
        """Returns a configuration dictionary with secrets masked."""
        safe_dict = {}
        for k, v in vars(cls).items():
            if k.startswith("_") or callable(v) or isinstance(v, classmethod):
                continue
            # Mask sensitive values
            if (
                isinstance(v, str)
                and v
                and any(
                    secret in k.upper()
                    for secret in [
                        "KEY",
                        "HASH",
                        "SECRET",
                        "TOKEN",
                        "PASSWORD",
                        "PHONE",
                    ]
                )
            ):
                safe_dict[k] = "***MASKED***"
            else:
                safe_dict[k] = v
        return safe_dict
