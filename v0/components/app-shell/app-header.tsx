"use client"

import { useApp } from "./app-context"
import { Terminal } from "lucide-react"
import { Button } from "@/components/ui/button"

export function AppHeader() {
  const { toggleDebugPanel, debugPanelOpen } = useApp()

  return (
    <header className="flex h-14 shrink-0 items-center justify-between border-b border-border bg-card px-4">
      <div className="flex items-center gap-3">
        <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-primary">
          <span className="text-sm font-bold text-primary-foreground">S</span>
        </div>
        <h1 className="text-sm font-semibold text-foreground tracking-tight">summagram</h1>
        <span className="rounded-md bg-secondary px-2 py-0.5 text-[10px] font-medium uppercase tracking-wider text-muted-foreground">
          version 0.1
        </span>
      </div>

      <div className="flex items-center gap-2">
        <Button
          variant="ghost"
          size="icon"
          className={`h-8 w-8 ${debugPanelOpen ? "bg-primary/15 text-primary" : "text-muted-foreground hover:text-foreground"}`}
          onClick={toggleDebugPanel}
          aria-label="Toggle debug panel"
        >
          <Terminal className="h-4 w-4" />
        </Button>
      </div>
    </header>
  )
}
