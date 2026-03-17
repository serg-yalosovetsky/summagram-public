"use client"

import { useApp } from "../app-shell/app-context"
import { motion, AnimatePresence } from "framer-motion"
import { Loader2, CheckCircle2 } from "lucide-react"

export function StatusPill() {
  const { processingTask, activeJobId } = useApp()

  return (
    <div className="fixed bottom-4 right-4 z-50">
      <AnimatePresence mode="wait">
        {processingTask && !activeJobId ? (
          <motion.div
            key="active"
            initial={{ scale: 0.8, opacity: 0 }}
            animate={{ scale: 1, opacity: 1 }}
            exit={{ scale: 0.8, opacity: 0 }}
            transition={{ type: "spring", damping: 20, stiffness: 300 }}
            className="flex items-center gap-2.5 rounded-full border border-border px-4 py-2 shadow-lg backdrop-blur-xl"
            style={{ backgroundColor: "oklch(0.17 0.005 285 / 0.9)" }}
          >
            {processingTask.progress >= 100 ? (
              <CheckCircle2 className="h-4 w-4 text-chart-2" />
            ) : (
              <Loader2 className="h-4 w-4 animate-spin text-primary" />
            )}
            <span className="text-xs font-medium text-foreground">
              {processingTask.progress >= 100
                ? "Complete"
                : `${processingTask.label} (${Math.round(processingTask.progress)}%)`}
            </span>
            <div className="h-1 w-16 overflow-hidden rounded-full bg-secondary">
              <motion.div
                className="h-full rounded-full bg-primary"
                initial={{ width: 0 }}
                animate={{ width: `${processingTask.progress}%` }}
                transition={{ duration: 0.3 }}
              />
            </div>
          </motion.div>
        ) : (
          <motion.div
            key="idle"
            initial={{ scale: 0.5, opacity: 0 }}
            animate={{ scale: 1, opacity: 1 }}
            exit={{ scale: 0.5, opacity: 0 }}
            className="h-3 w-3 rounded-full bg-muted-foreground/30"
            title="No background tasks"
          />
        )}
      </AnimatePresence>
    </div>
  )
}
