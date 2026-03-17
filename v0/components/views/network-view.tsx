"use client"

import { useEffect, useState, useCallback, useRef } from "react"
import { motion } from "framer-motion"
import { Button } from "@/components/ui/button"
import {
    Select,
    SelectContent,
    SelectItem,
    SelectTrigger,
    SelectValue,
} from "@/components/ui/select"
import { Share2, Hammer, RefreshCw, Loader2, Users, Link } from "lucide-react"
import {
    fetchGraphData,
    buildGraph,
    type GraphData,
    type GraphNode,
    type GraphEdge,
} from "@/lib/api"

// Cluster palette
const CLUSTER_COLOURS = [
    "#6366f1", // indigo
    "#f43f5e", // rose
    "#10b981", // emerald
    "#f59e0b", // amber
    "#3b82f6", // blue
    "#8b5cf6", // violet
    "#ec4899", // pink
    "#14b8a6", // teal
    "#ef4444", // red
    "#22d3ee", // cyan
]

const EDGE_COLOURS: Record<string, string> = {
    similarity: "#94a3b8",
    interaction: "#facc15",
    both: "#67e8f9",
}

// Dynamic import for react-force-graph-2d (no SSR)
import dynamic from "next/dynamic"
const ForceGraph2D = dynamic(() => import("react-force-graph-2d"), {
    ssr: false,
    loading: () => (
        <div className="flex h-[600px] items-center justify-center text-muted-foreground">
            Loading graph renderer…
        </div>
    ),
})

interface InternalNode {
    id: number
    label: string
    cluster: number
    message_count: number
    color: string
    val: number
}

interface InternalLink {
    source: number
    target: number
    weight: number
    edge_type: string
    interaction_count: number
    color: string
}

function toForceGraphData(
    data: GraphData,
    selectedCluster: number | null
) {
    const visibleIds = new Set<number>()
    for (const n of data.nodes) {
        if (selectedCluster !== null && n.cluster !== selectedCluster) continue
        visibleIds.add(n.id)
    }

    const nodes: InternalNode[] = data.nodes
        .filter((n) => visibleIds.has(n.id))
        .map((n) => ({
            id: n.id,
            label: n.label,
            cluster: n.cluster,
            message_count: n.message_count,
            color: CLUSTER_COLOURS[n.cluster % CLUSTER_COLOURS.length],
            val: 4 + Math.min(n.message_count / 5, 30),
        }))

    const links: InternalLink[] = data.edges
        .filter((e) => visibleIds.has(e.source) && visibleIds.has(e.target))
        .map((e) => ({
            source: e.source,
            target: e.target,
            weight: e.weight,
            edge_type: e.edge_type,
            interaction_count: e.interaction_count,
            color: EDGE_COLOURS[e.edge_type] || "#67e8f9",
        }))

    return { nodes, links }
}

