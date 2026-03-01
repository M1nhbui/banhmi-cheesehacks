import type { PickingInfo } from "@deck.gl/core"
import type { MapPlace } from "@/hooks/usePlaces"
import { formatPlaceInsight } from "@/lib/scoringCopy" // wherever you put it
import type { ScoreMode } from "./map-sidebar";

function BreakdownRow({ label, v }: { label: string; v: number }) {
  const pct = Math.round(Math.max(0, Math.min(1, v)) * 100)
  return (
    <div className="flex items-center justify-between gap-2 text-xs text-white/75">
      <span>{label}</span>
      <span className="font-mono">{pct}%</span>
    </div>
  )
}

export function PlaceHoverCard({
  hover,
  mode,
}: {
  hover: PickingInfo<MapPlace>
  mode: ScoreMode
}) {
  const p = hover.object
  if (!p) return null

  const { headline, driverLine, pct } = formatPlaceInsight({
    mode: mode as any, // remove if your ScoreMode matches the union
    type: p.type,
    score: p.score,
    breakdown: p.breakdown,
  })

  return (
    <div
      className="absolute z-30 w-[300px] rounded-xl bg-black/70 text-white backdrop-blur-md border border-white/10 shadow-xl"
      style={{ left: hover.x + 12, top: hover.y + 12 }}
    >
      <div className="p-3 space-y-2">
        <div className="flex items-start justify-between gap-2">
          <div className="min-w-0">
            <div className="font-semibold truncate">{p.name}</div>
            <div className="mt-0.5 text-xs text-white/70">
              {p.type === "event" ? "Event" : "Place"} · {p.address}
            </div>
          </div>

          <span className="shrink-0 rounded-full px-2 py-1 text-xs border border-white/15 bg-white/5">
            {pct}%
          </span>
        </div>

        <div className="text-sm">
          <div className="font-medium">{headline}</div>
          <div className="text-xs text-white/70">{driverLine}</div>
        </div>

        {p.description && (
          <div className="text-xs leading-relaxed text-white/85 max-h-[72px] overflow-hidden">
            {p.description}
          </div>
        )}

        <div className="pt-2 border-t border-white/10 space-y-1">
          <BreakdownRow label="Similarity" v={p.breakdown.similarity} />
          <BreakdownRow label="Hotness" v={p.breakdown.hotness} />
          <BreakdownRow label="Crowd" v={p.breakdown.crowd} />
          <BreakdownRow label="Urgency" v={p.breakdown.urgency} />
        </div>
      </div>
    </div>
  )
}