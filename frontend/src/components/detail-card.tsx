"use client"

import type { ResultRow } from "@/types/result"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Separator } from "@/components/ui/separator"
import { HoverPill } from "@/lib/hover/HoverPill"
import { X, MapPin, ExternalLink, Bookmark } from "lucide-react"

import { ScoreSummary } from "@/components/ScoreSummary"

function buildGoogleMapsUrl(r: ResultRow) {
    const q = encodeURIComponent(`${r.name} ${r.address}`.trim())
    return `https://www.google.com/maps/search/?api=1&query=${q}`
}

function buildGoogleSearchUrl(r: ResultRow) {
    const q = encodeURIComponent(`${r.name} ${r.address}`.trim())
    return `https://www.google.com/search?q=${q}`
}

export function DetailCard({
    row,
    onClose,
    onToggleSaved,
    isSaved,
    onBack,
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
                {/* Header */}
                <CardHeader className="space-y-3">
                    {/* Top row: badge + title (wrap) + actions pinned */}
                    <div className="flex items-start justify-between gap-3">
                        {/* Left: badge + title */}
                        <div className="min-w-0 flex-1">
                            <div className="flex items-start gap-2">
                                <HoverPill
                                    variant={row.type === "event" ? "event" : "place"}
                                    surface="light"
                                    className="shrink-0 mt-0.5"
                                >
                                    {row.type.toUpperCase()}
                                </HoverPill>

                                {/* Title: wrap instead of truncate; allow long words to break */}
                                <CardTitle className="text-lg leading-snug whitespace-normal break-words">
                                    {row.name}
                                </CardTitle>
                            </div>

                            {/* Address: allow true wrapping / new lines */}
                            <div className="mt-2 flex items-start gap-2 text-sm text-muted-foreground">
                                <MapPin className="mt-0.5 h-4 w-4 shrink-0" />
                                <span className="whitespace-normal break-words">{row.address}</span>
                            </div>
                        </div>

                        {/* Right: buttons NEVER get pushed off */}
                        <div className="shrink-0 flex items-center gap-1">
                            {onBack && (
                                <Button
                                    variant="ghost"
                                    size="sm"
                                    onClick={onBack}
                                    className="h-9 px-2 gap-1"
                                >
                                    ← <span className="hidden sm:inline">Back</span>
                                </Button>
                            )}

                            <Button
                                variant="ghost"
                                size="icon"
                                onClick={onClose}
                                aria-label="Close details"
                                className="h-9 w-9"
                            >
                                <X className="h-4 w-4" />
                            </Button>
                        </div>
                    </div>

                    <Separator />
                </CardHeader>

                {/* Body */}
                <CardContent className="h-[calc(100%-120px)] overflow-auto space-y-4 pb-8">
                    {/* score + breakdown (keep your aesthetic score behavior inside ScoreSummary) */}
                    <ScoreSummary row={row} />

                    {/* description */}
                    <div className="rounded-lg border bg-muted/10 p-3">
                        <div className="text-sm font-medium">Description</div>
                        <div className="mt-2 text-sm text-muted-foreground whitespace-pre-wrap break-words">
                            {row.description || "—"}
                        </div>
                    </div>

                    {/* actions (bigger + spaced) */}
                    <div className="space-y-3 pt-2">
                        <a href={buildGoogleMapsUrl(row)} target="_blank" rel="noreferrer" className="block">
                            <Button
                                variant="secondary"
                                className="w-full h-11 px-4 justify-between"
                            >
                                Open in Google Maps
                                <ExternalLink className="h-4 w-4" />
                            </Button>
                        </a>

                        <a href={buildGoogleSearchUrl(row)} target="_blank" rel="noreferrer" className="block">
                            <Button
                                variant="secondary"
                                className="w-full h-11 px-4 justify-between"
                            >
                                Google it
                                <ExternalLink className="h-4 w-4" />
                            </Button>
                        </a>

                        <Button
                            onClick={onToggleSaved}
                            variant={isSaved ? "default" : "outline"}
                            className="w-full h-11 px-4 justify-between"
                        >
                            <span className="flex items-center gap-2">
                                <Bookmark className="h-4 w-4" />
                                {isSaved ? "Saved (click to remove)" : "Save to my collection"}
                            </span>
                            <span className="text-base">{isSaved ? "✓" : "+"}</span>
                        </Button>
                    </div>
                </CardContent>
            </Card>
        </div>
    )
}