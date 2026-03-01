import { useCallback, useEffect, useMemo, useState } from "react"
import DeckGL from "@deck.gl/react"
import type { PickingInfo } from "@deck.gl/core"
import { ColumnLayer, ScatterplotLayer } from "@deck.gl/layers"

import Map from "react-map-gl/mapbox"
import "mapbox-gl/dist/mapbox-gl.css"

import { useSearchResults } from "@/hooks/usePlaces"
import { MapSidebar, type ScoreMode } from "./map-sidebar"
import { PlaceHoverCard } from "./hover-card"
import { DetailCard } from "./detail-card"
import type { ResultRow } from "@/types/result"

import { SavedToggleButton } from "./saved-toggle-button"
import { SavedPanel } from "./saved-sidebar"

type HoverInfo = PickingInfo<any> | null

const MAP_STYLE = "mapbox://styles/mapbox/dark-v11"

const INITIAL_VIEW = {
  longitude: -89.4012,
  latitude: 43.0731,
  zoom: 13,
  pitch: 45,
  bearing: 0,
}

function clamp01(n: number) {
  return Math.max(0, Math.min(1, Number(n ?? 0)))
}

const SAVED_KEY = "saved-results-v1"

function getSaved(): ResultRow[] {
  try {
    const raw = localStorage.getItem(SAVED_KEY)
    if (!raw) return []
    const parsed = JSON.parse(raw)
    return Array.isArray(parsed) ? (parsed as ResultRow[]) : []
  } catch {
    return []
  }
}

function setSaved(rows: ResultRow[]) {
  localStorage.setItem(SAVED_KEY, JSON.stringify(rows))
}

function stableId(r: ResultRow) {
  return `${r.type}:${r.name}:${r.lat.toFixed(6)}:${r.lon.toFixed(6)}`
}

