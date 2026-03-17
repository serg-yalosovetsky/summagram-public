import time
from loguru import logger
from llama_index.core import Settings
from shared.config import Config
from utils import monitor_perf
from llama_index.embeddings.huggingface import HuggingFaceEmbedding
from services.llm_wrapper import LocalVLLM
from llama_index.llms.openai_like import OpenAILike


@monitor_perf
def setup_llm_provider():
    """
    Configures the global LlamaIndex Settings based on Config.
    """
    time0 = time.time()
    logger.info(
        f"Initializing LLM Provider settings... (LLM: {Config.LLM_PROVIDER}, Embed: {Config.EMBEDDING_PROVIDER})"
    )

    # 1. Embedding Model
    if Config.EMBEDDING_PROVIDER == "local":
        # cache_folder can be specified if needed
        Settings.embed_model = HuggingFaceEmbedding(
            model_name=Config.EMBEDDING_MODEL, cache_folder="./models_cache"
        )
    # Add ollama later if needed
    # Add ollama later if needed

    # 2. LLM
    # Unified OpenAILike setup for OpenRouter, Ollama, and Local
    # 2. LLM
    if Config.LLM_PROVIDER == "local":
        Settings.llm = LocalVLLM()
    elif Config.LLM_PROVIDER in ["openrouter", "ollama", "groq"]:
        Settings.llm = OpenAILike(
            model=Config.LLM_MODEL,
            api_key=Config.LLM_API_KEY,
            api_base=Config.LLM_API_BASE,
            is_chat_model=True,
            max_retries=3,
            reuse_client=True,
            context_window=Config.CONTEXT_WINDOW,
        )

    logger.info(f"LLM Provider configured: {Config.LLM_MODEL}")
    logger.info(f"LLM Provider initialization took {time.time() - time0:.2f}s")


_llm_initialized = False


def get_llm():
    """Returns the configured LLM instance."""
    global _llm_initialized
    if not _llm_initialized:
        setup_llm_provider()
        _llm_initialized = True
    return Settings.llm