export function NetworkView() {
    const [data, setData] = useState<GraphData | null>(null)
    const [loading, setLoading] = useState(true)
    const [building, setBuilding] = useState(false)
    const [selectedCluster, setSelectedCluster] = useState<number | null>(null)
    const [hoveredNode, setHoveredNode] = useState<InternalNode | null>(null)
    const containerRef = useRef<HTMLDivElement>(null)
    const [dims, setDims] = useState({ width: 800, height: 600 })

    // Measure container
    useEffect(() => {
        const el = containerRef.current
        if (!el) return
        const obs = new ResizeObserver(([entry]) => {
            setDims({
                width: entry.contentRect.width,
                height: entry.contentRect.height,
            })
        })
        obs.observe(el)
        return () => obs.disconnect()
    }, [])

    // Initial load
    useEffect(() => {
        fetchGraphData()
            .then(setData)
            .catch(console.error)
            .finally(() => setLoading(false))
    }, [])

    const handleBuild = useCallback(
        async (force: boolean) => {
            setBuilding(true)
            try {
                const result = await buildGraph(force)
                setData(result)
                setSelectedCluster(null)
            } catch (e) {
                console.error(e)
            } finally {
                setBuilding(false)
            }
        },
        []
    )

    const graphInput =
        data && data.nodes.length > 0
            ? toForceGraphData(data, selectedCluster)
            : null

    return (
        <motion.div
            initial={{ opacity: 0, y: 12 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -12 }}
            transition={{ duration: 0.25, ease: "easeOut" }}
            className="flex h-full flex-col"
        >
            {/* Header */}
            <div className="flex items-center justify-between border-b border-border px-4 py-3">
                <div>
                    <div className="flex items-center gap-2">
                        <Share2 className="h-5 w-5 text-muted-foreground" />
                        <h2 className="text-lg font-semibold text-foreground">
                            Social Graph
                        </h2>
                    </div>
                    <p className="text-sm text-muted-foreground">
                        User connections based on interaction frequency &amp; semantic
                        similarity
                    </p>
                </div>

                <div className="flex items-center gap-2">
                    {/* Cluster filter */}
                    {data && data.clusters && data.clusters.length > 0 && (
                        <Select
                            value={
                                selectedCluster === null
                                    ? "all"
                                    : String(selectedCluster)
                            }
                            onValueChange={(v) =>
                                setSelectedCluster(v === "all" ? null : Number(v))
                            }
                        >
                            <SelectTrigger className="w-40">
                                <SelectValue placeholder="All clusters" />
                            </SelectTrigger>
                            <SelectContent>
                                <SelectItem value="all">All clusters</SelectItem>
                                {data.clusters.map((c) => (
                                    <SelectItem key={c} value={String(c)}>
                                        <span className="flex items-center gap-2">
                                            <span
                                                className="inline-block h-2.5 w-2.5 rounded-full"
                                                style={{
                                                    backgroundColor:
                                                        CLUSTER_COLOURS[
                                                        c % CLUSTER_COLOURS.length
                                                        ],
                                                }}
                                            />
                                            Cluster {c}
                                        </span>
                                    </SelectItem>
                                ))}
                            </SelectContent>
                        </Select>
                    )}

                    <Button
                        size="sm"
                        onClick={() => handleBuild(false)}
                        disabled={building}
                    >
                        {building ? (
                            <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                        ) : (
                            <Hammer className="mr-2 h-4 w-4" />
                        )}
                        Build
                    </Button>

                    <Button
                        size="sm"
                        variant="outline"
                        onClick={() => handleBuild(true)}
                        disabled={building}
                    >
                        <RefreshCw className="mr-2 h-4 w-4" />
                        Rebuild
                    </Button>
                </div>
            </div>

            {/* Stats bar */}
            {data && (
                <div className="flex items-center gap-4 border-b border-border px-4 py-2 text-xs text-muted-foreground">
                    <span className="flex items-center gap-1">
                        <Users className="h-3.5 w-3.5" />
                        {data.node_count} users
                    </span>
                    <span className="flex items-center gap-1">
                        <Link className="h-3.5 w-3.5" />
                        {data.edge_count} connections
                    </span>
                    <span className="ml-auto flex items-center gap-3">
                        <span className="flex items-center gap-1">
                            <span className="inline-block h-2 w-4 rounded-sm bg-[#94a3b8]" />
                            Similarity
                        </span>
                        <span className="flex items-center gap-1">
                            <span className="inline-block h-2 w-4 rounded-sm bg-[#facc15]" />
                            Interaction
                        </span>
                        <span className="flex items-center gap-1">
                            <span className="inline-block h-2 w-4 rounded-sm bg-[#67e8f9]" />
                            Both
                        </span>
                    </span>
                </div>
            )}

            {/* Graph canvas */}
            <div ref={containerRef} className="relative flex-1 bg-[#0f172a]">
                {loading && (
                    <div className="flex h-full items-center justify-center text-muted-foreground">
                        <Loader2 className="mr-2 h-5 w-5 animate-spin" />
                        Loading graph data…
                    </div>
                )}

                {!loading && !graphInput && (
                    <div className="flex h-full flex-col items-center justify-center gap-3 text-muted-foreground">
                        <Share2 className="h-12 w-12 opacity-30" />
                        <p className="text-sm">
                            No graph data yet. Click{" "}
                            <strong className="text-foreground">Build</strong> to
                            analyse user connections.
                        </p>
                    </div>
                )}

                {graphInput && graphInput.nodes.length > 0 && (
                    <ForceGraph2D
                        width={dims.width}
                        height={dims.height}
                        graphData={graphInput}
                        backgroundColor="#0f172a"
                        nodeLabel={(node: any) =>
                            `${node.label}\nMessages: ${node.message_count}\nCluster: ${node.cluster}`
                        }
                        nodeColor={(node: any) => node.color}
                        nodeVal={(node: any) => node.val}
                        linkColor={(link: any) => link.color}
                        linkWidth={(link: any) => 1 + link.weight * 2}
                        linkDirectionalParticles={2}
                        linkDirectionalParticleWidth={(link: any) =>
                            link.edge_type === "interaction" ? 2 : 0
                        }
                        onNodeHover={(node: any) => setHoveredNode(node || null)}
                        cooldownTicks={100}
                        d3AlphaDecay={0.02}
                        d3VelocityDecay={0.3}
                    />
                )}

                {/* Hover tooltip */}
                {hoveredNode && (
                    <div className="pointer-events-none absolute left-4 top-4 rounded-lg border border-border bg-card/90 px-3 py-2 text-xs shadow-lg backdrop-blur">
                        <p className="font-medium text-foreground">
                            {hoveredNode.label}
                        </p>
                        <p className="text-muted-foreground">
                            ID: {hoveredNode.id} · Messages:{" "}
                            {hoveredNode.message_count} · Cluster:{" "}
                            {hoveredNode.cluster}
                        </p>
                    </div>
                )}
            </div>
        </motion.div>
    )
}
