"use client"

import { useApp } from "./app-context"
import { motion, AnimatePresence } from "framer-motion"
import { X, Layers, Activity, ScrollText } from "lucide-react"
import { Button } from "@/components/ui/button"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { ScrollArea } from "@/components/ui/scroll-area"

const traceData = [
  { id: 1, type: "LLM_CALL", model: "gpt-4o", latency: "1.2s", tokens: 847 },
  { id: 2, type: "TOOL_USE", tool: "search_docs", latency: "0.3s", tokens: null },
  { id: 3, type: "LLM_CALL", model: "gpt-4o", latency: "2.1s", tokens: 1203 },
  { id: 4, type: "EMBEDDING", model: "text-3-small", latency: "0.1s", tokens: 256 },
  { id: 5, type: "RETRIEVAL", source: "vector_db", latency: "0.08s", tokens: null },
]

const stateData = [
  { key: "session_id", value: "sess_7f2a9b" },
  { key: "model", value: "gpt-4o" },
  { key: "temperature", value: "0.7" },
  { key: "max_tokens", value: "4096" },
  { key: "context_window", value: "128k" },
  { key: "tools_enabled", value: "true" },
  { key: "memory_strategy", value: "sliding_window" },
]

const logData = [
  { ts: "12:04:01", level: "INFO", msg: "Session initialized" },
  { ts: "12:04:02", level: "DEBUG", msg: "Loading context from vector store..." },
  { ts: "12:04:03", level: "INFO", msg: "Retrieved 12 chunks (score > 0.8)" },
  { ts: "12:04:04", level: "WARN", msg: "Token limit approaching (87%)" },
  { ts: "12:04:05", level: "INFO", msg: "LLM response generated" },
  { ts: "12:04:06", level: "DEBUG", msg: "Tool call: search_docs executed" },
  { ts: "12:04:07", level: "ERROR", msg: "Rate limit exceeded, retrying..." },
  { ts: "12:04:09", level: "INFO", msg: "Retry successful" },
]

export function DebugPanel() {
  const { debugPanelOpen, toggleDebugPanel } = useApp()

  return (
    <AnimatePresence>
      {debugPanelOpen && (
        <motion.aside
          initial={{ width: 0, opacity: 0 }}
          animate={{ width: 400, opacity: 1 }}
          exit={{ width: 0, opacity: 0 }}
          transition={{ type: "spring", damping: 25, stiffness: 300 }}
          className="shrink-0 overflow-hidden border-l border-border backdrop-blur-xl"
          style={{ backgroundColor: "oklch(0.15 0.005 285 / 0.85)" }}
        >
          <div className="flex h-full w-[400px] flex-col">
            <div className="flex h-10 items-center justify-between border-b border-border px-3">
              <span className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
                Debug Inspector
              </span>
              <Button
                variant="ghost"
                size="icon"
                className="h-6 w-6 text-muted-foreground hover:text-foreground"
                onClick={toggleDebugPanel}
                aria-label="Close debug panel"
              >
                <X className="h-3.5 w-3.5" />
              </Button>
            </div>

            <Tabs defaultValue="trace" className="flex flex-1 flex-col overflow-hidden">
              <TabsList className="mx-3 mt-2 h-8 w-auto bg-secondary">
                <TabsTrigger value="trace" className="gap-1.5 text-xs">
                  <Layers className="h-3 w-3" />
                  Trace
                </TabsTrigger>
                <TabsTrigger value="state" className="gap-1.5 text-xs">
                  <Activity className="h-3 w-3" />
                  State
                </TabsTrigger>
                <TabsTrigger value="logs" className="gap-1.5 text-xs">
                  <ScrollText className="h-3 w-3" />
                  Logs
                </TabsTrigger>
              </TabsList>

              <TabsContent value="trace" className="flex-1 overflow-hidden p-0">
                <ScrollArea className="h-full">
                  <div className="flex flex-col gap-2 p-3">
                    {traceData.map((trace) => (
                      <div
                        key={trace.id}
                        className="rounded-md border border-border bg-secondary/50 p-2.5"
                      >
                        <div className="flex items-center justify-between">
                          <span className="rounded bg-primary/15 px-1.5 py-0.5 font-mono text-[10px] font-medium text-primary">
                            {trace.type}
                          </span>
                          <span className="font-mono text-[10px] text-muted-foreground">
                            {trace.latency}
                          </span>
                        </div>
                        <div className="mt-1.5 flex items-center gap-2 text-[11px] text-muted-foreground">
                          <span>{trace.model || trace.tool || trace.source}</span>
                          {trace.tokens && (
                            <>
                              <span className="text-border">|</span>
                              <span>{trace.tokens} tokens</span>
                            </>
                          )}
                        </div>
                      </div>
                    ))}
                  </div>
                </ScrollArea>
              </TabsContent>

              <TabsContent value="state" className="flex-1 overflow-hidden p-0">
                <ScrollArea className="h-full">
                  <div className="flex flex-col gap-1 p-3">
                    {stateData.map((item) => (
                      <div
                        key={item.key}
                        className="flex items-center justify-between rounded-md px-2 py-1.5 text-xs hover:bg-secondary/50"
                      >
                        <span className="font-mono text-muted-foreground">{item.key}</span>
                        <span className="font-mono text-foreground">{item.value}</span>
                      </div>
                    ))}
                  </div>
                </ScrollArea>
              </TabsContent>

              <TabsContent value="logs" className="flex-1 overflow-hidden p-0">
                <ScrollArea className="h-full">
                  <div className="flex flex-col gap-0.5 p-3">
                    {logData.map((log, i) => (
                      <div
                        key={i}
                        className="flex items-start gap-2 rounded px-1.5 py-1 font-mono text-[11px] hover:bg-secondary/50"
                      >
                        <span className="shrink-0 text-muted-foreground">{log.ts}</span>
                        <span
                          className={`shrink-0 font-semibold ${
                            log.level === "ERROR"
                              ? "text-destructive"
                              : log.level === "WARN"
                                ? "text-chart-4"
                                : log.level === "DEBUG"
                                  ? "text-muted-foreground"
                                  : "text-primary"
                          }`}
                        >
                          {log.level}
                        </span>
                        <span className="text-foreground/80">{log.msg}</span>
                      </div>
                    ))}
                  </div>
                </ScrollArea>
              </TabsContent>
            </Tabs>
          </div>
        </motion.aside>
      )}
    </AnimatePresence>
  )
}
