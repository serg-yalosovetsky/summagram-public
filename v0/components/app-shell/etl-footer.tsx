"use client"

import { useApp } from "./app-context"
import { motion, AnimatePresence } from "framer-motion"
import { Progress } from "@/components/ui/progress"
import { Loader2, CheckCircle2, AlertCircle } from "lucide-react"

export function EtlFooter() {
    const { processingTask, activeJobId } = useApp()

    // Only show the footer if there's an active job OR a processing task (which stays for a bit after completion)
    const isVisible = !!activeJobId || !!processingTask

    return (
        <AnimatePresence>
            {isVisible && (
                <motion.div
                    initial={{ y: 100, opacity: 0 }}
                    animate={{ y: 0, opacity: 1 }}
                    exit={{ y: 100, opacity: 0 }}
                    transition={{ type: "spring", damping: 25, stiffness: 200 }}
                    className="fixed bottom-0 left-0 right-0 z-50 border-t border-border bg-background/80 px-6 py-3 backdrop-blur-xl shadow-[0_-4px_24px_-8px_rgba(0,0,0,0.5)]"
                >
                    <div className="mx-auto flex max-w-7xl items-center gap-6">
                        <div className="flex shrink-0 items-center gap-3 min-w-[200px]">
                            {processingTask && processingTask.progress >= 100 ? (
                                <div className="flex h-8 w-8 items-center justify-center rounded-full bg-chart-2/10 text-chart-2">
                                    <CheckCircle2 className="h-5 w-5" />
                                </div>
                            ) : (
                                <div className="flex h-8 w-8 items-center justify-center rounded-full bg-primary/10 text-primary">
                                    <Loader2 className="h-5 w-5 animate-spin" />
                                </div>
                            )}
                            <div className="flex flex-col">
                                <span className="text-[10px] font-bold uppercase tracking-wider text-muted-foreground/60">
                                    ETL Pipeline Action
                                </span>
                                <span className="text-sm font-medium text-foreground line-clamp-1">
                                    {processingTask?.label || "Initializing..."}
                                </span>
                            </div>
                        </div>

                        <div className="flex flex-1 flex-col gap-1.5">
                            <div className="flex items-center justify-between text-[10px] font-medium uppercase tracking-tight text-muted-foreground/80">
                                <span>Progress</span>
                                <span className="tabular-nums">{Math.round(processingTask?.progress || 0)}%</span>
                            </div>
                            <Progress value={processingTask?.progress || 0} className="h-1.5" />
                        </div>

                        <div className="flex shrink-0 items-center gap-2">
                            <div className="h-1.5 w-1.5 rounded-full bg-primary animate-pulse" />
                            <span className="text-[10px] font-mono text-muted-foreground/50 tabular-nums">
                                {activeJobId?.split('-')[0] || 'active'}
                            </span>
                        </div>
                    </div>
                </motion.div>
            )}
        </AnimatePresence>
    )
}
