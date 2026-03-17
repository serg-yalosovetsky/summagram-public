"use client"

import { motion } from "framer-motion"
import { Switch } from "@/components/ui/switch"
import { Separator } from "@/components/ui/separator"
import { ScrollArea } from "@/components/ui/scroll-area"

const settingsSections = [
  {
    title: "Model Configuration",
    settings: [
      {
        label: "Default Model",
        description: "Primary model for new sessions",
        type: "select" as const,
        value: "gpt-4o",
      },
      {
        label: "Temperature",
        description: "Controls randomness in outputs",
        type: "input" as const,
        value: "0.3",
      },
      {
        label: "Max Output Tokens",
        description: "Maximum tokens per response",
        type: "input" as const,
        value: "4096",
      },
    ],
  },
  {
    title: "Extraction Settings",
    settings: [
      {
        label: "Auto-validate",
        description: "Automatically validate extracted entities",
        type: "toggle" as const,
        value: true,
      },
      {
        label: "Confidence Threshold",
        description: "Minimum confidence score for entity extraction",
        type: "input" as const,
        value: "0.85",
      },
      {
        label: "Stream Responses",
        description: "Enable token streaming for real-time output",
        type: "toggle" as const,
        value: true,
      },
    ],
  },
  {
    title: "Debug & Logging",
    settings: [
      {
        label: "Verbose Logging",
        description: "Log all LLM calls and tool invocations",
        type: "toggle" as const,
        value: false,
      },
      {
        label: "Trace Retention",
        description: "Number of days to retain trace data",
        type: "input" as const,
        value: "30",
      },
      {
        label: "Export Traces",
        description: "Auto-export traces to external observability platform",
        type: "toggle" as const,
        value: false,
      },
    ],
  },
]

export function SettingsView() {
  return (
    <motion.div
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0, y: -12 }}
      transition={{ duration: 0.25, ease: "easeOut" }}
      className="flex h-full flex-col"
    >
      <div className="border-b border-border px-4 py-3">
        <h2 className="text-lg font-semibold text-foreground">Settings</h2>
        <p className="text-sm text-muted-foreground">Configure your ML pipeline defaults</p>
      </div>

      <ScrollArea className="flex-1">
        <div className="flex flex-col gap-6 p-4">
          {settingsSections.map((section) => (
            <div key={section.title}>
              <h3 className="mb-3 text-xs font-semibold uppercase tracking-wider text-muted-foreground">
                {section.title}
              </h3>
              <div className="flex flex-col gap-1 rounded-lg border border-border bg-card">
                {section.settings.map((setting, index) => (
                  <div key={setting.label}>
                    <div className="flex items-center justify-between px-4 py-3">
                      <div>
                        <p className="text-sm font-medium text-foreground">{setting.label}</p>
                        <p className="text-xs text-muted-foreground">{setting.description}</p>
                      </div>
                      {setting.type === "toggle" ? (
                        <Switch defaultChecked={setting.value as boolean} />
                      ) : (
                        <div className="w-36 rounded-md border border-border bg-input px-2.5 py-1.5 text-right text-xs text-foreground">
                          {setting.value as string}
                        </div>
                      )}
                    </div>
                    {index < section.settings.length - 1 && <Separator />}
                  </div>
                ))}
              </div>
            </div>
          ))}
        </div>
      </ScrollArea>
    </motion.div>
  )
}
