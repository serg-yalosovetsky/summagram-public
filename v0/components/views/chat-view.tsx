"use client"

import { useState, useEffect, useRef } from "react"
import { useApp } from "../app-shell/app-context"
import { motion } from "framer-motion"
import { Send, Paperclip, Sparkles, Bot, User, Download, ExternalLink } from "lucide-react"
import { Button } from "@/components/ui/button"
import { ScrollArea } from "@/components/ui/scroll-area"
import { toast } from "sonner"
import { fetchSessionMessages, sendSessionMessage, warmModel, fetchSystemStatus, type Message, type ReferencedMessage } from "@/lib/api"

const inlineMediaTypes = ["photo", "image", "video", "audio", "voice"]
const isInlineMedia = (t?: string | null) => t && inlineMediaTypes.includes(t.toLowerCase())

function ReferencedMessageBlock({ refMsg }: { refMsg: ReferencedMessage }) {
  // ... keeping ReferencedMessageBlock unchanged
  const { chat_id, doc_id, content, media_url, media_type, description } = refMsg
  const { setActiveChatId, setCurrentView, setScrollToDocId } = useApp()
  const showInline = media_url && isInlineMedia(media_type)
  const isPhoto = media_type && ["photo", "image"].includes(media_type.toLowerCase())
  const isVideo = media_type && media_type.toLowerCase() === "video"
  const isAudio = media_type && ["audio", "voice"].includes(media_type.toLowerCase())

  const handleViewMessage = () => {
    setActiveChatId(chat_id)
    setScrollToDocId(doc_id)
    setCurrentView("chat-messages")
  }

  return (
    <div className="mt-3 space-y-2 border-t border-border/50 pt-2">
      {content && (
        <p className="text-sm text-muted-foreground whitespace-pre-wrap">{content}</p>
      )}
      {showInline && isPhoto && (
        <div className="overflow-hidden rounded-lg border border-border/50 bg-black/5 aspect-video flex items-center justify-center max-w-xs">
          <img
            src={media_url}
            alt={description || "Message media"}
            className="max-h-full max-w-full object-contain"
            onError={(e) => { (e.target as HTMLImageElement).style.display = "none" }}
          />
        </div>
      )}
      {showInline && isVideo && (
        <video src={media_url} controls className="max-w-xs rounded-lg border border-border/50" />
      )}
      {showInline && isAudio && (
        <div className="flex flex-col gap-2">
          <audio src={media_url} controls className="w-full max-w-xs" />
          <a
            href={media_url}
            download
            className="inline-flex items-center gap-1.5 text-xs text-primary hover:underline"
          >
            <Download className="h-3.5 w-3.5" />
            Download
          </a>
        </div>
      )}
      {media_url && !showInline && (
        <div className="flex items-center gap-2 text-xs">
          {description && <span className="text-muted-foreground">{description}</span>}
          <a
            href={media_url}
            download
            className="inline-flex items-center gap-1 text-primary hover:underline"
          >
            <Download className="h-3.5 w-3.5" />
            Download
          </a>
        </div>
      )}
      <div className="flex items-center gap-2">
        <button
          type="button"
          onClick={handleViewMessage}
          className="inline-flex items-center gap-1 text-xs text-primary hover:underline"
        >
          <ExternalLink className="h-3.5 w-3.5" />
          View message
        </button>
      </div>
    </div>
  )
}

