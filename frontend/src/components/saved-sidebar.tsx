"use client"

import type { ResultRow } from "@/types/result"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { X, Bookmark, ExternalLink, Trash2 } from "lucide-react"
import { HoverPill } from "@/lib/hover/HoverPill"

function buildGoogleMapsUrl(r: ResultRow) {
  const q = encodeURIComponent(`${r.name} ${r.address}`.trim())
  return `https://www.google.com/maps/search/?api=1&query=${q}`
}

function stableKey(r: ResultRow) {
  return `${r.type}:${r.name}:${r.lat}:${r.lon}`
}

function SavedRow({
  row,
  onSelect,
  onRemove,
}: {
  row: ResultRow
  onSelect: () => void
  onRemove?: () => void
}) {
  return (
    <div className="group flex items-center gap-2 rounded-md border bg-muted/10 p-2 hover:bg-muted/20">
      {/* whole left area clickable -> open DetailCard */}
      <button type="button" onClick={onSelect} className="flex-1 min-w-0 text-left cursor-pointer">
        <div className="flex items-center gap-2 min-w-0">
          <HoverPill
            variant={row.type === "event" ? "event" : "place"}
            surface="light"
            className="shrink-0 mt-0.5"
          >
            {row.type.toUpperCase()}
          </HoverPill>
          <div className="truncate font-medium">{row.name}</div>
        </div>
        <div className="truncate text-xs text-muted-foreground">{row.address}</div>
      </button>

      {/* open google maps */}
      <a href={buildGoogleMapsUrl(row)} target="_blank" rel="noreferrer">
        <Button variant="ghost" size="icon" aria-label="Open in Google Maps">
          <ExternalLink className="h-4 w-4 " />
        </Button>
      </a>

      {/* optional remove */}
      {onRemove && (
        <Button
          variant="ghost"
          size="icon"
          onClick={onRemove}
          aria-label="Remove from saved"
          className="opacity-70 hover:opacity-100 cursor-pointer"
        >
          <Trash2 className="h-4 w-4" />
        </Button>
      )}
    </div>
  )
}

export function SavedPanel({
  saved,
  onClose,
  onSelect,
  onRemove,
}: {
  saved: ResultRow[]
  onClose: () => void
  onSelect: (row: ResultRow) => void
  onRemove?: (row: ResultRow) => void
}) {
  return (
    <div className="absolute z-30 top-0 left-0 h-full w-[380px] max-w-[90vw] p-3">
      <Card className="h-full overflow-hidden">
        <CardHeader className="flex flex-row items-center justify-between space-y-0">
          <div className="flex items-center gap-2">
            <Bookmark className="h-4 w-4" />
            <CardTitle className="text-lg">Saved</CardTitle>
            <span className="ml-1 text-xs text-muted-foreground tabular-nums">({saved.length})</span>
          </div>

          <Button variant="ghost" size="icon" onClick={onClose} aria-label="Close saved panel">
            <X className="h-4 w-4 " />
          </Button>
        </CardHeader>

        <CardContent className="h-[calc(100%-64px)] overflow-auto space-y-2">
          {saved.length === 0 ? (
            <div className="text-sm text-muted-foreground">No saved places/events yet.</div>
          ) : (
            saved.map((row) => (
              <SavedRow
                key={stableKey(row)}
                row={row}
                onSelect={() => onSelect(row)}
                onRemove={onRemove ? () => onRemove(row) : undefined}
              />
            ))
          )}
        </CardContent>
      </Card>
    </div>
  )
}