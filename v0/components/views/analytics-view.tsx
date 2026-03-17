"use client"

import { useState, useEffect } from "react"
import { motion } from "framer-motion"
import {
  Cpu,
  HardDrive,
  Layers,
  Eye,
  Mic,
  FileText,
  CircleDot,
  AlertCircle,
} from "lucide-react"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { Progress } from "@/components/ui/progress"
import { fetchSystemStatus, subscribeSystemStatus, type SystemStatus } from "@/lib/api"

const MODEL_TYPE_META: Record<string, { icon: typeof Eye; label: string }> = {
  vision: { icon: Eye, label: "Vision" },
  audio: { icon: Mic, label: "Audio" },
  document: { icon: FileText, label: "Document" },
}

function formatMb(mb: number): string {
  if (mb >= 1024) return `${(mb / 1024).toFixed(1)} GB`
  return `${Math.round(mb)} MB`
}

export function AnalyticsView() {
  const [status, setStatus] = useState<SystemStatus | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    const unsubscribe = subscribeSystemStatus(
      (data) => {
        setStatus(data)
        setError(null)
      },
      () => {
        setError("Connection lost")
      }
    )
    return unsubscribe
  }, [])

  const gpu = status?.gpu
  const usedPercent =
    gpu?.memory_total_mb && gpu.memory_reserved_mb
      ? (gpu.memory_reserved_mb / gpu.memory_total_mb) * 100
      : 0
  const allocPercent =
    gpu?.memory_total_mb && gpu.memory_allocated_mb
      ? (gpu.memory_allocated_mb / gpu.memory_total_mb) * 100
      : 0

  return (
    <motion.div
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0, y: -12 }}
      transition={{ duration: 0.25, ease: "easeOut" }}
      className="flex h-full flex-col overflow-auto"
    >
      <div className="border-b border-border p-4">
        <h2 className="text-lg font-semibold text-foreground flex items-center gap-2">
          <Cpu className="h-5 w-5 text-primary" />
          System Status
        </h2>
        <p className="text-sm text-muted-foreground">
          GPU resources, task queue, and model configuration
        </p>
      </div>

      {error && !status && (
        <div className="m-4 flex items-center gap-2 rounded-lg border border-destructive/40 bg-destructive/10 p-3 text-sm text-destructive">
          <AlertCircle className="h-4 w-4 shrink-0" />
          Backend unreachable: {error}
        </div>
      )}

      <div className="grid grid-cols-1 gap-4 p-4 md:grid-cols-2">
        {/* Active Model */}
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="flex items-center gap-2 text-sm">
              <CircleDot className="h-4 w-4 text-primary" />
              Active Model
            </CardTitle>
          </CardHeader>
          <CardContent>
            {status?.current_model ? (
              <div className="flex items-center gap-2">
                {(() => {
                  const meta = MODEL_TYPE_META[status.current_model]
                  const Icon = meta?.icon ?? Layers
                  return <Icon className="h-5 w-5 text-primary" />
                })()}
                <span className="text-2xl font-bold capitalize">
                  {MODEL_TYPE_META[status.current_model]?.label ?? status.current_model}
                </span>
                <Badge variant="default" className="ml-auto">
                  In VRAM
                </Badge>
              </div>
            ) : (
              <span className="text-muted-foreground text-sm">
                {status ? "Idle -- no model loaded" : "Loading..."}
              </span>
            )}
          </CardContent>
        </Card>

        {/* Task Queue */}
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="flex items-center gap-2 text-sm">
              <Layers className="h-4 w-4 text-primary" />
              Task Queue
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">
              {status?.total_pending ?? "--"}
              <span className="ml-1 text-sm font-normal text-muted-foreground">pending</span>
            </div>
            {status && (
              <div className="mt-2 flex flex-wrap gap-2">
                {Object.entries(status.queue).map(([key, count]) => {
                  const meta = MODEL_TYPE_META[key]
                  return (
                    <Badge
                      key={key}
                      variant={count > 0 ? "default" : "secondary"}
                      className="gap-1"
                    >
                      {meta?.label ?? key}: {count}
                    </Badge>
                  )
                })}
              </div>
            )}
          </CardContent>
        </Card>

        {/* GPU Memory */}
        <Card className="md:col-span-2">
          <CardHeader className="pb-2">
            <CardTitle className="flex items-center gap-2 text-sm">
              <HardDrive className="h-4 w-4 text-primary" />
              GPU Memory
              {gpu?.gpu_name && (
                <span className="ml-auto text-xs font-normal text-muted-foreground">
                  {gpu.gpu_name}
                </span>
              )}
            </CardTitle>
          </CardHeader>
          <CardContent>
            {gpu?.cuda_available ? (
              <div className="space-y-3">
                {/* Visual bar */}
                <div className="relative h-6 w-full overflow-hidden rounded-full bg-muted">
                  {/* Reserved (vcache + fragmentation) */}
                  <div
                    className="absolute inset-y-0 left-0 rounded-full bg-primary/30 transition-all"
                    style={{ width: `${usedPercent}%` }}
                  />
                  {/* Allocated (model weights) */}
                  <div
                    className="absolute inset-y-0 left-0 rounded-full bg-primary transition-all"
                    style={{ width: `${allocPercent}%` }}
                  />
                </div>

                <div className="grid grid-cols-2 gap-x-6 gap-y-1 text-sm sm:grid-cols-4">
                  <div>
                    <span className="text-muted-foreground">Model (allocated)</span>
                    <p className="font-medium">{formatMb(gpu.memory_allocated_mb ?? 0)}</p>
                  </div>
                  <div>
                    <span className="text-muted-foreground">Reserved (+ vcache)</span>
                    <p className="font-medium">{formatMb(gpu.memory_reserved_mb ?? 0)}</p>
                  </div>
                  <div>
                    <span className="text-muted-foreground">Free</span>
                    <p className="font-medium">{formatMb(gpu.memory_free_mb ?? 0)}</p>
                  </div>
                  <div>
                    <span className="text-muted-foreground">Total</span>
                    <p className="font-medium">{formatMb(gpu.memory_total_mb ?? 0)}</p>
                  </div>
                </div>

                {/* Legend */}
                <div className="flex items-center gap-4 text-xs text-muted-foreground">
                  <span className="flex items-center gap-1">
                    <span className="inline-block h-2.5 w-2.5 rounded-sm bg-primary" />
                    Model weights
                  </span>
                  <span className="flex items-center gap-1">
                    <span className="inline-block h-2.5 w-2.5 rounded-sm bg-primary/30" />
                    Reserved (vcache)
                  </span>
                  <span className="flex items-center gap-1">
                    <span className="inline-block h-2.5 w-2.5 rounded-sm bg-muted border" />
                    Free
                  </span>
                </div>
              </div>
            ) : (
              <span className="text-sm text-muted-foreground">
                {status ? "CUDA not available" : "Loading..."}
              </span>
            )}
          </CardContent>
        </Card>

        {/* Model Configuration */}
        <Card className="md:col-span-2">
          <CardHeader className="pb-2">
            <CardTitle className="flex items-center gap-2 text-sm">
              <Cpu className="h-4 w-4 text-primary" />
              Configured Models
            </CardTitle>
          </CardHeader>
          <CardContent>
            {status ? (
              <div className="grid grid-cols-1 gap-2 sm:grid-cols-2">
                {Object.entries(status.models_config).map(([key, model]) => (
                  <div
                    key={key}
                    className="flex items-start justify-between rounded-lg border border-border bg-secondary/30 px-3 py-2"
                  >
                    <div>
                      <span className="text-xs font-medium uppercase text-muted-foreground">
                        {key}
                      </span>
                      <p className="text-sm font-medium break-all">{model}</p>
                    </div>
                    {status.current_model === key && (
                      <Badge variant="default" className="ml-2 shrink-0">Active</Badge>
                    )}
                  </div>
                ))}
              </div>
            ) : (
              <span className="text-sm text-muted-foreground">Loading...</span>
            )}
          </CardContent>
        </Card>
      </div>

      {/* Container Metrics */}
      <div className="p-4 pt-0">
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="flex items-center gap-2 text-sm">
              <Layers className="h-4 w-4 text-primary" />
              Containers
            </CardTitle>
          </CardHeader>
          <CardContent>
            {status?.containers && status.containers.length > 0 ? (
              <div className="overflow-x-auto">
                <table className="w-full text-sm text-left">
                  <thead className="text-xs uppercase bg-muted text-muted-foreground">
                    <tr>
                      <th className="px-4 py-2 font-medium">Name</th>
                      <th className="px-4 py-2 font-medium text-right">CPU</th>
                      <th className="px-4 py-2 font-medium text-right">RAM</th>
                      <th className="px-4 py-2 font-medium text-right">Limit</th>
                      <th className="px-4 py-2 font-medium text-right">RAM %</th>
                      <th className="px-4 py-2 font-medium text-right">VRAM</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-border">
                    {status.containers.map((c) => (
                      <tr key={c.name} className="hover:bg-muted/50 transition-colors">
                        <td className="px-4 py-2 font-medium whitespace-nowrap">{c.name}</td>
                        <td className="px-4 py-2 text-right tabular-nums">{c.cpu_perc.toFixed(2)}%</td>
                        <td className="px-4 py-2 text-right tabular-nums">{formatMb(c.mem_used_b / 1024 / 1024)}</td>
                        <td className="px-4 py-2 text-right tabular-nums">{formatMb(c.mem_limit_b / 1024 / 1024)}</td>
                        <td className="px-4 py-2 text-right tabular-nums">{c.mem_perc.toFixed(2)}%</td>
                        <td className="px-4 py-2 text-right tabular-nums">{c.vram_used_mib} MiB</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ) : (
              <span className="text-sm text-muted-foreground">No container metrics available</span>
            )}
          </CardContent>
        </Card>
      </div>
    </motion.div>
  )
}
