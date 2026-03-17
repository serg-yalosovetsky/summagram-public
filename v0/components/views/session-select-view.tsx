"use client"

import { useState, useEffect, useRef } from "react"
import { useApp } from "../app-shell/app-context"
import { motion } from "framer-motion"
import {
  MessageSquare,
  Clock,
  FileText,
  ChevronDown,
  ChevronRight,
  Search,
} from "lucide-react"
import { Button } from "@/components/ui/button"
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from "@/components/ui/collapsible"
import { fetchChats, createSession, warmModel, type Chat } from "@/lib/api"
import { TelegramImportDialog } from "./telegram-import-dialog"
import { Tv, Sparkles } from "lucide-react"

export function SessionSelectView() {
  const { setCurrentView, setActiveSessionId, setActiveChatId, setActiveJobId, activeJobId } = useApp()
  const [configOpen, setConfigOpen] = useState(false)
  const [sessions, setSessions] = useState<Chat[]>([])
  const [loading, setLoading] = useState(true)
  const [dialogMode, setDialogMode] = useState<"sync" | "analyze" | null>(null)
  const analyzeJobIdRef = useRef<string | null>(null)

  useEffect(() => {
    if (!activeJobId && analyzeJobIdRef.current) {
      loadChats()
      analyzeJobIdRef.current = null
    }
  }, [activeJobId])

  const loadChats = async () => {
    setLoading(true)
    try {
      const data = await fetchChats()
      const mapped = data.map(chat => ({
        ...chat,
        status: chat.status || "active" as const
      }))
      setSessions(mapped)
    } catch (error) {
      console.error("Failed to load chats:", error)
    } finally {
      setLoading(false)
    }
  }

  const handleStartSession = async (chatId: number, chatTitle: string) => {
    const id = crypto.randomUUID()
    // Pre-warm the text model immediately when the user clicks a session
    warmModel("text")
    try {
      await createSession(id, `Analysis: ${chatTitle}`, chatId)
      setActiveSessionId(id)
      setCurrentView("chat")
    } catch (error) {
      console.error("Failed to start session from chat:", error)
    }
  }

  useEffect(() => {
    loadChats()
  }, [])

  if (loading) return <div className="p-8 text-center text-sm text-muted-foreground">Loading chats...</div>

  return (
    <motion.div
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0, y: -12 }}
      transition={{ duration: 0.25, ease: "easeOut" }}
      className="flex h-full flex-col overflow-auto"
    >
      <div className="border-b border-border p-4">
        <div className="flex items-center justify-between">
          <div>
            <h2 className="text-lg font-semibold text-foreground flex items-center gap-2">
              <MessageSquare className="h-5 w-5 text-primary" />
              Telegram Chats
            </h2>
            <p className="text-sm text-muted-foreground">
              {sessions.length} source chats for analysis
            </p>
          </div>
          <div className="flex gap-2">
            <Button
              onClick={() => setDialogMode("analyze")}
              size="sm"
              variant="outline"
              className="h-8 gap-2 font-medium border-border"
            >
              <Sparkles className="h-4 w-4" />
              Analyze chats
            </Button>
            <Button
              onClick={() => setDialogMode("sync")}
              size="sm"
              className="h-8 gap-2 bg-primary/10 text-primary hover:bg-primary/20 hover:text-primary transition-all font-medium border border-primary/20"
            >
              <Tv className="h-4 w-4" />
              Sync Telegram
            </Button>
          </div>
        </div>

        {/* Configuration Collapsible (Optional - kept for now) */}
        <Collapsible open={configOpen} onOpenChange={setConfigOpen} className="mt-3">
          <CollapsibleTrigger asChild>
            <Button
              variant="ghost"
              size="sm"
              className="h-7 gap-2 text-xs text-muted-foreground hover:text-foreground"
            >
              <Search className="h-3 w-3" />
              Filter Chats
              {configOpen ? (
                <ChevronDown className="h-3 w-3" />
              ) : (
                <ChevronRight className="h-3 w-3" />
              )}
            </Button>
          </CollapsibleTrigger>
          <CollapsibleContent>
            <div className="mt-2 p-3 text-xs text-muted-foreground bg-secondary/30 rounded-lg">
              Filters coming soon...
            </div>
          </CollapsibleContent>
        </Collapsible>
      </div>

      <div className="grid grid-cols-1 gap-3 p-4 md:grid-cols-2 lg:grid-cols-3">
        {sessions.map((session, index) => (
          <motion.div
            key={session.source_id}
            role="button"
            tabIndex={0}
            initial={{ opacity: 0, y: 8 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: index * 0.05, duration: 0.2 }}
            className="group flex cursor-pointer flex-col items-start rounded-lg border border-border bg-card p-4 text-left transition-colors hover:border-primary/40 hover:bg-secondary/50"
            onClick={() => handleStartSession(session.source_id, session.title || "")}
            onKeyDown={(e) => {
              if (e.key === "Enter" || e.key === " ") {
                e.preventDefault()
                handleStartSession(session.source_id, session.title || "")
              }
            }}
          >
            <div className="flex w-full items-start justify-between">
              <div className="flex items-center gap-2">
                <div
                  className={`h-2 w-2 rounded-full ${"bg-primary shadow-[0_0_6px_oklch(0.65_0.2_250)]"
                    }`}
                />
                <span className="text-sm font-medium text-foreground group-hover:text-primary line-clamp-1">
                  {session.title || `Chat ${session.source_id}`}
                </span>
              </div>
            </div>
            <p className="mt-1.5 line-clamp-2 text-xs text-muted-foreground">
              {session.description || "No description"}
            </p>
            <div className="mt-3 flex w-full items-center gap-3 text-[11px] text-muted-foreground">
              <span className="flex items-center gap-1">
                <MessageSquare className="h-3 w-3" />
                {session.message_count_me}
              </span>
              <span className="flex items-center gap-1">
                <FileText className="h-3 w-3" />
                Score: {session.importance_score.toFixed(2)}
              </span>
              <span className="ml-auto flex items-center gap-1">
                <Clock className="h-3 w-3" />
                {session.last_analyzed_at ? new Date(session.last_analyzed_at).toLocaleDateString() : "N/A"}
              </span>
            </div>
            <Button
              variant="ghost"
              size="sm"
              className="mt-2 h-6 text-[10px] text-muted-foreground hover:text-primary"
              onClick={(e) => {
                e.stopPropagation()
                setActiveChatId(session.source_id)
                setCurrentView("chat-messages")
              }}
            >
              View messages
            </Button>
          </motion.div>
        ))}
      </div>

      <TelegramImportDialog
        open={dialogMode !== null}
        onOpenChange={(open) => !open && setDialogMode(null)}
        onComplete={loadChats}
        mode={dialogMode === "analyze" ? "analyze" : "sync"}
        onJobStarted={(jobId) => {
          if (dialogMode === "analyze") {
            analyzeJobIdRef.current = jobId
          }
          setActiveJobId(jobId)
        }}
      />
    </motion.div>
  )
}
