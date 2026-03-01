// components/MapSidebar.tsx
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { ToggleGroup, ToggleGroupItem } from "@/components/ui/toggle-group"
import { Separator } from "@/components/ui/separator"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"

export type ScoreMode = "relevant" | "hottest" | "chill" | "hidden_gems"

type Props = {
  mode: ScoreMode
  onModeChange: (m: ScoreMode) => void
  onRefresh: () => void | Promise<void>
  loading?: boolean

  // ✅ emojis are multi-select now
  emojiKeys: string[]
  onEmojiToggle: (key: string) => void

  // ✅ text input
  query: string
  onQueryChange: (v: string) => void
}

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
  const EMOJIS = [
    { key: "food", label: "🍜" },
    { key: "coffee", label: "☕️" },
    { key: "music", label: "🎶" },
    { key: "outdoor", label: "🌿" },
    { key: "date", label: "💞" },
  ]

  return (
    <Card className="absolute z-30 top-4 right-4 w-[340px] max-w-[calc(100vw-2rem)] shadow-xl">
      <CardHeader className="space-y-1">
        <div className="flex items-start justify-between gap-3">
          <div>
            <CardTitle className="text-base">Discover</CardTitle>
            <CardDescription className="text-xs">Pick vibes + scoring mode</CardDescription>
          </div>

          <Button
            size="sm"
            variant="secondary"
            className="h-8 px-3"
            onClick={onRefresh}
            disabled={!!loading}
          >
            {loading ? "Refreshing…" : "Refresh ↻"}
          </Button>
        </div>
      </CardHeader>

      <CardContent className="space-y-4">
        {/* ✅ Input field */}
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

        <Separator />

        {/* ✅ Emojis (multi-select) */}
        <div className="space-y-2">
          <div className="text-xs font-medium">Vibes</div>
          <div className="flex gap-2">
            {EMOJIS.map((v) => {
              const active = emojiKeys.includes(v.key)
              return (
                <Button
                  key={v.key}
                  variant={active ? "default" : "secondary"}
                  size="sm"
                  className={["flex-1 transition-all", active && "ring-2 ring-primary"].join(" ")}
                  onClick={() => onEmojiToggle(v.key)}
                >
                  {v.label}
                </Button>
              )
            })}
          </div>

          {emojiKeys.length > 0 && (
            <Button
              type="button"
              variant="ghost"
              size="sm"
              className="h-7 px-2 text-xs"
              onClick={() => {
                // quick clear: caller can implement by setting empty array
                // but we can also just toggle off all by calling onEmojiToggle for each
                // keeping it simple: do nothing here unless you want a clear callback
              }}
              disabled
              title="Optional: add a clear button if you want"
            >
              {/* left disabled intentionally to keep API minimal */}
            </Button>
          )}
        </div>

        <Separator />

        {/* Mode (mutually exclusive) */}
        <div className="space-y-2">
          <div className="text-xs font-medium">Scoring mode</div>

          <ToggleGroup
            type="single"
            value={mode}
            onValueChange={(v) => {
              if (!v) return
              onModeChange(v as ScoreMode)
            }}
            className="grid grid-cols-2 gap-2"
          >
            <ToggleGroupItem value="relevant">🎯 Relevant</ToggleGroupItem>
            <ToggleGroupItem value="hottest">🔥 Hottest</ToggleGroupItem>
            <ToggleGroupItem value="chill">🧊 Chill</ToggleGroupItem>
            <ToggleGroupItem value="hidden_gems">💎 Hidden gems</ToggleGroupItem>
          </ToggleGroup>

          <div className="text-[11px] text-muted-foreground">
            Refresh sends <span className="font-mono">mode={mode}</span> to backend.
          </div>
        </div>
      </CardContent>
    </Card>
  )
}