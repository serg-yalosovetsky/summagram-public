"use client"

import { useApp, type AppView } from "./app-context"
import {
  MessageSquare,
  FolderOpen,
  Settings,
  Plus,
  Search,
  Database,
  Layers,
  Workflow,
  FileText,
  BarChart3,
  Sparkles,
  Bot,
  Share2,
  type LucideIcon,
} from "lucide-react"
import { Button } from "@/components/ui/button"
import { cn } from "@/lib/utils"
import { createSession } from "@/lib/api"

interface NavItem {
  icon: LucideIcon
  label: string
  view?: AppView
  active?: boolean
}

const navigationSections = [
  {
    title: "Navigation",
    items: [
      { icon: MessageSquare, label: "Chats", view: "session-select" },
      { icon: Bot, label: "Sessions", view: "sessions" },
      { icon: Database, label: "Datasets", view: "datasets" },
      { icon: Workflow, label: "Pipelines", view: "pipeline" },
      { icon: Share2, label: "Network", view: "network" },
      { icon: BarChart3, label: "Analytics", view: "analytics" },
    ] as NavItem[],
  },
]

const chatItems: NavItem[] = [
  { icon: MessageSquare, label: "Chat", view: "chat" },
  { icon: FileText, label: "Documents", view: "documents" },
  { icon: Layers, label: "Context", view: "context" },
  { icon: Search, label: "Search", view: "search" },
]

const settingsItems: NavItem[] = [
  { icon: Settings, label: "General", view: "settings" },
  { icon: Workflow, label: "Integrations", view: "integrations" },
]

export function LeftNavigation() {
  const { currentView, setCurrentView, activeSessionId, setActiveSessionId } = useApp()

  const handleNewSession = async () => {
    const id = crypto.randomUUID()
    try {
      await createSession(id, `Analysis Session ${new Date().toLocaleDateString()}`)
      setActiveSessionId(id)
      setCurrentView("chat")
    } catch (error) {
      console.error("Failed to create new session:", error)
    }
  }

  return (
    <nav className="flex w-56 shrink-0 flex-col border-r border-border bg-sidebar">
      <div className="flex flex-col gap-1 p-3 overflow-y-auto">
        <Button
          className="mb-4 justify-start gap-2 bg-primary text-primary-foreground hover:bg-primary/90"
          size="sm"
          onClick={handleNewSession}
        >
          <Plus className="h-4 w-4" />
          New Session
        </Button>

        {/* Main Navigation */}
        {navigationSections.map((section) => (
          <div key={section.title} className="flex flex-col gap-1 pb-4">
            <div className="mb-1 px-2 pt-2">
              <span className="text-[10px] font-semibold uppercase tracking-wider text-muted-foreground">
                {section.title}
              </span>
            </div>
            {section.items.map((item) => {
              const isActive = item.view === currentView
              return (
                <button
                  key={item.label}
                  className={cn(
                    "flex items-center gap-3 rounded-md px-2 py-1.5 text-sm font-medium transition-colors",
                    isActive
                      ? "bg-sidebar-accent text-sidebar-accent-foreground"
                      : "text-muted-foreground hover:bg-sidebar-accent/50 hover:text-sidebar-foreground"
                  )}
                  onClick={() => item.view && setCurrentView(item.view)}
                >
                  <item.icon className="h-4 w-4" />
                  {item.label}
                </button>
              )
            })}
          </div>
        ))}

        {/* Current Session - only if active or in chat related views */}
        {(activeSessionId || ["chat", "documents", "context", "search"].includes(currentView)) && (
          <div className="flex flex-col gap-1 pb-4">
            <div className="mb-1 px-2 pt-2">
              <span className="text-[10px] font-semibold uppercase tracking-wider text-muted-foreground">
                Current Session
              </span>
            </div>
            {chatItems.map((item) => {
              const isActive = item.view === currentView
              return (
                <button
                  key={item.label}
                  className={cn(
                    "flex items-center gap-3 rounded-md px-2 py-1.5 text-sm font-medium transition-colors",
                    isActive
                      ? "bg-sidebar-accent text-sidebar-accent-foreground"
                      : "text-muted-foreground hover:bg-sidebar-accent/50 hover:text-sidebar-foreground"
                  )}
                  onClick={() => item.view && setCurrentView(item.view)}
                >
                  <item.icon className="h-4 w-4" />
                  {item.label}
                </button>
              )
            })}
          </div>
        )}

        {/* Settings Section - Persistent */}
        <div className="flex flex-col gap-1 pb-4 mt-auto">
          <div className="mb-1 px-2 pt-2">
            <span className="text-[10px] font-semibold uppercase tracking-wider text-muted-foreground">
              Settings
            </span>
          </div>
          {settingsItems.map((item) => {
            const isActive = item.view === currentView
            return (
              <button
                key={item.label}
                className={cn(
                  "flex items-center gap-3 rounded-md px-2 py-1.5 text-sm font-medium transition-colors",
                  isActive
                    ? "bg-sidebar-accent text-sidebar-accent-foreground"
                    : "text-muted-foreground hover:bg-sidebar-accent/50 hover:text-sidebar-foreground"
                )}
                onClick={() => item.view && setCurrentView(item.view)}
              >
                <item.icon className="h-4 w-4" />
                {item.label}
              </button>
            )
          })}
        </div>
      </div>

      <div className="mt-auto border-t border-sidebar-border p-3">
        <div className="flex items-center gap-3 rounded-md px-2 py-1.5">
          <div className="flex h-7 w-7 items-center justify-center rounded-full bg-primary/20 text-xs font-medium text-primary">
            AK
          </div>
          <div className="flex flex-col">
            <span className="text-xs font-medium text-sidebar-foreground">A. Kowalski</span>
            <span className="text-[10px] text-muted-foreground">Pro Plan</span>
          </div>
        </div>
      </div>
    </nav>
  )
}
