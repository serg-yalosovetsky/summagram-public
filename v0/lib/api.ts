// API Client for Summagram Backend\n
// API Client Types

export interface Chat {
    id: number
    source_id: number
    title: string
    description?: string
    message_count_me: number
    importance_score: number
    last_analyzed_at?: string
    status?: "active" | "idle" | "completed" // Derived
}

export interface ReferencedMessage {
    chat_id: number
    doc_id: string
    content: string
    media_url?: string | null
    media_type?: string | null
    description?: string | null
    sender_name?: string | null
}

export interface Message {
    role: "user" | "assistant"
    content: string
    timestamp: string
    source_id?: number | string
    referenced_message?: ReferencedMessage | null
}

export interface Session {
    id: string
    title: string
    created_at: string
    updated_at: string
    context_chat_id?: number
}

export interface Document {
    doc_id: string
    source_id: string
    content: string
    timestamp: string
    metadata: any
}

export interface Config {
    HF_MODEL_TEXT: string
    HF_MODEL_MEDIA: string
    VISION_PROVIDER: string
    OLLAMA_VISION_MODEL: string
    EMBEDDING_MODEL: string
    [key: string]: any
}

export interface JobStatus {
    job_id: string
    status: "queued" | "running" | "completed" | "failed"
    progress: number
    message: string
    result?: any
    error?: string
}

// --- System Status ---

export interface GpuInfo {
    cuda_available: boolean
    gpu_name?: string
    memory_total_mb?: number
    memory_allocated_mb?: number
    memory_reserved_mb?: number
    memory_free_mb?: number
}

export interface ContainerMetrics {
    name: string
    cpu_perc: number
    mem_used_b: number
    mem_limit_b: number
    mem_perc: number
    vram_used_mib: number
    gpu_proc_count: number
}

export interface SystemStatus {
    queue: Record<string, number>
    total_pending: number
    current_model: string | null
    switching?: boolean
    available_modes?: string[]
    gpu: GpuInfo
    models_config: Record<string, string>
    containers: ContainerMetrics[]
}

export async function fetchSystemStatus(): Promise<SystemStatus> {
    const res = await fetch(`/api/system/status`)
    if (!res.ok) throw new Error("Failed to fetch system status")
    return res.json()
}

export function subscribeSystemStatus(
    onData: (status: SystemStatus) => void,
    onError?: (err: Event) => void,
): () => void {
    const host = typeof window !== "undefined" ? window.location.hostname : "localhost"
    const backendUrl = `http://${host}:8003/system/status/stream`

    const es = new EventSource(backendUrl)
    es.onmessage = (event) => {
        try {
            onData(JSON.parse(event.data))
        } catch (e) {
            console.error("Failed to parse SSE event data:", e)
        }
    }
    es.onerror = (event) => {
        console.error("SSE connection error:", event)
        onError?.(event)
    }
    return () => es.close()
}

// API Functions

export async function fetchChats(limit = 50, offset = 0): Promise<Chat[]> {
    const res = await fetch(`/api/chats?limit=${limit}&offset=${offset}`)
    if (!res.ok) throw new Error("Failed to fetch chats")
    return res.json()
}

export async function fetchChatMessages(chatId: number, limit = 50, offset = 0): Promise<Message[]> {
    const res = await fetch(`/api/chat/${chatId}/messages?limit=${limit}&offset=${offset}`)
    if (!res.ok) throw new Error("Failed to fetch messages")
    const rawMessages = await res.json()

    // Transform raw messages if necessary
    return rawMessages.map((msg: any) => ({
        role: msg.metadata?.sender_id ? (msg.metadata.sender_id === "me" ? "user" : "assistant") : "assistant", // Provisional logic
        content: msg.content,
        timestamp: new Date(msg.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
        source_id: msg.source_id
    }))
}

export async function sendMessage(chatId: number, content: string): Promise<{ user_message: Message, assistant_message: Message }> {
    console.log(`[API] Sending message to chat ${chatId}:`, content)
    const res = await fetch(`/api/chat/${chatId}/messages`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ content }),
    })
    if (!res.ok) {
        const error = await res.text()
        console.error(`[API] Failed to send message:`, error)
        throw new Error("Failed to send message")
    }
    const data = await res.json()
    console.log(`[API] Received response for chat ${chatId}:`, data)
    return data
}