export default function MapView() {
  const [hover, setHover] = useState<HoverInfo>(null)
  const { places, loading } = useSearchResults(true)

  const [mode, setMode] = useState<ScoreMode>("relevant")
  const [emojis, setEmojis] = useState<string[] | []>([])
  const [query, setQuery] = useState("")

  // panels
  const [selected, setSelected] = useState<ResultRow | null>(null)
  const [savedOpen, setSavedOpen] = useState(false)

  // saved state (ids + full rows for panel)
  const [savedRows, setSavedRows] = useState<ResultRow[]>([])
  const [savedIds, setSavedIds] = useState<Set<string>>(new Set())

  const toggleEmojis = (key: string) => {
    setEmojis((prev: string[]) => (prev.includes(key) ? prev.filter((k) => k !== key) : [...prev, key]))
  }

  // TODO: implement refresh on usePlaces
  function refresh() { }

  const token = import.meta.env.VITE_MAPBOX_TOKEN as string

  const [detailFromSaved, setDetailFromSaved] = useState(false)

  useEffect(() => {
    const saved = getSaved()
    setSavedRows(saved)
    setSavedIds(new Set(saved.map(stableId)))
  }, [])

  const toggleSaved = useCallback((row: ResultRow) => {
    const id = stableId(row)
    const existing = getSaved()
    const exists = existing.some((r) => stableId(r) === id)

    const next = exists ? existing.filter((r) => stableId(r) !== id) : [row, ...existing]
    setSaved(next)
    setSavedRows(next)
    setSavedIds(new Set(next.map(stableId)))
  }, [])

  const handlePick = useCallback(
    (info: PickingInfo<any>) => {
      if (info?.object) {
        setSelected(info.object as ResultRow)
        setHover(null)
        setSavedOpen(false) // detail wins
        setDetailFromSaved(false) // ✅
      }
    },
    [setSelected]
  )

  const savedCount = savedIds.size

  const layers = useMemo(() => {
    const placeData = (places ?? []).filter((p: any) => p.type === "place")
    const eventData = (places ?? []).filter((p: any) => p.type === "event")

    return [
      new ColumnLayer({
        id: "place-columns",
        data: placeData,
        pickable: true,
        autoHighlight: true,

        diskResolution: 20,
        radius: 3,
        extruded: true,
        elevationScale: 1.5,

        getPosition: (d: any) => [d.lon ?? d.lng, d.lat],
        getElevation: (d: any) => clamp01(d.score) * 80,
        getFillColor: (d: any) => {
          const t = clamp01(d.score)
          return [255 * t, 120, 255 * (1 - t), 190]
        },

        onHover: (info: any) => setHover(info.object ? info : null),
        onClick: handlePick,
      }),

      new ScatterplotLayer({
        id: "event-dots",
        data: eventData,
        pickable: true,
        autoHighlight: true,

        radiusUnits: "meters",
        getRadius: 25,
        getPosition: (d: any) => [d.lon ?? d.lng, d.lat],
        getFillColor: () => [255, 0, 0, 220],

        onHover: (info: any) => setHover(info.object ? info : null),
        onClick: handlePick,
      }),
    ]
  }, [places, handlePick]) // mode not used inside; remove to avoid extra rebuilds

  return (
    <div className="relative h-full w-full">
      <DeckGL
        initialViewState={INITIAL_VIEW}
        controller
        layers={layers}
        onClick={(info) => {
          if (!info?.object) setSelected(null)
        }}
      >
        {loading && (
          <div className="absolute z-20 top-4 left-4 bg-black/60 text-white px-3 py-1 rounded-md text-sm">
            Loading places...
          </div>
        )}

        <Map
          mapboxAccessToken={token}
          mapStyle={MAP_STYLE}
          onLoad={(e) => {
            const map = e.target
            if (map.getLayer("3d-buildings")) return

            const styleLayers = map.getStyle().layers
            const labelLayerId = styleLayers?.find((l: any) => l.type === "symbol" && l.layout?.["text-field"])?.id

            map.addLayer(
              {
                id: "3d-buildings",
                source: "composite",
                "source-layer": "building",
                filter: ["==", "extrude", "true"],
                type: "fill-extrusion",
                minzoom: 13,
                paint: {
                  "fill-extrusion-color": "#9aa0a6",
                  "fill-extrusion-height": ["*", ["coalesce", ["get", "height"], 6], 0.22],
                  "fill-extrusion-base": ["*", ["coalesce", ["get", "min_height"], 0], 0.22],
                  "fill-extrusion-opacity": 0.5,
                },
              },
              labelLayerId
            )
          }}
        />
      </DeckGL>

      <MapSidebar
        mode={mode}
        onModeChange={setMode}
        onRefresh={refresh}
        loading={loading}
        emojiKeys={emojis}
        onEmojiToggle={toggleEmojis}
        query={query}
        onQueryChange={setQuery}
      />

      {hover?.object && <PlaceHoverCard hover={hover} mode={mode} />}

      {selected && (
        <DetailCard
          row={selected}
          onClose={() => setSelected(null)}
          onToggleSaved={() => toggleSaved(selected)}
          isSaved={savedIds.has(stableId(selected))}
          onBack={
            detailFromSaved
              ? () => {
                setSelected(null)
                setSavedOpen(true)
                setDetailFromSaved(false)
              }
              : undefined
          }
        />
      )}

      <SavedToggleButton
        count={savedCount}
        open={savedOpen}
        onToggle={() => {
          setSavedOpen((v) => {
            const next = !v
            if (next) setSelected(null) // saved panel wins, kick detail
            return next
          })
        }}
      />

      {savedOpen && (
        <SavedPanel
          saved={savedRows}
          onClose={() => setSavedOpen(false)}
          onSelect={(row) => {
            setSelected(row)
            setSavedOpen(false)
            setDetailFromSaved(true) // ✅
          }}
          onRemove={(row) => toggleSaved(row)}
        />
      )}
    </div>
  )
}