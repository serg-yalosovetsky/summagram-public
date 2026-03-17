"use client"

import { useEffect, useState } from "react"
import { motion } from "framer-motion"
import { ScrollArea } from "@/components/ui/scroll-area"
import { Switch } from "@/components/ui/switch"
import { Separator } from "@/components/ui/separator"
import { Button } from "@/components/ui/button"
import { Workflow, Save } from "lucide-react"
import { fetchConfig, updateConfig, type Config } from "@/lib/api"

export function PipelineView() {
    const [config, setConfig] = useState<Config | null>(null)
    const [loading, setLoading] = useState(true)
    const [saving, setSaving] = useState(false)

    useEffect(() => {
        fetchConfig()
            .then(setConfig)
            .catch(console.error)
            .finally(() => setLoading(false))
    }, [])

    const handleSave = async () => {
        if (!config) return
        setSaving(true)
        try {
            // Just sending back the whole config for now as the update endpoint accepts partials
            await updateConfig(config)
        } catch (e) {
            console.error(e)
        } finally {
            setSaving(false)
        }
    }

    const updateField = (key: keyof Config, value: any) => {
        if (!config) return
        setConfig({ ...config, [key]: value })
    }

    if (loading) return <div className="p-8 text-center">Loading pipeline settings...</div>

    return (
        <motion.div
            initial={{ opacity: 0, y: 12 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -12 }}
            transition={{ duration: 0.25, ease: "easeOut" }}
            className="flex h-full flex-col"
        >
            <div className="flex items-center justify-between border-b border-border px-4 py-3">
                <div>
                    <div className="flex items-center gap-2">
                        <Workflow className="h-5 w-5 text-muted-foreground" />
                        <h2 className="text-lg font-semibold text-foreground">Pipeline Configuration</h2>
                    </div>
                    <p className="text-sm text-muted-foreground">Manage data sources and model parameters</p>
                </div>
                <Button size="sm" onClick={handleSave} disabled={saving}>
                    <Save className="mr-2 h-4 w-4" />
                    {saving ? "Saving..." : "Save Changes"}
                </Button>
            </div>

            <ScrollArea className="flex-1 min-h-0">
                <div className="flex flex-col gap-6 p-4">
                    {/* Model Configuration */}
                    <div>
                        <h3 className="mb-3 text-xs font-semibold uppercase tracking-wider text-muted-foreground">
                            Model Configuration
                        </h3>
                        <div className="flex flex-col gap-1 rounded-lg border border-border bg-card">

                            {/* Text Model */}
                            <div className="flex items-center justify-between px-4 py-3">
                                <div>
                                    <p className="text-sm font-medium text-foreground">Text Model (HF)</p>
                                    <p className="text-xs text-muted-foreground">HuggingFace Hub ID for text generation</p>
                                </div>
                                <input
                                    className="w-64 rounded-md border border-border bg-input px-2.5 py-1.5 text-xs text-foreground"
                                    value={config?.HF_MODEL_TEXT || ""}
                                    onChange={(e) => updateField("HF_MODEL_TEXT", e.target.value)}
                                    disabled // Typically read-only from env, but let's show it
                                />
                            </div>
                            <Separator />

                            {/* Vision Provider */}
                            <div className="flex items-center justify-between px-4 py-3">
                                <div>
                                    <p className="text-sm font-medium text-foreground">Vision Provider</p>
                                    <p className="text-xs text-muted-foreground">"local" (SmolVLM) or "ollama" (LLaVA)</p>
                                </div>
                                <select
                                    className="w-36 rounded-md border border-border bg-input px-2 py-1.5 text-xs text-foreground"
                                    value={config?.VISION_PROVIDER || "local"}
                                    onChange={(e) => updateField("VISION_PROVIDER", e.target.value)}
                                >
                                    <option value="local">Local (Transformers)</option>
                                    <option value="ollama">Ollama</option>
                                </select>
                            </div>
                        </div>
                    </div>

                    {/* Data Sources Placeholder */}
                    <div>
                        <h3 className="mb-3 text-xs font-semibold uppercase tracking-wider text-muted-foreground">
                            Data Sources (Read-Only)
                        </h3>
                        <div className="flex flex-col gap-1 rounded-lg border border-border bg-card">
                            <div className="flex items-center justify-between px-4 py-3">
                                <div>
                                    <p className="text-sm font-medium text-foreground">Telegram</p>
                                    <p className="text-xs text-muted-foreground">Active</p>
                                </div>
                                <Switch checked={true} disabled />
                            </div>
                        </div>
                    </div>

                </div>
            </ScrollArea>
        </motion.div>
    )
}