export function ChatView() {
  const { activeSessionId } = useApp()
  const [messages, setMessages] = useState<Message[]>([])
  const [inputValue, setInputValue] = useState("")
  const [loading, setLoading] = useState(false)
  const [warming, setWarming] = useState(false)
  const bottomRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    // Pre-warm the text model as soon as the chat view mounts
    warmModel("text")
  }, [])

  useEffect(() => {
    if (!activeSessionId) return

    setLoading(true)
    fetchSessionMessages(activeSessionId)
      .then(setMessages)
      .catch(console.error)
      .finally(() => setLoading(false))
  }, [activeSessionId])

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" })
  }, [messages, loading, warming])

  const handleSend = async () => {
    if (!inputValue.trim() || !activeSessionId) {
      console.warn("[ChatView] Send blocked: empty input or no active session")
      return
    }

    try {
      const status = await fetchSystemStatus()
      if (status.switching || status.current_model === null) {
        setWarming(true)
        toast("Model is warming up, this might take a minute...")
      }
    } catch (e) {
      console.warn("[ChatView] Failed to check system status:", e)
      // Continue anyway, maybe it'll work or hit the circuit breaker
    }

    console.log("[ChatView] handleSend triggered", { activeSessionId, inputValue })

    const userMessageContent = inputValue
    setInputValue("")

    // Optimistic update
    const userMsg: Message = {
      role: "user",
      content: userMessageContent,
      timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
    }
    setMessages(prev => [...prev, userMsg])
    setLoading(true)

    try {
      console.log(`[ChatView] Calling sendSessionMessage API for session ${activeSessionId}`)
      const { assistant_message } = await sendSessionMessage(activeSessionId, userMessageContent)

      console.log("[ChatView] Received AI response", assistant_message)

      // Update with server timestamp and AI response
      setMessages(prev => {
        const msg: Message = {
          role: "assistant",
          content: assistant_message.content,
          timestamp: new Date(assistant_message.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
        }
        if (assistant_message.referenced_message) {
          msg.referenced_message = assistant_message.referenced_message
        }
        return [...prev, msg]
      })
      setWarming(false)
    } catch (error) {
      const msg = error instanceof Error ? error.message : "Failed to send message"
      console.warn("[ChatView] Error sending message:", msg)
      toast.error(msg)
      setMessages(prev => prev.slice(0, -1))
      setInputValue(userMessageContent) // restore input
    } finally {
      setLoading(false)
      setWarming(false)
    }
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
        <div className="h-2 w-2 rounded-full bg-primary shadow-[0_0_6px_oklch(0.65_0.2_250)]" />
        <div>
          <h3 className="text-sm font-medium text-foreground">
            {activeSessionId ? `Session #${activeSessionId}` : "Select a Session"}
          </h3>
          <p className="text-[11px] text-muted-foreground">
            {loading ? "Loading..." : `${messages.length} messages`}
          </p>
        </div>
      </div>

      <ScrollArea className="flex-1 min-h-0">
        <div className="flex flex-col gap-4 p-4">
          {(() => {
            // Pre-calculate inline media counts
            const parsedMessages = messages.map(msg => {
              if (msg.role !== 'assistant') return { ...msg, inlineMedia: [] as string[] };
              const regex = /(\/media\/[a-zA-Z0-9_.-]+\.(?:jpg|jpeg|png|gif|webp))/gi;
              const matches = [...msg.content.matchAll(regex)];
              const inlineMedia = matches.map(m => m[1]);
              return { ...msg, inlineMedia };
            });
            const totalInlineMediaCount = parsedMessages.reduce((sum, msg) => sum + (msg.inlineMedia?.length || 0), 0);
            let currentInlineMediaIndex = 0;

            return parsedMessages.map((message, idx) => (
              <div
                key={idx}
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
                  <p className="whitespace-pre-wrap text-sm leading-relaxed">{message.content}</p>

                  {message.inlineMedia && message.inlineMedia.length > 0 && (
                    <div className="mt-3 flex flex-col gap-2">
                      {message.inlineMedia.map((url, i) => {
                        currentInlineMediaIndex++;
                        const isLastMedia = currentInlineMediaIndex === totalInlineMediaCount;
                        return (
                          <details
                            key={i}
                            open={isLastMedia}
                            className="group border border-border/50 rounded-lg p-2 bg-black/5"
                          >
                            <summary className="cursor-pointer text-xs font-medium text-muted-foreground focus:outline-none flex items-center gap-1">
                              <span className="group-open:hidden">Show attached image</span>
                              <span className="hidden group-open:inline">Hide attached image</span>
                            </summary>
                            <div className="mt-2 flex flex-col gap-2">
                              <a href={url} target="_blank" rel="noopener noreferrer" className="overflow-hidden rounded-md flex items-center justify-center bg-black/10">
                                <img src={url} alt="inline media" className="max-h-64 object-contain" />
                              </a>
                              <a href={url} download className="inline-flex items-center gap-1.5 text-xs text-primary hover:underline">
                                <Download className="h-3.5 w-3.5" />
                                Download file
                              </a>
                            </div>
                          </details>
                        )
                      })}
                    </div>
                  )}

                  {message.role === "assistant" && message.referenced_message && (
                    <ReferencedMessageBlock refMsg={message.referenced_message} />
                  )}
                  <span className="mt-1.5 block text-[10px] text-muted-foreground">
                    {message.timestamp}
                  </span>
                </div>
              </div>
            ))
          })()}
          {(loading || warming) && (
            <div className="flex gap-3">
              <div className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-primary/15 text-primary">
                <Bot className="h-3.5 w-3.5" />
              </div>
              <div className="max-w-[75%] rounded-lg px-4 py-3 bg-secondary/70 flex items-center justify-center min-w-[60px]">
                {warming ? (
                  <span className="flex gap-1 items-center text-xs text-muted-foreground">
                    <span className="w-1.5 h-1.5 bg-primary/40 rounded-full animate-bounce" style={{ animationDelay: '0ms' }} />
                    <span className="w-1.5 h-1.5 bg-primary/60 rounded-full animate-bounce" style={{ animationDelay: '150ms' }} />
                    <span className="w-1.5 h-1.5 bg-primary/80 rounded-full animate-bounce" style={{ animationDelay: '300ms' }} />
                    <span className="ml-1 tracking-wide">Warming up...</span>
                  </span>
                ) : (
                  <span className="flex gap-1" aria-label="Thinking">
                    <span className="w-1.5 h-1.5 bg-muted-foreground/40 rounded-full animate-bounce" style={{ animationDelay: '0ms' }} />
                    <span className="w-1.5 h-1.5 bg-muted-foreground/60 rounded-full animate-bounce" style={{ animationDelay: '150ms' }} />
                    <span className="w-1.5 h-1.5 bg-muted-foreground/80 rounded-full animate-bounce" style={{ animationDelay: '300ms' }} />
                  </span>
                )}
              </div>
            </div>
          )}
          <div ref={bottomRef} />
        </div>
      </ScrollArea>

      <div className="border-t border-border p-4">
        <div className="flex items-center gap-2 rounded-lg border border-border bg-secondary/50 px-3 py-2">
          <Button
            variant="ghost"
            size="icon"
            className="h-7 w-7 shrink-0 text-muted-foreground hover:text-foreground"
            aria-label="Attach file"
          >
            <Paperclip className="h-4 w-4" />
          </Button>
          <input
            type="text"
            value={inputValue}
            onChange={(e) => setInputValue(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && handleSend()}
            placeholder="Type a message..."
            className="flex-1 bg-transparent text-sm text-foreground placeholder:text-muted-foreground focus:outline-none"
          />
          <Button
            variant="ghost"
            size="icon"
            className="h-7 w-7 shrink-0 text-muted-foreground hover:text-primary"
            aria-label="AI suggestions"
          >
            <Sparkles className="h-4 w-4" />
          </Button>
          <Button
            size="icon"
            className="h-7 w-7 shrink-0 bg-primary text-primary-foreground hover:bg-primary/90"
            aria-label="Send message"
            onClick={handleSend}
          >
            <Send className="h-3.5 w-3.5" />
          </Button>
        </div>
      </div>
    </motion.div>
  )
}
