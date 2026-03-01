// components/MapSidebar.tsx
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Separator } from "@/components/ui/separator"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"

export type ScoreMode = "relevant" | "hottest" | "chill" | "hidden_gems"

type Props = {
  mode: ScoreMode
  onModeChange: (m: ScoreMode) => void
  onRefresh: () => void | Promise<void>
  loading?: boolean

  /**
   * Multi-select values for vibe filters.
   * NOTE: After this refactor, these are *descriptive statements* (not short keys),
   * so you can send them to the backend for vectorization.
   */
  emojiKeys: string[]
  onEmojiToggle: (value: string) => void

  query: string
  onQueryChange: (v: string) => void
}

/**
 * Central config: one place to edit what the UI supports.
 * - `value` is what you store/send to backend (vector-friendly statement).
 * - Keep these consistent in tone/format so embeddings work better.
 */
type VibeOption = {
  id: "food" | "coffee" | "music" | "outdoor" | "date"
  emoji: string
  label: string
  value: string
}

const VIBE_OPTIONS: VibeOption[] = [
  {
    id: "food",
    emoji: "🍜",
    label: "Food",
    value:
      "Places focused on food and dining such as restaurants, ramen shops, sushi spots, casual eateries, and places known for good meals and quick bites.",
  },
  {
    id: "coffee",
    emoji: "☕️",
    label: "Coffee",
    value:
      "Coffee-focused places such as cafés, espresso bars, bakeries with coffee, study-friendly coffee shops, and cozy spots for working or reading.",
  },
  {
    id: "music",
    emoji: "🎶",
    label: "Music",
    value:
      "Places centered around music such as live music venues, bars with performances, jazz lounges, DJ sets, open mics, and spaces known for good sound and atmosphere.",
  },
  {
    id: "outdoor",
    emoji: "🌿",
    label: "Outdoor",
    value:
      "Nature-forward places such as parks, lakes, trails, gardens, scenic viewpoints, and outdoor areas that feel green, calm, and refreshing.",
  },
  {
    id: "date",
    emoji: "💞",
    label: "Date",
    value:
      "Romantic or date-friendly places such as intimate restaurants, wine bars, dessert spots, scenic walks, cozy lounges, and places good for conversation and ambiance.",
  },
] as const

type ModeOption = {
  id: ScoreMode
  label: string
  hint?: string
}

const MODE_OPTIONS: ModeOption[] = [
  { id: "relevant", label: "🎯 For you", hint: "Best fit to your query + vibes" },
  { id: "hottest", label: "🔥 Trending", hint: "Prioritize popular spots" },
  { id: "chill", label: "🧊 Chill", hint: "Lower-key, calmer picks" },
  { id: "hidden_gems", label: "💎 Hidden gems", hint: "Underrated finds" },
] as const

export function MapSidebar({
  mode,
  onModeChange,
  onRefresh,
  loading,
  emojiKeys,
  onEmojiToggle,
  query,
  onQueryChange,
}: Props) {
  return (
    <Card className="absolute z-30 top-4 right-4 w-[340px] max-w-[calc(100vw-2rem)] shadow-xl">
      <Header loading={!!loading} onRefresh={onRefresh} />

      <CardContent className="space-y-4">
        <QueryField query={query} onQueryChange={onQueryChange} />

        <Separator />

        <VibesPicker selectedValues={emojiKeys} onToggle={onEmojiToggle} />

        <Separator />

        <ModePicker mode={mode} onModeChange={onModeChange} />

        <div className="text-[11px] text-muted-foreground">
          Refresh sends <span className="font-mono">mode={mode}</span> to backend.
        </div>
      </CardContent>
    </Card>
  )
}

function Header({
  loading,
  onRefresh,
}: {
  loading: boolean
  onRefresh: () => void | Promise<void>
}) {
  return (
    <CardHeader className="space-y-1">
      <div className="flex items-start justify-between gap-3">
        <div>
          <CardTitle className="text-base">Discover</CardTitle>
          <CardDescription className="text-xs">Pick vibes + what matters right now</CardDescription>
        </div>

        <Button
          size="sm"
          variant="secondary"
          className="h-8 px-3 cursor-pointer disabled:cursor-not-allowed"
          onClick={onRefresh}
          disabled={loading}
        >
          {loading ? "Refreshing…" : "Refresh ↻"}
        </Button>
      </div>
    </CardHeader>
  )
}

function QueryField({
  query,
  onQueryChange,
}: {
  query: string
  onQueryChange: (v: string) => void
}) {
  return (
    <div className="space-y-2">
      <Label htmlFor="place-query" className="text-xs font-medium">
        Places you want to go
      </Label>
      <Input
        id="place-query"
        value={query}
        onChange={(e) => onQueryChange(e.target.value)}
        placeholder='e.g. "coffee shop", "sushi", "bookstore"'
      />
    </div>
  )
}

function VibesPicker({
  selectedValues,
  onToggle,
}: {
  selectedValues: string[]
  onToggle: (value: string) => void
}) {
  return (
    <div className="space-y-2">
      <div className="text-xs font-medium">Vibes</div>

      <div className="flex gap-2">
        {VIBE_OPTIONS.map((opt) => {
          // Selection is based on the statement value (vector-friendly payload).
          const active = selectedValues.includes(opt.value)

          return (
            <Button
              key={opt.id}
              variant={active ? "default" : "secondary"}
              size="sm"
              className={["flex-1 transition-all cursor-pointer disabled:cursor-not-allowed", active && "ring-2 ring-primary"].join(" ")}
              onClick={() => onToggle(opt.value)}
              title={opt.label}
            >
              {opt.emoji}
            </Button>
          )
        })}
      </div>

      {selectedValues.length > 0 && (
        <div className="text-[11px] text-muted-foreground">
          Sending {selectedValues.length} vibe statement{selectedValues.length === 1 ? "" : "s"}.
        </div>
      )}
    </div>
  )
}

/**
 * 4 independent buttons in a 2x2 grid:
 * - fixes the "broken pill" look when ToggleGroup wraps
 * - matches your emoji buttons: selected = primary (purple)
 */
function ModePicker({
  mode,
  onModeChange,
}: {
  mode: ScoreMode
  onModeChange: (m: ScoreMode) => void
}) {
  return (
    <div className="space-y-2">
      <div className="text-xs font-medium">What feels right</div>

      <div className="grid grid-cols-2 gap-2">
        {MODE_OPTIONS.map((opt) => {
          const active = mode === opt.id

          return (
            <Button
              key={opt.id}
              type="button"
              variant={active ? "default" : "secondary"}
              className={[
                "h-10 justify-start px-3 transition-all cursor-pointer disabled:cursor-not-allowed",
                active && "ring-2 ring-primary",
              ].join(" ")}
              onClick={() => onModeChange(opt.id)}
              title={opt.hint}
            >
              {opt.label}
            </Button>
          )
        })}
      </div>

      <div className="text-[11px] text-muted-foreground">
        Pick what you care about most right now.
      </div>
    </div>
  )
}