// --- Session API ---

export async function fetchSessions(limit = 50, offset = 0): Promise<Session[]> {
    const res = await fetch(`/api/sessions?limit=${limit}&offset=${offset}`)
    if (!res.ok) throw new Error("Failed to fetch sessions")
    return res.json()
}

export async function createSession(id: string, title: string, context_chat_id?: number): Promise<Session> {
    const res = await fetch(`/api/sessions`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ id, title, context_chat_id }),
    })
    if (!res.ok) throw new Error("Failed to create session")
    return res.json()
}

export async function fetchSessionMessages(sessionId: string, limit = 50, offset = 0): Promise<Message[]> {
    const res = await fetch(`/api/session/${sessionId}/messages?limit=${limit}&offset=${offset}`)
    if (!res.ok) throw new Error("Failed to fetch session messages")
    const rawMessages = await res.json()
    return rawMessages.map((msg: any) => ({
        role: msg.metadata?.sender_id === "me" ? "user" : "assistant",
        content: msg.content,
        timestamp: new Date(msg.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
        source_id: msg.source_id,
        referenced_message: msg.metadata?.referenced_message ?? null,
    }))
}

export async function sendSessionMessage(sessionId: string, content: string, context_chat_id?: number): Promise<{ user_message: Message, assistant_message: Message }> {
    const res = await fetch(`/api/session/${sessionId}/messages`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ content, context_chat_id }),
    })
    if (!res.ok) {
        const bodyText = await res.text()
        let detail = ""
        try {
            const body = JSON.parse(bodyText)
            detail = body?.detail ?? ""
        } catch {
            detail = bodyText
        }
        const msg = detail ? `Failed to send session message: ${detail}` : `Failed to send session message (${res.status})`
        throw new Error(msg)
    }
    return res.json()
}

/**
 * Fire-and-forget: ask backend to pre-warm the text model.
 * Errors are silently ignored — this is best-effort.
 */
export function warmModel(mode: string = "text"): void {
    fetch(`/api/warm?mode=${mode}`, { method: "POST" }).catch(() => { })
}

export async function fetchDocuments(limit = 50, offset = 0, mediaType?: string): Promise<Document[]> {
    const params = new URLSearchParams({ limit: String(limit), offset: String(offset) })
    if (mediaType) params.set("media_type", mediaType)
    const res = await fetch(`/api/documents?${params}`)
    if (!res.ok) throw new Error("Failed to fetch documents")
    return res.json()
}

export type DocumentCounts = Record<string, number>

export async function fetchDocumentCounts(): Promise<DocumentCounts> {
    const res = await fetch(`/api/documents/counts`)
    if (!res.ok) throw new Error("Failed to fetch document counts")
    return res.json()
}

export async function fetchConfig(): Promise<Config> {
    const res = await fetch(`/api/config`)
    if (!res.ok) throw new Error("Failed to fetch config")
    return res.json()
}

export async function updateConfig(config: Partial<Config>): Promise<Config> {
    const res = await fetch(`/api/config`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(config),
    })
    if (!res.ok) throw new Error("Failed to update config")
    return (await res.json()).config
}

// --- Social Graph ---

export interface GraphNode {
    id: number
    label: string
    cluster: number
    message_count: number
}

export interface GraphEdge {
    source: number
    target: number
    weight: number
    edge_type: "similarity" | "interaction" | "both"
    interaction_count: number
}

export interface GraphData {
    nodes: GraphNode[]
    edges: GraphEdge[]
    node_count: number
    edge_count: number
    clusters: number[]
}

export interface TelegramDialog {
    id: number
    name: string
    type: "personal" | "group" | "channel" | "unknown"
    archived: boolean
    date: number
}

export async function fetchGraphData(): Promise<GraphData | null> {
    const res = await fetch(`/etl/graph/data`)
    if (res.status === 404) return null
    if (!res.ok) throw new Error("Failed to fetch graph data")
    return res.json()
}

