"use client"

import { useState, useEffect } from "react"
import {
    Dialog,
    DialogContent,
    DialogHeader,
    DialogTitle,
    DialogDescription,
    DialogFooter,
} from "@/components/ui/dialog"
import { Button } from "@/components/ui/button"
import { Checkbox } from "@/components/ui/checkbox"
import { Progress } from "@/components/ui/progress"
import { Slider } from "@/components/ui/slider"
import { ScrollArea } from "@/components/ui/scroll-area"
import { Badge } from "@/components/ui/badge"
import { Search, Loader2, CheckCircle2, AlertCircle, Users, User, Tv, Archive } from "lucide-react"
import { Input } from "@/components/ui/input"
import { fetchTelegramDialogs, submitTelegramJob, submitAnalyzeChatsJob, subscribeJobStatus, type TelegramDialog, type JobStatus } from "@/lib/api"
import { toast } from "sonner"
import { Sparkles } from "lucide-react"

interface TelegramImportDialogProps {
    open: boolean
    onOpenChange: (open: boolean) => void
    onComplete: () => void
    /** "sync" = full sync with messages; "analyze" = only generate descriptions/tags for selected chats */
    mode?: "sync" | "analyze"
    /** Called when an analyze job is started (so parent can set activeJobId). Not used in sync mode. */
    onJobStarted?: (jobId: string) => void
}

