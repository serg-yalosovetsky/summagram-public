import time
from loguru import logger
from utils import timer, monitor_perf

from shared.config import Config
from llm_setup import setup_llm_provider  # Alias to minimize code change
from etl.processing.telegram_etl import transform_telegram_docs_to_nodes

with timer("indexer imports (lazy)"):
    # Heavy imports moved to functions
    pass

# Global Settings Setup
# Removed global call to setup_llm_provider() to fix slow startup
# It will be called lazily when needed.

STORAGE_DIR = "./storage"  # Still used for Property Graph or other persistence if needed, but Vector is now Chroma


def get_chroma_client():
    import chromadb

    # If running in Docker, we might use HTTP client. For now let's use persistent client or http based on config.
    if Config.CHROMA_DB_IP and Config.CHROMA_DB_IP != "localhost":
        # Remote/Docker (HttpClient)
        logger.info(
            f"Connecting to ChromaDB at {Config.CHROMA_DB_IP}:{Config.CHROMA_DB_PORT}"
        )
        return chromadb.HttpClient(
            host=Config.CHROMA_DB_IP, port=int(Config.CHROMA_DB_PORT)
        )
    else:
        # Local persistent
        logger.info(f"Connecting to local ChromaDB at {Config.CHROMA_DB_PATH}")
        return chromadb.PersistentClient(path=Config.CHROMA_DB_PATH)




@monitor_perf
def get_index():
    """
    Loads/Creates the index using ChromaDB as the vector store.
    """
    from llama_index.core import VectorStoreIndex, StorageContext
    from llama_index.vector_stores.chroma import ChromaVectorStore

    start_time = time.time()
    setup_llm_provider()  # Lazy init

    # Initialize Chroma
    db = get_chroma_client()
    chroma_collection = db.get_or_create_collection("summagram_chats")
    vector_store = ChromaVectorStore(chroma_collection=chroma_collection)

    # Create Storage Context with Chroma
    storage_context = StorageContext.from_defaults(vector_store=vector_store)

    # We can load the index from this storage context.
    # Since Chroma persists data itself, simple VectorStoreIndex.from_vector_store is usually enough
    # If it's a new run, it will just wrap the existing store.

    index = VectorStoreIndex.from_vector_store(
        vector_store, storage_context=storage_context
    )

    logger.info(f"Index retrieval/initialization took {time.time() - start_time:.2f}s")
    return index


@monitor_perf
def update_index(docs):
    """
    Ingests GenericDocuments into the Vector Store using the new ETL pipeline.
    docs: List[GenericDocument]
    """
    if not docs:
        return

    setup_llm_provider()  # Lazy init

    logger.info(f"Indexing {len(docs)} documents into ChromaDB...")

    # 1. Transform to Nodes (ETL w/ Context Windowing)
    nodes = transform_telegram_docs_to_nodes(docs, context_window_size=3)

    logger.info(f"Generated {len(nodes)} nodes with context windowing.")

    # 2. Insert into Index (Chroma)
    index = get_index()
    index.insert_nodes(nodes)

    # 3. Insert into Property Graph (Experimental)
    # Using SimplePropertyGraphStore (persisted locally)

    # We use the same nodes.
    # Note: PropertyGraph creation can be slow due to LLM extraction.
    # For now, we might want to skip or make it optional/async.
    # But sticking to plan:

    logger.info("Indexing complete.")


def get_chat_engine(system_prompt_suffix: str = ""):
    """
    Returns a chat engine interface for the index.
    """
    index = get_index()

    base_prompt = (
        "You are a personal assistant with access to the user's Telegram chat history. "
        "Your goal is to answer questions accurately based on the provided context.\n\n"
        "### IMPORTANT CONTEXT GUIDELINES:\n"
        "1. **Identity**: The name 'Me' in the chat logs refers to the USER (the person you are talking to). "
        "Any message starting with '[TIMESTAMP] Me' was sent by the user.\n"
        "2. **Contacts**: Other names like 'Хурма', 'Лев', etc., are the user's contacts. "
        "If a message says '[TIMESTAMP] Хурма', it means it was RECEIVED from that contact.\n"
        "3. **Format**: Chat logs follow the format: `[TIMESTAMP] SENDER (in CHAT_TITLE): CONTENT`.\n"
        "4. **Multimedia**: You may see markers like `[PHOTO]`, `[AUDIO]`, `[VIDEO]`. "
        "If a description follows (e.g., `[PHOTO] A cat sitting on a mat`), use it. "
        "If it only says `[AUDIO]` without text, acknowledge that you can see an audio message exists but you don't have the transcription yet.\n"
        "5. **Language**: Respond in the same language as the user's query unless asked otherwise."
    )

    final_prompt = f"{base_prompt}\n\n{system_prompt_suffix}"

    # "context" mode uses retrieval to answer.
    return index.as_chat_engine(chat_mode="context", system_prompt=final_prompt)


def get_visual_collection():
    """
    Returns the ChromaDB collection for visual search.
    """
    db = get_chroma_client()
    return db.get_or_create_collection(Config.VISUAL_SEARCH_COLLECTION)


@monitor_perf
def search_visual(query_embedding: list[float], n_results: int = 5):
    """
    Searches the visual embedding collection for similar frames.
    """
    collection = get_visual_collection()
    results = collection.query(query_embeddings=[query_embedding], n_results=n_results)
    return results
