"use client"

import { useState, useEffect } from "react"
import { useApp } from "../app-shell/app-context"
import { motion } from "framer-motion"
import {
    Sparkles,
    Clock,
    MessageSquare,
    ChevronDown,
    ChevronRight,
    Plus,
} from "lucide-react"
import { Button } from "@/components/ui/button"
import {
    Collapsible,
    CollapsibleContent,
    CollapsibleTrigger,
} from "@/components/ui/collapsible"
import { fetchSessions, createSession, warmModel, type Session } from "@/lib/api"

export function SessionsView() {
    const { setCurrentView, setActiveSessionId } = useApp()
    const [configOpen, setConfigOpen] = useState(false)
    const [sessions, setSessions] = useState<Session[]>([])
    const [loading, setLoading] = useState(true)

    useEffect(() => {
        fetchSessions()
            .then(setSessions)
            .catch(console.error)
            .finally(() => setLoading(false))
    }, [])

    const handleCreateSession = async () => {
        const id = crypto.randomUUID()
        const title = `New Session ${new Date().toLocaleDateString()}`
        // Pre-warm the text model immediately when the user creates a session
        warmModel("text")
        try {
            const session = await createSession(id, title)
            setSessions(prev => [session, ...prev])
            setActiveSessionId(id)
            setCurrentView("chat")
        } catch (error) {
            console.error("Failed to create session:", error)
        }
    }

    if (loading) return <div className="p-8 text-center text-sm text-muted-foreground">Loading sessions...</div>

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
                            <Sparkles className="h-5 w-5 text-primary" />
                            AI Sessions
                        </h2>
                        <p className="text-sm text-muted-foreground">
                            Your recent interactions and queries
                        </p>
                    </div>
                    <Button
                        size="sm"
                        className="gap-2"
                        onClick={handleCreateSession}
                    >
                        <Plus className="h-4 w-4" />
                        New Session
                    </Button>
                </div>

                <Collapsible open={configOpen} onOpenChange={setConfigOpen} className="mt-3">
                    <CollapsibleTrigger asChild>
                        <Button
                            variant="ghost"
                            size="sm"
                            className="h-7 gap-2 text-xs text-muted-foreground hover:text-foreground"
                        >
                            <Clock className="h-3 w-3" />
                            Recent Sessions
                            {configOpen ? (
                                <ChevronDown className="h-3 w-3" />
                            ) : (
                                <ChevronRight className="h-3 w-3" />
                            )}
                        </Button>
                    </CollapsibleTrigger>
                    <CollapsibleContent>
                        <div className="mt-2 p-3 text-xs text-muted-foreground bg-secondary/30 rounded-lg">
                            History management coming soon...
                        </div>
                    </CollapsibleContent>
                </Collapsible>
            </div>

            <div className="grid grid-cols-1 gap-3 p-4 md:grid-cols-2 lg:grid-cols-3">
                {sessions.map((session, index) => (
                    <motion.div
                        key={session.id}
                        initial={{ opacity: 0, y: 8 }}
                        animate={{ opacity: 1, y: 0 }}
                        transition={{ delay: index * 0.05, duration: 0.2 }}
                        className="group flex cursor-pointer flex-col items-start rounded-lg border border-border bg-card p-4 text-left transition-colors hover:border-primary/40 hover:bg-secondary/50"
                        role="button"
                        tabIndex={0}
                        onClick={() => {
                            warmModel("text")
                            setActiveSessionId(session.id)
                            setCurrentView("chat")
                        }}
                        onKeyDown={(e) => {
                            if (e.key === "Enter" || e.key === " ") {
                                e.preventDefault()
                                warmModel("text")
                                setActiveSessionId(session.id)
                                setCurrentView("chat")
                            }
                        }}
                    >
                        <div className="flex w-full items-start justify-between">
                            <div className="flex items-center gap-2">
                                <div className="flex h-6 w-6 items-center justify-center rounded-md bg-primary/10 text-primary group-hover:bg-primary group-hover:text-primary-foreground transition-colors">
                                    <MessageSquare className="h-3.5 w-3.5" />
                                </div>
                                <span className="text-sm font-medium text-foreground group-hover:text-primary line-clamp-1">
                                    {session.title || `Session ${session.id.substring(0, 8)}`}
                                </span>
                            </div>
                        </div>
                        <p className="mt-2 line-clamp-2 text-xs text-muted-foreground">
                            {session.context_chat_id ? `Analyzing Chat #${session.context_chat_id}` : "AI Analysis Session"}
                        </p>
                        <div className="mt-4 flex w-full items-center justify-between text-[11px] text-muted-foreground">
                            <span className="flex items-center gap-1">
                                <Clock className="h-3 w-3" />
                                Last updated {new Date(session.updated_at).toLocaleDateString()}
                            </span>
                            <span className="text-primary text-[11px] font-medium opacity-0 group-hover:opacity-100 transition-opacity">
                                Open Session →
                            </span>
                        </div>
                    </motion.div>
                ))}
                {sessions.length === 0 && (
                    <div className="col-span-full py-12 text-center">
                        <Sparkles className="mx-auto h-12 w-12 text-muted-foreground/20" />
                        <h3 className="mt-4 text-sm font-medium text-foreground">No active sessions</h3>
                        <p className="mt-1 text-xs text-muted-foreground">Start a new session to ask your data questions.</p>
                        <Button
                            variant="outline"
                            size="sm"
                            className="mt-4"
                            onClick={handleCreateSession}
                        >
                            New Session
                        </Button>
                    </div>
                )}
            </div>
        </motion.div>
    )
}
