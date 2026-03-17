"use client"

import { createContext, useContext, useState, useCallback, useEffect, type ReactNode } from "react"

export type AppView = "session-select" | "sessions" | "chat" | "chat-messages" | "settings" | "datasets" | "pipeline" | "network" | "analytics" | "documents" | "context" | "search" | "models" | "integrations"

interface ProcessingTask {
  label: string
  progress: number
}

interface AppContextType {
  currentView: AppView
  setCurrentView: (view: AppView) => void
  debugPanelOpen: boolean
  toggleDebugPanel: () => void
  processingTask: ProcessingTask | null
  activeJobId: string | null
  setActiveJobId: (id: string | null) => void
  activeSessionId: string | null
  setActiveSessionId: (id: string | null) => void
  activeChatId: number | null
  setActiveChatId: (id: number | null) => void
  scrollToDocId: string | null
  setScrollToDocId: (id: string | null) => void
}

const AppContext = createContext<AppContextType | undefined>(undefined)

export function AppProvider({ children }: { children: ReactNode }) {
  const [currentView, setCurrentView] = useState<AppView>("session-select")
  const [debugPanelOpen, setDebugPanelOpen] = useState(false)
  const [processingTask, setProcessingTask] = useState<ProcessingTask | null>(null)
  const [activeJobId, setActiveJobId] = useState<string | null>(null)
  const [activeSessionId, setActiveSessionId] = useState<string | null>(null)
  const [activeChatId, setActiveChatId] = useState<number | null>(null)
  const [scrollToDocId, setScrollToDocId] = useState<string | null>(null)

  const toggleDebugPanel = useCallback(() => {
    setDebugPanelOpen((prev) => !prev)
  }, [])

  // Real-time streaming for ETL jobs via EventSource
  useEffect(() => {
    if (!activeJobId) return

    let unsubscribe: (() => void) | undefined;

    import("@/lib/api").then(({ subscribeJobStatus }) => {
      unsubscribe = subscribeJobStatus(activeJobId, (status) => {
        setProcessingTask({
          label: status.message || (status.status === "queued" ? "Queued..." : "Processing..."),
          progress: (status.progress || 0) * 100
        })

        if (status.status === "completed" || status.status === "failed") {
          // Keep the message for a moment then clear
          setTimeout(() => {
            setActiveJobId(null)
            setProcessingTask(null)
          }, 3000)
          unsubscribe?.()
        }
      }, (err) => {
        console.error("Job status SSE error:", err)
      })
    }).catch(err => {
      console.error("Failed to dynamically import api:", err)
    })

    return () => {
      if (unsubscribe) unsubscribe()
    }
  }, [activeJobId])

  return (
    <AppContext.Provider
      value={{
        currentView,
        setCurrentView,
        debugPanelOpen,
        toggleDebugPanel,
        processingTask,
        activeJobId,
        setActiveJobId,
        activeSessionId,
        setActiveSessionId,
        activeChatId,
        setActiveChatId,
        scrollToDocId,
        setScrollToDocId,
      }}
    >
      {children}
    </AppContext.Provider>
  )
}

export function useApp() {
  const ctx = useContext(AppContext)
  if (!ctx) throw new Error("useApp must be used within AppProvider")
  return ctx
}