export function TelegramImportDialog({ open, onOpenChange, onComplete, mode = "sync", onJobStarted }: TelegramImportDialogProps) {
    const [dialogs, setDialogs] = useState<TelegramDialog[]>([])
    const [loading, setLoading] = useState(false)
    const [searchQuery, setSearchQuery] = useState("")
    const [selectedIds, setSelectedIds] = useState<Set<number>>(new Set())
    const [daysBack, setDaysBack] = useState(30)

    // Job state
    const [isSyncing, setIsSyncing] = useState(false)
    const [jobId, setJobId] = useState<string | null>(null)
    const [jobStatus, setJobStatus] = useState<JobStatus | null>(null)

    useEffect(() => {
        if (open && dialogs.length === 0) {
            loadDialogs()
        }
    }, [open])

    useEffect(() => {
        if (!jobId) return

        const unsubscribe = subscribeJobStatus(jobId, (status) => {
            setJobStatus(status)

            if (status.status === "completed") {
                setIsSyncing(false)
                toast.success("Sync complete!")
                onComplete()
                onOpenChange(false)
                setJobId(null)
                unsubscribe()
            } else if (status.status === "failed") {
                setIsSyncing(false)
                toast.error(`Sync failed: ${status.error || "Unknown error"}`)
                setJobId(null)
                unsubscribe()
            }
        }, (error) => {
            console.error("Error streaming job status:", error)
        })

        return () => unsubscribe()
    }, [jobId])

    const loadDialogs = async () => {
        setLoading(true)
        try {
            const healthRes = await fetch("/etl/health").catch(() => null)
            if (!healthRes?.ok) {
                throw new Error(
                    "ETL service is not running. Start it with: docker compose up etl (or run uvicorn etl.main:app --port 8002)"
                )
            }
            const data = await fetchTelegramDialogs()
            // Sort: active personal first, then groups, then channels, then archived
            const sorted = [...data].sort((a, b) => {
                if (a.archived !== b.archived) return a.archived ? 1 : -1
                if (a.type !== b.type) {
                    const order = { personal: 0, group: 1, channel: 2, unknown: 3 }
                    return order[a.type] - order[b.type]
                }
                return b.date - a.date
            })
            setDialogs(sorted)

            // Auto-select active personal chats
            const personalIds = sorted
                .filter(d => d.type === "personal" && !d.archived)
                .map(d => d.id)
            setSelectedIds(new Set(personalIds))
        } catch (error) {
            console.error("Failed to load Telegram dialogs:", error)
            const msg = error instanceof Error ? error.message : "Failed to load chats from Telegram"
            toast.error(msg)
        } finally {
            setLoading(false)
        }
    }

    const handleToggleChat = (id: number) => {
        const next = new Set(selectedIds)
        if (next.has(id)) next.delete(id)
        else next.add(id)
        setSelectedIds(next)
    }

    const handleSelectAll = (type?: TelegramDialog["type"]) => {
        const next = new Set(selectedIds)
        filteredDialogs.forEach(d => {
            if (!type || d.type === type) {
                next.add(d.id)
            }
        })
        setSelectedIds(next)
    }

    const handleDeselectAll = () => {
        setSelectedIds(new Set())
    }

    const startSync = async () => {
        if (selectedIds.size === 0) return

        setIsSyncing(true)
        try {
            if (mode === "analyze") {
                const { job_id } = await submitAnalyzeChatsJob(Array.from(selectedIds))
                onJobStarted?.(job_id)
                onComplete()
                onOpenChange(false)
                toast.success("Analysis started")
            } else {
                const { job_id } = await submitTelegramJob({
                    chat_ids: Array.from(selectedIds),
                    days_back: daysBack
                })
                setJobId(job_id)
                onJobStarted?.(job_id)
            }
        } catch (error) {
            console.error(mode === "analyze" ? "Failed to start analysis:" : "Failed to start sync:", error)
            toast.error(mode === "analyze" ? "Failed to start analysis" : "Failed to start synchronization")
            setIsSyncing(false)
        }
    }

    const filteredDialogs = dialogs.filter(d =>
        d.name.toLowerCase().includes(searchQuery.toLowerCase())
    )

    const groupedDialogs = {
        personal: filteredDialogs.filter(d => d.type === "personal" && !d.archived),
        group: filteredDialogs.filter(d => d.type === "group" && !d.archived),
        channel: filteredDialogs.filter(d => d.type === "channel" && !d.archived),
        archived: filteredDialogs.filter(d => d.archived),
    }

    const renderGroup = (title: string, items: TelegramDialog[], icon: React.ReactNode) => {
        if (items.length === 0) return null
        return (
            <div className="mb-6">
                <div className="flex items-center justify-between mb-2 px-1">
                    <h3 className="text-xs font-semibold uppercase tracking-wider text-muted-foreground flex items-center gap-1.5">
                        {icon}
                        {title} ({items.length})
                    </h3>
                </div>
                <div className="space-y-1">
                    {items.map(chat => (
                        <div
                            key={chat.id}
                            className="flex items-center space-x-2 rounded-md p-2 hover:bg-secondary/50 transition-colors cursor-pointer"
                            onClick={() => handleToggleChat(chat.id)}
                        >
                            <Checkbox
                                id={`chat-${chat.id}`}
                                checked={selectedIds.has(chat.id)}
                                onCheckedChange={() => handleToggleChat(chat.id)}
                            />
                            <div className="flex flex-col flex-1 min-w-0">
                                <label
                                    htmlFor={`chat-${chat.id}`}
                                    className="text-sm font-medium leading-none peer-disabled:cursor-not-allowed peer-disabled:opacity-70 truncate cursor-pointer"
                                >
                                    {chat.name}
                                </label>
                                <span className="text-[10px] text-muted-foreground">
                                    Last active: {new Date(chat.date * 1000).toLocaleDateString()}
                                </span>
                            </div>
                            {chat.archived && <Badge variant="outline" className="text-[10px] h-4">Archived</Badge>}
                        </div>
                    ))}
                </div>
            </div>
        )
    }

    return (
        <Dialog open={open} onOpenChange={onOpenChange}>
            <DialogContent className="sm:max-w-[600px] h-[85vh] flex flex-col p-0 overflow-hidden">
                <DialogHeader className="p-6 pb-2">
                    <div className="flex items-start justify-between gap-4">
                        <div className="space-y-1.5">
                            <DialogTitle className="flex items-center gap-2">
                                {mode === "analyze" ? (
                                    <Sparkles className="h-5 w-5 text-primary" />
                                ) : (
                                    <Tv className="h-5 w-5 text-primary" />
                                )}
                                {mode === "analyze" ? "Analyze Chats" : "Sync Telegram Chats"}
                            </DialogTitle>
                            <DialogDescription>
                                {mode === "analyze"
                                    ? "Generate descriptions and tags for selected chats. Only selected chats will be analyzed."
                                    : "Select chats and timeframe to import messages into Summagram. Sync also updates chat descriptions for selected chats."}
                            </DialogDescription>
                        </div>
                        {!isSyncing && (
                            <Button
                                size="sm"
                                onClick={startSync}
                                disabled={loading || selectedIds.size === 0 || (mode === "sync" && daysBack <= 0)}
                            >
                                {mode === "analyze" ? "Analyze selected" : "Sync"}
                            </Button>
                        )}
                    </div>
                </DialogHeader>

                {isSyncing ? (
                    <div className="flex-1 flex flex-col items-center justify-center p-12 space-y-6">
                        <div className="relative">
                            <div className="h-24 w-24 rounded-full border-4 border-primary/20 animate-pulse flex items-center justify-center">
                                {jobStatus?.status === "completed" ? (
                                    <CheckCircle2 className="h-12 w-12 text-green-500" />
                                ) : jobStatus?.status === "failed" ? (
                                    <AlertCircle className="h-12 w-12 text-destructive" />
                                ) : (
                                    <Loader2 className="h-12 w-12 text-primary animate-spin" />
                                )}
                            </div>
                        </div>

                        <div className="w-full max-w-sm space-y-2">
                            <div className="flex justify-between text-sm font-medium">
                                <span>{jobStatus?.message || "Syncing..."}</span>
                                <span>{Math.round((jobStatus?.progress || 0) * 100)}%</span>
                            </div>
                            <Progress value={(jobStatus?.progress || 0) * 100} className="h-2" />
                        </div>

                        <p className="text-center text-sm text-muted-foreground max-w-xs">
                            {jobStatus?.status === "completed"
                                ? "All messages have been imported and indexed."
                                : jobStatus?.status === "failed"
                                    ? "Something went wrong during the sync process."
                                    : "Downloading and processing messages. This may take a few minutes depending on the selected range."}
                        </p>

                        {jobStatus?.status === "completed" && (
                            <Button onClick={() => onOpenChange(false)} variant="outline">Close</Button>
                        )}
                    </div>
                ) : (
                    <>
                        <div className="px-6 py-2 space-y-4">
                            {mode === "sync" && (
                                <div className="space-y-2">
                                    <div className="flex justify-between items-center">
                                        <label className="text-sm font-medium">Lookback Period: {daysBack} days</label>
                                        <span className="text-xs text-muted-foreground">
                                            From {new Date(Date.now() - daysBack * 24 * 60 * 60 * 1000).toLocaleDateString()}
                                        </span>
                                    </div>
                                    <Slider
                                        value={[daysBack]}
                                        onValueChange={(vals) => setDaysBack(vals[0])}
                                        max={365}
                                        min={1}
                                        step={1}
                                    />
                                </div>
                            )}

                            <div className="relative">
                                <Search className="absolute left-2.5 top-2.5 h-4 w-4 text-muted-foreground" />
                                <Input
                                    placeholder="Search chats..."
                                    className="pl-9"
                                    value={searchQuery}
                                    onChange={(e) => setSearchQuery(e.target.value)}
                                />
                            </div>

                            <div className="flex gap-2">
                                <Button variant="outline" size="sm" onClick={() => handleSelectAll()} className="text-[10px] h-7">
                                    Select Filtered
                                </Button>
                                <Button variant="outline" size="sm" onClick={handleDeselectAll} className="text-[10px] h-7">
                                    Deselect All
                                </Button>
                            </div>
                        </div>

                        <ScrollArea className="flex-1 min-h-0 px-6">
                            {loading ? (
                                <div className="flex flex-col items-center justify-center py-12 space-y-3">
                                    <Loader2 className="h-8 w-8 text-primary animate-spin" />
                                    <p className="text-sm text-muted-foreground">Fetching dialogs from Telegram...</p>
                                </div>
                            ) : (
                                <div className="py-2">
                                    {renderGroup("Personal Chats", groupedDialogs.personal, <User className="h-3 w-3" />)}
                                    {renderGroup("Groups", groupedDialogs.group, <Users className="h-3 w-3" />)}
                                    {renderGroup("Channels", groupedDialogs.channel, <Tv className="h-3 w-3" />)}
                                    {renderGroup("Archived", groupedDialogs.archived, <Archive className="h-3 w-3" />)}

                                    {filteredDialogs.length === 0 && (
                                        <div className="text-center py-12 text-muted-foreground italic text-sm">
                                            No chats found matching your search.
                                        </div>
                                    )}
                                </div>
                            )}
                        </ScrollArea>

                        <DialogFooter className="p-6 pt-2 border-t bg-secondary/10">
                            <div className="flex items-center justify-between w-full">
                                <span className="text-xs text-muted-foreground font-medium">
                                    {selectedIds.size} chats selected
                                </span>
                                <div className="flex gap-2">
                                    <Button variant="ghost" onClick={() => onOpenChange(false)}>Cancel</Button>
                                    <Button
                                        disabled={loading || selectedIds.size === 0 || (mode === "sync" && daysBack <= 0)}
                                        onClick={startSync}
                                    >
                                        {mode === "analyze" ? "Analyze selected" : "Sync"}
                                    </Button>
                                </div>
                            </div>
                        </DialogFooter>
                    </>
                )}
            </DialogContent>
        </Dialog>
    )
}
