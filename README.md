# Summagram: Modular Agentic RAG

## Project Overview
Summagram is a modular Agentic RAG (Retrieval-Augmented Generation) application designed to solve the problem of information overload in Telegram. By syncing and indexing messages from your personal chats, groups, and channels, it allows you to query your own data using natural language.

### Key Features
*   **Telegram Sync**: Seamlessly download and index messages from your Telegram account (personal chats, groups, and channels).
*   **Agentic RAG**: Uses a hybrid search approach (combining keyword and vector search) to answer questions based on your chat history, empowered by local, robust AI services.
*   **Event Extraction**: Automatically analyzes messages to extract and store potential calendar events.
*   **Multimodal Analysis**: Processes images, videos, and audio locally through dedicated backend inference engines.
*   **Visual Dashboard**: A Streamlit-based UI to view statistics, upcoming events, and manage data sources.
*   **Privacy-Focused**: Runs completely locally using Docker; your personal data and media stay on your machine.

---

## How to Run

### Option 1: Docker (Recommended)
The easiest way to run Summagram is using Docker Compose.

1.  **Clone the repository**:
    ```bash
    git clone <repository-url>
    cd summagram
    ```

2.  **Start the services**:
    ```bash
    docker-compose up --build
    ```

3.  **Access the App**:
    Open your browser and navigate to `http://localhost:8501`.

### Option 2: Local Development (recommended for dev)
If you prefer running it natively or need to debug:

1.  **Prerequisites**:
    *   Python 3.11+
    *   [uv](https://github.com/astral-sh/uv) (recommended)
    *   An active Telegram account

2.  **Setup Environment & Run**:
    ```bash
    # Install dependencies and sync
    uv sync
    
    # Run the Application
    uv run streamlit run app.py
    ```

---

## Configuration
Summagram uses environment variables for configuration. Create a `.env` file in the root directory.

### Essential Settings

**1. Telegram Credentials**
To connect to Telegram, you need an API ID and Hash. Get them from [my.telegram.org/apps](https://my.telegram.org/apps).
```env
TELEGRAM_API_ID=your_api_id
TELEGRAM_API_HASH=your_api_hash
TELEGRAM_PHONE=+1234567890  # Your phone number with country code
```

**2. Local AI & Analytics Resources**
The app leverages robust local models running in Docker. Ensure you have the hardware to support them (NVIDIA GPU recommended for fast inference).
```env
# Point to the local orchestrator/SGLang cluster
LLM_API_BASE=http://backend:8000/v1
LLM_SERVER_URL=http://sglang:30000/v1
HF_HOME=/app/models_cache
```

**3. External LLM Provider (Optional)**
If not using the default local `sglang` stack, you can override the AI provider logic in your `.env`. Examples:

*   **OpenRouter**:
    ```env
    LLM_PROVIDER=openrouter
    LLM_API_KEY=your_openrouter_key
    ```

*   **OpenAI**:
    ```env
    LLM_PROVIDER=openai
    LLM_API_KEY=your_openai_key
    LLM_MODEL=gpt-4o
    ```

*   **Ollama (Local Custom)**:
    ```env
    LLM_PROVIDER=ollama
    LLM_API_BASE=http://localhost:11434/v1
    LLM_MODEL=llama3.2
    ```

### Optional Settings
*   `EMBEDDING_PROVIDER`: Defaults to `local` (HuggingFace). Set to `openai` to use OpenAI embeddings.
*   `DB_PATH`: Path to the SQLite database (default: `summagram.db`).
*   `CHROMA_DB_PATH`: Path to the local vector store (default: `./chroma_data`).

---

## Usage Guide

1.  **Connect & Sync**:
    *   Open the app at `http://localhost:8501`.
    *   Go to the **Sources & Control** tab.
    *   Click **Open Chat Manager** to load your Telegram chats.
    *   Select the chats (Personal, Groups, Channels) you want to index.
    *   Click **Start Sync Now**. The app will fetch recent messages and index them.

2.  **Query Your Data**:
    *   Go to the **Chat** tab.
    *   Ask questions like:
        *   *"What did John say about the project meeting?"*
        *   *"Are there any upcoming deadlines mentioned in the 'Work' group?"*
        *   *"Summarize the discussion about the new feature."*

3.  **View Events**:
    *   The **Dashboard** tab shows a list of automatically extracted upcoming events found in your messages.
