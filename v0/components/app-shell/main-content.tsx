"use client"

import { useApp } from "./app-context"
import { AnimatePresence } from "framer-motion"
import { SessionSelectView } from "@/components/views/session-select-view"
import { ChatView } from "@/components/views/chat-view"
import { ChatMessagesView } from "@/components/views/chat-messages-view"
import { SettingsView } from "@/components/views/settings-view"
import { DatasetsView } from "@/components/views/datasets-view"
import { PipelineView } from "@/components/views/pipeline-view"
import { NetworkView } from "@/components/views/network-view"
import { SessionsView } from "@/components/views/sessions-view"
import { AnalyticsView } from "@/components/views/analytics-view"

export function MainContent() {
  const { currentView } = useApp()

  return (
    <main className="flex flex-1 min-h-0 flex-col overflow-hidden">
      <AnimatePresence mode="wait">
        {currentView === "session-select" && <SessionSelectView key="session-select" />}
        {currentView === "chat" && <ChatView key="chat" />}
        {currentView === "chat-messages" && <ChatMessagesView key="chat-messages" />}
        {currentView === "sessions" && <SessionsView key="sessions" />}
        {currentView === "settings" && <SettingsView key="settings" />}
        {currentView === "datasets" && <DatasetsView key="datasets" />}
        {currentView === "pipeline" && <PipelineView key="pipeline" />}
        {currentView === "network" && <NetworkView key="network" />}
        {currentView === "analytics" && <AnalyticsView key="analytics" />}
        {["models", "documents", "context", "search", "integrations"].includes(currentView) && (
          <div key={currentView} className="flex h-full items-center justify-center text-muted-foreground">
            <div className="text-center">
              <h2 className="text-xl font-semibold capitalize">{currentView} View</h2>
              <p>This view is under development.</p>
            </div>
          </div>
        )}
      </AnimatePresence>
    </main>
  )
}
