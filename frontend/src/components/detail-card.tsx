"use client"

import type { ResultRow } from "@/types/result"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Separator } from "@/components/ui/separator"
import { Badge } from "@/components/ui/badge"
import { X, MapPin, ExternalLink, Bookmark } from "lucide-react"

function clamp01(n: number) {
    return Math.max(0, Math.min(1, Number(n ?? 0)))
}

function buildGoogleMapsUrl(r: ResultRow) {
    const q = encodeURIComponent(`${r.name} ${r.address}`.trim())
    return `https://www.google.com/maps/search/?api=1&query=${q}`
}

function buildGoogleSearchUrl(r: ResultRow) {
    const q = encodeURIComponent(`${r.name} ${r.address}`.trim())
    return `https://www.google.com/search?q=${q}`
}

function Metric({
    label,
    value,
}: {
    label: string
    value: number
}) {
    return (
        <div className="flex items-center justify-between rounded-md border bg-muted/30 px-2 py-1 text-sm">
            <span className="text-muted-foreground">{label}</span>
            <span className="font-medium tabular-nums">{clamp01(value).toFixed(2)}</span>
        </div>
    )
}

export function DetailCard({
    row,
    onClose,
    onToggleSaved,
    isSaved,
    onBack
}: {
    row: ResultRow
    onClose: () => void
    onToggleSaved: () => void
    isSaved: boolean
    onBack?: () => void
}) {
    return (
        <div className="absolute z-30 top-0 left-0 h-full w-[380px] max-w-[90vw] p-3 pointer-events-auto">
            <Card className="h-full overflow-hidden">
                <CardHeader className="space-y-2">
                    <div className="flex items-start justify-between gap-3">
                        <div className="min-w-0">
                            <div className="flex items-center gap-2">
                                <Badge variant="secondary" className="shrink-0">
                                    {row.type.toUpperCase()}
                                </Badge>
                                <CardTitle className="truncate text-lg">{row.name}</CardTitle>
                            </div>

                            <div className="mt-2 flex items-start gap-2 text-sm text-muted-foreground">
                                <MapPin className="mt-0.5 h-4 w-4 shrink-0" />
                                <span className="line-clamp-2">{row.address}</span>
                            </div>
                        </div>

                        {onBack && (
                            <Button variant="ghost" size="sm" onClick={onBack} className="gap-2">
                                ← Back
                            </Button>
                        )}
                        <Button variant="ghost" size="icon" onClick={onClose} aria-label="Close details">
                            <X className="h-4 w-4" />
                        </Button>
                    </div>

                    <Separator />
                </CardHeader>

                <CardContent className="h-[calc(100%-96px)] overflow-auto space-y-4 pb-6">
                    {/* score + breakdown */}
                    <div className="rounded-lg border bg-muted/20 p-3">
                        <div className="flex items-center justify-between">
                            <div className="text-sm text-muted-foreground">Score</div>
                            <div className="font-semibold tabular-nums">{clamp01(row.score).toFixed(2)}</div>
                        </div>

                        <div className="mt-3 grid grid-cols-2 gap-2">
                            <Metric label="Similarity" value={row.breakdown?.similarity ?? 0} />
                            <Metric label="Popularity" value={row.breakdown?.popularity ?? 0} />
                            <Metric label="Weather" value={row.breakdown?.weather ?? 0} />
                            <Metric label="Urgency" value={row.breakdown?.urgency ?? 0} />
                        </div>
                    </div>

                    {/* description */}
                    <div className="rounded-lg border bg-muted/10 p-3">
                        <div className="text-sm font-medium">Description</div>
                        <div className="mt-2 text-sm text-muted-foreground whitespace-pre-wrap">
                            {row.description || "—"}
                        </div>
                    </div>

                    {/* lat/lon */}
                    <div className="rounded-lg border bg-muted/10 p-3">
                        <div className="text-sm font-medium">Location</div>
                        <div className="mt-2 grid grid-cols-2 gap-2 text-sm">
                            <div className="rounded-md border bg-background/40 px-2 py-1">
                                <div className="text-xs text-muted-foreground">Lat</div>
                                <div className="font-medium tabular-nums">{row.lat}</div>
                            </div>
                            <div className="rounded-md border bg-background/40 px-2 py-1">
                                <div className="text-xs text-muted-foreground">Lon</div>
                                <div className="font-medium tabular-nums">{row.lon}</div>
                            </div>
                        </div>
                    </div>

                    {/* actions */}
                    <div className="space-y-2">
                        <a href={buildGoogleMapsUrl(row)} target="_blank" rel="noreferrer">
                            <Button variant="secondary" className="w-full justify-between">
                                Open in Google Maps
                                <ExternalLink className="h-4 w-4" />
                            </Button>
                        </a>

                        <a href={buildGoogleSearchUrl(row)} target="_blank" rel="noreferrer">
                            <Button variant="secondary" className="w-full justify-between">
                                Google it
                                <ExternalLink className="h-4 w-4" />
                            </Button>
                        </a>

                        <Button
                            onClick={onToggleSaved}
                            variant={isSaved ? "default" : "outline"}
                            className="w-full justify-between"
                        >
                            <span className="flex items-center gap-2">
                                <Bookmark className="h-4 w-4" />
                                {isSaved ? "Saved (click to remove)" : "Save to my collection"}
                            </span>
                            {isSaved ? "✓" : "+"}
                        </Button>
                    </div>
                </CardContent>
            </Card>
        </div>
    )
}