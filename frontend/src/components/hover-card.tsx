import type { PickingInfo } from "@deck.gl/core"
import type { MapPlace } from "@/hooks/usePlaces"
import type { ScoreMode } from "./map-sidebar"
import { clampText } from "@/lib/hover/text"
import { breakdownToTags, scoreToStatus } from "@/lib/hover/tags"
import { HoverPill } from "@/lib/hover/HoverPill"
import { formatPlaceInsight } from "@/lib/scoringCopy" // keep your copy generator

export function PlaceHoverCard({
  hover,
  mode,
}: {
  hover: PickingInfo<MapPlace>
  mode: ScoreMode
}) {
  const p = hover.object
  if (!p) return null

  // Hard caps (tune these)
  const name = clampText(p.name, 44)
  const addr = clampText(p.address, 54)
  const desc = clampText(p.description, 160)

  // New: user-friendly pills
  const typeVariant = p.type === "event" ? "event" : "place"
  const status = scoreToStatus(p.score)
  const microTags = breakdownToTags(p.breakdown, p.score)

  return (
    <div
      className="absolute z-30 w-[320px] rounded-xl bg-black/70 text-white backdrop-blur-md border border-white/10 shadow-xl"
      style={{ left: hover.x + 12, top: hover.y + 12 }}
    >
      <div className="p-3 space-y-2">
        {/* Header */}
        <div className="flex items-start justify-between gap-2">
          <div className="min-w-0">
            <div className="font-semibold truncate">{name}</div>
            <div className="mt-0.5 text-xs text-white/70">
              {p.type === "event" ? "Event" : "Place"} · {addr}
            </div>
          </div>

          {/* Replace % badge with pills */}
          <div className="shrink-0 flex flex-col items-end gap-1">
            <HoverPill variant={typeVariant}>{p.type === "event" ? "Event" : "Place"}</HoverPill>
            <HoverPill
              variant={
                status.tone === "good"
                  ? "good"
                  : status.tone === "warn"
                    ? "warn"
                    : status.tone === "fun"
                      ? "fun"
                      : "neutral"
              }
            >
              {status.text}
            </HoverPill>
          </div>
        </div>

        {/* Tags derived from breakdown */}
        {microTags.length > 0 && (
          <div className="flex flex-wrap gap-1.5 pt-1">
            {microTags.map((t) => (
              <HoverPill
                key={t.key}
                variant={t.tone === "warn" ? "warn" : t.tone === "good" ? "good" : t.tone === "fun" ? "fun" : "neutral"}
              >
                {t.text}
              </HoverPill>
            ))}
          </div>
        )}

        {/* Description (hard capped + fixed height window) */}
        {desc && (
          <div className="text-xs leading-relaxed text-white/85 max-h-[84px] overflow-hidden">
            {desc}
          </div>
        )}
      </div>
    </div>
  )
}