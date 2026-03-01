// components/detail/ScoreSummary.tsx
"use client"

import { useMemo } from "react"
import type { ResultRow } from "@/types/result"
import { HoverPill } from "@/lib/hover/HoverPill"
import { scoreToStatus, breakdownToTags } from "@/lib/hover/tags"
import { aestheticScore, displaySimilarity } from "@/lib/hover/aestheticScore"
import { clamp01 } from "@/lib/hover/text"

function TinyBar({ v }: { v: number }) {
    const pct = Math.round(clamp01(v) * 100)
    return (
        <div className="w-full h-1.5 rounded-full bg-muted overflow-hidden">
            <div className="h-full bg-primary/70" style={{ width: `${pct}%` }} />
        </div>
    )
}

export function ScoreSummary({ row }: { row: ResultRow }) {
    const seed = `${row.type}:${row.name}:${row.address}`

    const sPretty = useMemo(() => aestheticScore(row.score ?? 0, seed), [row.score, seed])
    const status = useMemo(() => scoreToStatus(row.score ?? 0), [row.score])
    const tags = useMemo(
        () => breakdownToTags(row.breakdown ?? { similarity: 0, popularity: 0, weather: 0, urgency: 0 }, row.score ?? 0),
        [row.breakdown, row.score]
    )

    return (
        <div className="rounded-lg border bg-muted/20 p-3 space-y-3">
            {/* Top line: score + status */}
            <div className="flex items-start justify-between gap-3">
                <div className="space-y-1 min-w-0">
                    <div className="text-sm text-muted-foreground">Score</div>
                    <div className="flex items-center gap-2 flex-wrap">
                        <HoverPill
                            variant={
                                row.type === "event" ? "event" : "place"
                            }
                            surface="light"
                        >
                            {row.type === "event" ? "Event" : "Place"}
                        </HoverPill>

                        <HoverPill
                            variant={
                                status.tone === "good" ? "good" : status.tone === "warn" ? "warn" : status.tone === "fun" ? "fun" : "neutral"
                            }
                            surface="light"
                        >
                            {status.text}
                        </HoverPill>
                    </div>
                </div>

                {/* Aesthetic score number (stable jitter) */}
                <div className="text-right">
                    <div className="text-xs text-muted-foreground">signal</div>
                    <div className="font-semibold tabular-nums">{clamp01(sPretty).toFixed(2)}</div>
                </div>
            </div>

            {/* Quick breakdown: tiny bars + labels (no raw decimals) */}
            <div className="grid grid-cols-2 gap-2 text-xs">
                <div className="space-y-1">
                    <div className="text-muted-foreground">Hotness</div>
                    <TinyBar v={row.breakdown?.hotness ?? 0} />
                </div>
                <div className="space-y-1">
                    <div className="text-muted-foreground">Urgency</div>
                    <TinyBar v={row.breakdown?.urgency ?? 0} />
                </div>
                <div className="space-y-1">
                    <div className="text-muted-foreground">Crowd</div>
                    <TinyBar v={row.breakdown?.crowd ?? 0} />
                </div>
                <div className="space-y-1">
                    <div className="text-muted-foreground">Similarity</div>

                    <TinyBar v={displaySimilarity(row.score ?? 0, seed)} />
                </div>
            </div>

            {/* Tags (same vibe tags as hover card) */}
            {tags.length > 0 && (
                <div className="flex flex-wrap gap-1.5">
                    {tags.map((t) => (
                        <HoverPill
                            key={t.key}
                            variant={t.tone === "warn" ? "warn" : t.tone === "good" ? "good" : t.tone === "fun" ? "fun" : "neutral"}
                            surface="light"
                        >
                            {t.text}
                        </HoverPill>
                    ))}
                </div>
            )}
        </div>
    )
}