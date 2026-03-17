"use client"

import { useState, useEffect, useRef } from "react"
import { useApp } from "../app-shell/app-context"
import { motion } from "framer-motion"
import { ArrowLeft, Bot, User, Download } from "lucide-react"
import { Button } from "@/components/ui/button"
import { ScrollArea } from "@/components/ui/scroll-area"
import { getMediaUrl } from "@/lib/api"

interface ChatMessageItem {
  role: "user" | "assistant"
  content: string
  timestamp: string
  doc_id?: string
  metadata?: { media?: { path?: string; type?: string; description?: string; file_name?: string; extension?: string }; chat_title?: string }
}

export function ChatMessagesView() {
  const { activeChatId, setCurrentView, setActiveChatId, scrollToDocId, setScrollToDocId } = useApp()
  const [messages, setMessages] = useState<ChatMessageItem[]>([])
  const [loading, setLoading] = useState(false)
  const [chatTitle, setChatTitle] = useState<string>("")
  const scrollRefs = useRef<Record<string, HTMLDivElement | null>>({})

  useEffect(() => {
    if (!activeChatId) return

    setLoading(true)
    Promise.all([
      fetch(`/api/chat/${activeChatId}`).then((r) => (r.ok ? r.json() : null)),
      fetch(`/api/chat/${activeChatId}/messages?limit=100&offset=0`).then((r) =>
        r.ok ? r.json() : []
      ),
    ])
      .then(([chat, raw]: [any, any[]]) => {
        if (chat?.title) setChatTitle(chat.title)
        const items: ChatMessageItem[] = (raw || []).map((msg: any) => ({
          role: msg.metadata?.sender_id === "me" ? "user" : "assistant",
          content: msg.content,
          timestamp: new Date(msg.timestamp).toLocaleTimeString([], {
            hour: "2-digit",
            minute: "2-digit",
          }),
          doc_id: msg.doc_id,
          metadata: msg.metadata,
        }))
        setMessages(items)
        if (!chat?.title && raw?.[0]?.metadata?.chat_title) {
          setChatTitle(raw[0].metadata.chat_title)
        }
      })
      .catch(console.error)
      .finally(() => setLoading(false))
  }, [activeChatId])

  useEffect(() => {
    if (scrollToDocId && scrollRefs.current[scrollToDocId]) {
      scrollRefs.current[scrollToDocId]?.scrollIntoView({ behavior: "smooth" })
      setScrollToDocId(null)
    }
  }, [scrollToDocId, setScrollToDocId])

  const handleBack = () => {
    setActiveChatId(null)
    setCurrentView("chat")
  }

  if (!activeChatId) {
    return (
      <motion.div
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        className="flex h-full flex-col items-center justify-center gap-4 p-8"
      >
        <p className="text-sm text-muted-foreground">No chat selected</p>
        <Button variant="outline" onClick={() => setCurrentView("chat")}>
          Back to Chat
        </Button>
      </motion.div>
    )
  }

  return (
    <motion.div
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0, y: -12 }}
      transition={{ duration: 0.25, ease: "easeOut" }}
      className="flex h-full flex-col overflow-hidden"
    >
      <div className="flex items-center gap-3 border-b border-border px-4 py-3">
        <Button
          variant="ghost"
          size="icon"
          className="h-8 w-8 shrink-0"
          onClick={handleBack}
          aria-label="Back to chat"
        >
          <ArrowLeft className="h-4 w-4" />
        </Button>
        <div>
          <h3 className="text-sm font-medium text-foreground">
            {chatTitle || `Chat ${activeChatId}`}
          </h3>
          <p className="text-[11px] text-muted-foreground">
            {loading ? "Loading..." : `${messages.length} messages`}
          </p>
        </div>
      </div>

      <ScrollArea className="flex-1 min-h-0">
        <div className="flex flex-col gap-4 p-4">
          {messages.map((message, idx) => {
            const doc = message.doc_id
              ? {
                doc_id: message.doc_id,
                metadata: message.metadata,
                source_id: String(activeChatId),
              }
              : null
            const mediaUrl = doc ? getMediaUrl(doc) : null

            return (
              <div
                key={message.doc_id || idx}
                ref={(el) => {
                  if (message.doc_id) scrollRefs.current[message.doc_id] = el
                }}
                id={message.doc_id ? `msg-${message.doc_id}` : undefined}
                className={`flex gap-3 ${message.role === "user" ? "flex-row-reverse" : ""}`}
              >
                <div
                  className={`flex h-7 w-7 shrink-0 items-center justify-center rounded-full ${message.role === "assistant"
                      ? "bg-primary/15 text-primary"
                      : "bg-secondary text-muted-foreground"
                    }`}
                >
                  {message.role === "assistant" ? (
                    <Bot className="h-3.5 w-3.5" />
                  ) : (
                    <User className="h-3.5 w-3.5" />
                  )}
                </div>
                <div
                  className={`max-w-[75%] rounded-lg px-3.5 py-2.5 ${message.role === "user"
                      ? "bg-primary/10 text-foreground"
                      : "bg-secondary/70 text-foreground"
                    }`}
                >
                  {mediaUrl && message.metadata?.media?.type === "photo" && (
                    <div className="mb-2 overflow-hidden rounded-lg border border-border/50 bg-black/5 aspect-video flex items-center justify-center max-w-xs">
                      <img
                        src={mediaUrl}
                        alt={message.metadata?.media?.description || "Photo"}
                        className="max-h-full max-w-full object-contain"
                      />
                    </div>
                  )}
                  {mediaUrl &&
                    ["audio", "voice"].includes(message.metadata?.media?.type || "") && (
                      <div className="mb-2 flex flex-col gap-2">
                        <audio src={mediaUrl} controls className="w-full max-w-xs" />
                        {message.metadata?.media?.original_transcript || message.metadata?.media?.description ? (
                          <div className="text-xs text-foreground/90 leading-relaxed font-sans bg-background/50 p-2 rounded-md border border-border/50 max-w-xs">
                            <p className="whitespace-pre-wrap">{message.metadata.media.original_transcript || message.metadata.media.description}</p>
                            {message.metadata.media.translation && (
                              <details className="mt-2 cursor-pointer group">
                                <summary className="font-semibold select-none text-primary/80 group-hover:text-primary transition-colors">Перевод</summary>
                                <p className="mt-1.5 whitespace-pre-wrap p-2 bg-background rounded border border-border/30">{message.metadata.media.translation}</p>
                              </details>
                            )}
                          </div>
                        ) : null}
                        <a
                          href={mediaUrl}
                          download
                          className="inline-flex items-center gap-1.5 text-xs text-primary hover:underline"
                        >
                          <Download className="h-3.5 w-3.5" />
                          Download
                        </a>
                      </div>
                    )}
                  {mediaUrl && message.metadata?.media?.type === "video" && (
                    <div className="mb-2">
                      <video src={mediaUrl} controls className="max-w-xs rounded-lg border border-border/50" />
                    </div>
                  )}
                  {mediaUrl &&
                    message.metadata?.media?.type === "document" && (() => {
                      const m = message.metadata!.media!
                      const label = m.file_name
                        || m.path?.split("/").pop()
                        || (m.extension ? `${m.extension.toUpperCase()} document` : "Document")
                      return (
                        <div className="mb-2 flex items-center gap-2 rounded-md bg-muted/30 px-3 py-2 border border-border/50">
                          <Download className="h-4 w-4 shrink-0 text-primary" />
                          <a
                            href={mediaUrl}
                            download={m.file_name || true}
                            className="text-xs font-medium text-primary hover:underline truncate"
                          >
                            {label}
                          </a>
                        </div>
                      )
                    })()}
                  <p className="whitespace-pre-wrap text-sm leading-relaxed">{message.content}</p>
                  <span className="mt-1.5 block text-[10px] text-muted-foreground">
                    {message.timestamp}
                  </span>
                </div>
              </div>
            )
          })}
        </div>
      </ScrollArea>
    </motion.div>
  )
}
