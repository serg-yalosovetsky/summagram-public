"use client"

import { useEffect, useState, useMemo } from "react"
import { motion } from "framer-motion"
import { ScrollArea } from "@/components/ui/scroll-area"
import { FileText, Calendar, Database, Search, Image as ImageIcon, Music, Video, File, ListFilter, RefreshCw, ExternalLink, Download, ChevronDown, Mic } from "lucide-react"
import { fetchDocuments, fetchDocumentCounts, reindexMedia, getMediaUrl, downloadMediaFile, openMediaFile, type Document, type DocumentCounts } from "@/lib/api"
import { Input } from "@/components/ui/input"
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { Button } from "@/components/ui/button"
import {
    DropdownMenu,
    DropdownMenuContent,
    DropdownMenuItem,
    DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"
import { toast } from "sonner"
import { useApp } from "@/components/app-shell/app-context"

export function DatasetsView() {
    const { setActiveJobId } = useApp()
    const [documents, setDocuments] = useState<Document[]>([])
    const [counts, setCounts] = useState<DocumentCounts>({})
    const [loading, setLoading] = useState(true)
    const [error, setError] = useState<string | null>(null)
    const [searchQuery, setSearchQuery] = useState("")
    const [activeTab, setActiveTab] = useState("all")
    const [isReprocessing, setIsReprocessing] = useState(false)

    const TAB_TO_MEDIA_TYPE: Record<string, string | undefined> = {
        all: undefined,
        text: "text",
        images: "photo",
        audio: "audio",
        video: "video",
        docs: "document",
    }

    useEffect(() => {
        setLoading(true)
        setError(null)
        fetchDocuments(50, 0, TAB_TO_MEDIA_TYPE[activeTab])
            .then(setDocuments)
            .catch((err) => setError(err.message))
            .finally(() => setLoading(false))
    }, [activeTab])

    useEffect(() => {
        fetchDocumentCounts().then(setCounts).catch(() => { })
    }, [])

    const MEDIA_TYPE_LABELS: Record<string, string> = {
        photo: "images",
        audio: "audio",
        video: "video",
        voice: "voice",
        document: "documents",
    }

    const handleReprocess = async (mediaTypes?: string[]) => {
        setIsReprocessing(true)
        try {
            const result = await reindexMedia(false, mediaTypes)
            if (result.job_id) {
                setActiveJobId(result.job_id)
            }
            const label = mediaTypes
                ? mediaTypes.map((t) => MEDIA_TYPE_LABELS[t] ?? t).join(", ")
                : "all media"
            toast.success("Media reprocessing started", {
                description: `Re-analyzing ${label} files in the background.`
            })
        } catch (err: any) {
            toast.error("Failed to start reprocessing", {
                description: err.message
            })
        } finally {
            setIsReprocessing(false)
        }
    }

    function formatFileSize(bytes: number): string {
        if (bytes < 1024) return `${bytes} B`
        if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
        return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
    }

    function resolveDocTitle(doc: Document): string {
        const media = doc.metadata?.media
        if (media?.file_name) return media.file_name
        if (media?.path) {
            const basename = media.path.split("/").pop()
            if (basename) return basename
        }
        if (media?.extension) return `${media.extension.toUpperCase()} document`
        if (media?.mime) {
            const mimeLabel = media.mime.split("/").pop()?.toUpperCase() ?? media.type?.toUpperCase()
            const sizeLabel = media.size ? ` (${formatFileSize(media.size)})` : ""
            return `${mimeLabel} file${sizeLabel}`
        }
        if (media?.type) return `${media.type.toUpperCase()} file`
        return `Doc ${doc.doc_id}`
    }

    const filteredDocuments = useMemo(() => {
        if (!searchQuery) return documents
        const searchTerm = searchQuery.toLowerCase()
        return documents.filter((doc) => {
            return (
                doc.content.toLowerCase().includes(searchTerm) ||
                (doc.metadata?.chat_title || "").toLowerCase().includes(searchTerm) ||
                (doc.metadata?.file_name || "").toLowerCase().includes(searchTerm) ||
                (doc.metadata?.sender_name || "").toLowerCase().includes(searchTerm)
            )
        })
    }, [documents, searchQuery])

    return (
        <motion.div
            initial={{ opacity: 0, y: 12 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -12 }}
            transition={{ duration: 0.25, ease: "easeOut" }}
            className="flex h-full flex-col overflow-hidden"
        >
            <div className="border-b border-border bg-background/50 backdrop-blur-sm px-4 py-3 space-y-3">
                <div className="flex items-center justify-between">
                    <div className="flex items-center gap-2">
                        <Database className="h-5 w-5 text-primary" />
                        <div>
                            <h2 className="text-lg font-semibold text-foreground">Datasets</h2>
                            <p className="text-[10px] text-muted-foreground uppercase tracking-wider">
                                {filteredDocuments.length} of {counts.all ?? "..."} documents
                            </p>
                        </div>
                    </div>
                    <div className="flex items-center">
                        <Button
                            variant="outline"
                            size="sm"
                            className="gap-2 h-9 rounded-r-none border-primary/20 hover:bg-primary/5 text-primary"
                            onClick={() => handleReprocess()}
                            disabled={isReprocessing}
                        >
                            <RefreshCw className={`h-4 w-4 ${isReprocessing ? 'animate-spin' : ''}`} />
                            {isReprocessing ? 'Starting...' : 'Reprocess All Media'}
                        </Button>
                        <DropdownMenu>
                            <DropdownMenuTrigger asChild>
                                <Button
                                    variant="outline"
                                    size="sm"
                                    className="h-9 px-2 rounded-l-none border-l-0 border-primary/20 hover:bg-primary/5 text-primary"
                                    disabled={isReprocessing}
                                >
                                    <ChevronDown className="h-4 w-4" />
                                </Button>
                            </DropdownMenuTrigger>
                            <DropdownMenuContent align="end">
                                <DropdownMenuItem onClick={() => handleReprocess(["photo"])}>
                                    <ImageIcon className="h-4 w-4 mr-2" />
                                    Images
                                </DropdownMenuItem>
                                <DropdownMenuItem onClick={() => handleReprocess(["audio"])}>
                                    <Music className="h-4 w-4 mr-2" />
                                    Audio
                                </DropdownMenuItem>
                                <DropdownMenuItem onClick={() => handleReprocess(["video"])}>
                                    <Video className="h-4 w-4 mr-2" />
                                    Video
                                </DropdownMenuItem>
                                <DropdownMenuItem onClick={() => handleReprocess(["voice"])}>
                                    <Mic className="h-4 w-4 mr-2" />
                                    Voice
                                </DropdownMenuItem>
                                <DropdownMenuItem onClick={() => handleReprocess(["document"])}>
                                    <File className="h-4 w-4 mr-2" />
                                    Documents
                                </DropdownMenuItem>
                            </DropdownMenuContent>
                        </DropdownMenu>
                    </div>
                </div>

                <div className="flex flex-col sm:flex-row gap-3">
                    <div className="relative flex-1">
                        <Search className="absolute left-2.5 top-2.5 h-4 w-4 text-muted-foreground" />
                        <Input
                            placeholder="Filter by content, chat or filename..."
                            className="pl-9 bg-muted/50 border-none h-9 text-sm"
                            value={searchQuery}
                            onChange={(e) => setSearchQuery(e.target.value)}
                        />
                    </div>
                </div>

                <Tabs value={activeTab} onValueChange={setActiveTab} className="w-full">
                    <TabsList className="bg-muted/30 p-1 h-auto flex-wrap justify-start gap-1">
                        <TabsTrigger value="all" className="py-1 px-3 text-xs"><ListFilter className="mr-1.5 h-3 w-3" /> All {counts.all != null && <span className="ml-1 text-muted-foreground">{counts.all}</span>}</TabsTrigger>
                        <TabsTrigger value="text" className="py-1 px-3 text-xs"><FileText className="mr-1.5 h-3 w-3" /> Text {counts.text != null && <span className="ml-1 text-muted-foreground">{counts.text}</span>}</TabsTrigger>
                        <TabsTrigger value="images" className="py-1 px-3 text-xs"><ImageIcon className="mr-1.5 h-3 w-3" /> Images {counts.photo != null && <span className="ml-1 text-muted-foreground">{counts.photo}</span>}</TabsTrigger>
                        <TabsTrigger value="audio" className="py-1 px-3 text-xs"><Music className="mr-1.5 h-3 w-3" /> Audio {counts.audio != null && <span className="ml-1 text-muted-foreground">{counts.audio}</span>}</TabsTrigger>
                        <TabsTrigger value="video" className="py-1 px-3 text-xs"><Video className="mr-1.5 h-3 w-3" /> Video {counts.video != null && <span className="ml-1 text-muted-foreground">{counts.video}</span>}</TabsTrigger>
                        <TabsTrigger value="docs" className="py-1 px-3 text-xs"><File className="mr-1.5 h-3 w-3" /> Docs {counts.document != null && <span className="ml-1 text-muted-foreground">{counts.document}</span>}</TabsTrigger>
                    </TabsList>
                </Tabs>
            </div>

            <ScrollArea className="flex-1 min-h-0">
                <div className="flex flex-col gap-2 p-4 pb-10">
                    {loading && <div className="p-8 text-center text-sm text-muted-foreground">Loading documents...</div>}
                    {error && <div className="p-8 text-center text-sm text-destructive bg-destructive/5 rounded-lg border border-destructive/20">Error: {error}</div>}

                    {!loading && !error && filteredDocuments.length === 0 && (
                        <div className="p-12 text-center text-sm text-muted-foreground border border-dashed border-border rounded-xl">
                            No documents match your filters.
                        </div>
                    )}

                    {!loading && !error && filteredDocuments.map((doc) => (
                        <div
                            key={`${doc.source_id}-${doc.doc_id}`}
                            className="flex flex-col gap-1 rounded-xl border border-border bg-card/40 p-4 transition-all hover:bg-secondary/30 hover:border-primary/20 group"
                        >
                            <div className="flex items-start justify-between">
                                <div className="flex items-center gap-2.5">
                                    <div className="p-2 rounded-lg bg-primary/10 text-primary">
                                        {doc.metadata?.media?.type === "photo" ? <ImageIcon className="h-4 w-4" /> :
                                            doc.metadata?.media?.type === "audio" || doc.metadata?.media?.type === "voice" ? <Music className="h-4 w-4" /> :
                                                doc.metadata?.media?.type === "video" ? <Video className="h-4 w-4" /> :
                                                    doc.metadata?.media?.type === "document" ? <File className="h-4 w-4" /> :
                                                        <FileText className="h-4 w-4" />}
                                    </div>
                                    <div className="flex flex-col">
                                        <span className="text-sm font-semibold text-foreground group-hover:text-primary transition-colors">
                                            {resolveDocTitle(doc)}
                                        </span>
                                        <span className="text-[10px] text-muted-foreground font-medium uppercase tracking-tighter">
                                            {doc.source_id}
                                        </span>
                                    </div>
                                </div>

                                {doc.metadata?.media && getMediaUrl(doc) && (
                                    <div className="flex items-center gap-1.5 opacity-40 group-hover:opacity-100 transition-opacity">
                                        <Button
                                            variant="ghost"
                                            size="icon"
                                            className="h-8 w-8 rounded-full hover:bg-primary/10 hover:text-primary"
                                            onClick={() => openMediaFile(doc).catch(() =>
                                                toast.error("Failed to open media file")
                                            )}
                                        >
                                            <ExternalLink className="h-3.5 w-3.5" />
                                        </Button>
                                        <Button
                                            variant="ghost"
                                            size="icon"
                                            className="h-8 w-8 rounded-full hover:bg-primary/10 hover:text-primary"
                                            onClick={() => downloadMediaFile(doc).catch(() =>
                                                toast.error("Failed to download media file")
                                            )}
                                        >
                                            <Download className="h-3.5 w-3.5" />
                                        </Button>
                                    </div>
                                )}
                            </div>

                            {doc.metadata?.media?.type === "photo" && getMediaUrl(doc) && (
                                <div className="mt-3 overflow-hidden rounded-lg border border-border/50 bg-black/5 aspect-video flex items-center justify-center">
                                    <img
                                        src={getMediaUrl(doc)!}
                                        alt={doc.metadata?.file_name || "Preview"}
                                        className="max-h-full max-w-full object-contain"
                                        onError={(e) => {
                                            (e.target as HTMLImageElement).style.display = 'none';
                                        }}
                                    />
                                </div>
                            )}

                            {doc.metadata?.media?.type === "video" && getMediaUrl(doc) && (
                                <div className="mt-3 overflow-hidden rounded-lg border border-border/50 bg-black/5">
                                    <video
                                        src={getMediaUrl(doc)!}
                                        controls
                                        preload="metadata"
                                        className="w-full max-h-80"
                                    />
                                </div>
                            )}

                            {(doc.metadata?.media?.type === "audio" || doc.metadata?.media?.type === "voice") && getMediaUrl(doc) && (
                                <div className="mt-3 flex flex-col gap-2">
                                    <audio
                                        src={getMediaUrl(doc)!}
                                        controls
                                        preload="metadata"
                                        className="w-full"
                                    />
                                    {doc.metadata?.media?.original_transcript || doc.metadata?.media?.description ? (
                                        <div className="text-xs text-muted-foreground/90 leading-relaxed font-sans bg-muted/20 p-2 rounded-md border border-border/50">
                                            <p className="whitespace-pre-wrap">{doc.metadata.media.original_transcript || doc.metadata.media.description}</p>
                                            {doc.metadata.media.translation && (
                                                <details className="mt-2 cursor-pointer group">
                                                    <summary className="font-semibold select-none text-primary/80 group-hover:text-primary transition-colors">Перевод</summary>
                                                    <p className="mt-1.5 whitespace-pre-wrap p-2 bg-background/50 rounded border border-border/30">{doc.metadata.media.translation}</p>
                                                </details>
                                            )}
                                        </div>
                                    ) : null}
                                </div>
                            )}

                            <div className="mt-2 text-xs text-muted-foreground/90 leading-relaxed font-sans line-clamp-3 bg-muted/20 p-2 rounded-md border border-border/50">
                                {doc.content ? doc.content.substring(0, 300) : "No text content (Media file)"}
                            </div>

                            <div className="mt-3 flex items-center gap-4 text-[10px] text-muted-foreground/70">
                                <span className="flex items-center gap-1.5 px-2 py-0.5 rounded-full bg-muted/50">
                                    <Calendar className="h-3 w-3" />
                                    {new Date(doc.timestamp).toLocaleString()}
                                </span>
                                {doc.metadata?.chat_title && (
                                    <span className="flex items-center gap-1.5 px-2 py-0.5 rounded-full bg-primary/5 text-primary/70">
                                        Chat: {doc.metadata.chat_title}
                                    </span>
                                )}
                            </div>
                        </div>
                    ))}
                </div>
            </ScrollArea>
        </motion.div>
    )
}
