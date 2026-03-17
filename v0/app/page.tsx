"use client"

import { AppProvider } from "@/components/app-shell/app-context"
import { AppHeader } from "@/components/app-shell/app-header"
import { LeftNavigation } from "@/components/app-shell/left-navigation"
import { MainContent } from "@/components/app-shell/main-content"
import { DebugPanel } from "@/components/app-shell/debug-panel"
import { StatusPill } from "@/components/app-shell/status-pill"
import { EtlFooter } from "@/components/app-shell/etl-footer"
import { Toaster } from "@/components/ui/sonner"

export default function Page() {
  return (
    <AppProvider>
      <div className="flex h-dvh flex-col bg-background">
        <AppHeader />
        <div className="flex flex-1 overflow-hidden">
          <LeftNavigation />
          <MainContent />
          <DebugPanel />
        </div>
        <StatusPill />
        <EtlFooter />
      </div>
      <Toaster />
    </AppProvider>
  )
}