export async function buildGraph(force = false): Promise<GraphData> {
    const res = await fetch(`/etl/graph/build?force_rebuild=${force}`, {
        method: "POST",
    })
    if (!res.ok) throw new Error("Failed to build graph")
    return res.json()
}

export async function reindexMedia(force = false, mediaTypes?: string[]): Promise<any> {
    const types = mediaTypes ?? ["photo", "audio", "document", "voice"]
    const res = await fetch(`/etl/reindex-media?force_reindex=${force}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
            media_types: types,
            force_reindex: force
        })
    })
    if (!res.ok) throw new Error("Failed to start media reindexing")
    return res.json()
}

export async function fetchJobStatus(jobId: string): Promise<JobStatus> {
    const res = await fetch(`/etl/jobs/${jobId}`)
    if (!res.ok) throw new Error("Failed to fetch job status")
    return res.json()
}

export function subscribeJobStatus(
    jobId: string,
    onData: (status: JobStatus) => void,
    onError?: (err: Event) => void,
): () => void {
    // Attempting to bypass Next.js proxy cache for EventSource by going direct to ETL port 8002
    const host = typeof window !== "undefined" ? window.location.hostname : "localhost"
    const etlUrl = `http://${host}:8002/jobs/stream/${jobId}`

    const es = new EventSource(etlUrl)
    es.onmessage = (event) => {
        try {
            onData(JSON.parse(event.data))
        } catch (e) {
            console.error("Failed to parse Job Status SSE event data:", e)
        }
    }
    es.onerror = (event) => {
        console.error("Job Status SSE connection error:", event)
        onError?.(event)
    }
    return () => es.close()
}

export async function fetchTelegramDialogs(): Promise<TelegramDialog[]> {
    const res = await fetch(`/etl/sources/telegram/dialogs`)
    if (!res.ok) {
        const data = await res.json().catch(() => ({}))
        const detail = data.detail != null
            ? (typeof data.detail === "string" ? data.detail : JSON.stringify(data.detail))
            : null
        const msg = detail ? `Failed to fetch Telegram dialogs: ${detail}` : `Failed to fetch Telegram dialogs (${res.status})`
        throw new Error(msg)
    }
    const data = await res.json()
    return data.dialogs
}

export async function submitTelegramJob(params: { chat_ids: number[], days_back: number }): Promise<{ job_id: string }> {
    const res = await fetch(`/etl/jobs/telegram`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ params })
    })
    if (!res.ok) throw new Error("Failed to submit Telegram sync job")
    return res.json()
}

export async function submitAnalyzeChatsJob(chatIds: number[]): Promise<{ job_id: string }> {
    const res = await fetch(`/etl/analyze-chats`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ chat_ids: chatIds })
    })
    if (!res.ok) throw new Error("Failed to submit analyze chats job")
    return res.json()
}

/**
 * Resolves a media file path to a public URL proxied by the frontend.
 */
export function getMediaUrl(doc: Document): string | null {
    const path = doc.metadata?.media?.path;
    if (!path) return null;

    // Path is stored as /app/storage/media/... on the backend
    // Frontend proxies /media/* to backend's StaticFiles mount
    const filename = path.split('/').pop();
    return filename ? `/media/${filename}` : null;
}

/**
 * Downloads media via fetch+blob to bypass Next.js rewrite issues with <a download>.
 */
export async function downloadMediaFile(doc: Document): Promise<void> {
    const url = getMediaUrl(doc);
    if (!url) return;

    const res = await fetch(url);
    if (!res.ok) throw new Error(`Download failed: ${res.status}`);

    const blob = await res.blob();
    const blobUrl = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = blobUrl;
    a.download = doc.metadata?.file_name || `download_${doc.doc_id}`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(blobUrl);
}

/**
 * Opens media in a new tab via fetch+blob to bypass Next.js rewrite issues.
 */
export async function openMediaFile(doc: Document): Promise<void> {
    const url = getMediaUrl(doc);
    if (!url) return;

    const res = await fetch(url);
    if (!res.ok) throw new Error(`Failed to load media: ${res.status}`);

    const blob = await res.blob();
    const blobUrl = URL.createObjectURL(blob);
    window.open(blobUrl, "_blank");
}
