import { useMemo, useState } from "react"
import DeckGL from "@deck.gl/react"
import type { PickingInfo } from "@deck.gl/core"
import { ColumnLayer, ScatterplotLayer } from "@deck.gl/layers"

import Map from "react-map-gl/mapbox"
import "mapbox-gl/dist/mapbox-gl.css"

import { useSearchResults } from "@/hooks/usePlaces"
import { MapSidebar, type ScoreMode } from "./map-sidebar"
import { PlaceHoverCard } from "./hover-card"
import { DetailCard } from "./detail-card"

import { SavedToggleButton } from "./saved-toggle-button"
import { SavedPanel } from "./saved-sidebar"

import { LoadingPill } from "./loading-pill"
import { add3dBuildingsLayer } from "./mapbox-3d-buildings"

import type { ResultRow } from "@/types/result"
import { useSavedResults, stableId } from "@/hooks/useSavedResults"
import { useDetailStack } from "@/hooks/useDetailStack"
import { placeFillColor } from "@/lib/viz/color"

import { eventCoreColor, eventCoreRadiusMeters, eventHaloColor, eventHaloRadiusMeters } from "@/lib/viz/event-style"

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

export default function MapView() {

  const [hover, setHover] = useState<HoverInfo>(null)
  const [mode, setMode] = useState<ScoreMode>("relevant")
  const [emojis, setEmojis] = useState<string[]>([])
  const [query, setQuery] = useState("")

  const { places, loading, refresh: refreshScores } = useSearchResults({
    initialMode: mode,           // or "relevant" fixed
    initialKeywords: emojis,      // likely []
    initialQuery: query,          // likely ""
    mock: true
  })


  const token = import.meta.env.VITE_MAPBOX_TOKEN as string

  // saved state + persistence
  const { savedRows, savedCount, toggleSaved, removeSaved, isSaved } = useSavedResults()

  // panel stack + back behavior
  const {
    selected,
    savedOpen,
    detailFromSaved,
    closeDetail,
    openDetailFromMap,
    toggleSavedPanel,
    selectFromSavedList,
    backToSavedList,
    setSelected,
  } = useDetailStack()

  const toggleEmojis = (key: string) => {
    setEmojis((prev) => (prev.includes(key) ? prev.filter((k) => k !== key) : [...prev, key]))
  }

  async function refresh() {
    // keywords should be the emoji values (your “statements”)
    // If you want query to influence matching too, include it:
    // const keywords = query.trim() ? [query.trim(), ...emojis] : emojis

    await refreshScores({
      mode,
      keywords: emojis,
      query
    })
  }

  const layers = useMemo(() => {
    const placeData = (places ?? []).filter((p: any) => p.type === "place")
    const eventData = (places ?? []).filter((p: any) => p.type === "event")

    return [
      new ColumnLayer({
        id: "place-columns",
        data: placeData,
        pickable: true,
        autoHighlight: true,

        diskResolution: 5,
        radius: 5,
        extruded: true,
        elevationScale: 4,

        getPosition: (d: any) => [d.lon ?? d.lng, d.lat],
        getElevation: (d: any) => clamp01(d.score) * 80,
        getFillColor: (d: any) => placeFillColor(d.score),

        onHover: (info: any) => setHover(info.object ? info : null),
        onClick: (info: PickingInfo<any>) => {
          openDetailFromMap(info)
          setHover(null)
        },
      }),

      // EVENTS: halo (behind)
      new ScatterplotLayer({
        id: "event-halo",
        data: eventData,

        // important: don't steal clicks/hover
        pickable: false,
        autoHighlight: false,

        radiusUnits: "meters",
        getRadius: (d: any) => eventHaloRadiusMeters(d.score),
        getPosition: (d: any) => [d.lon ?? d.lng, d.lat],
        getFillColor: (d: any) => eventHaloColor(d.score),

        // depth test off helps halo show over columns
        parameters: { depthTest: false },
      }),

      // EVENTS: core (clickable beacon)
      new ScatterplotLayer({
        id: "event-core",
        data: eventData,

        pickable: true,
        autoHighlight: true,

        radiusUnits: "meters",
        getRadius: (d: any) => eventCoreRadiusMeters(d.score),
        getPosition: (d: any) => [d.lon ?? d.lng, d.lat],
        getFillColor: (d: any) => eventCoreColor(d.score),

        // makes them win visually against tall columns
        parameters: { depthTest: false },

        onHover: (info: any) => setHover(info.object ? info : null),
        onClick: (info: PickingInfo<any>) => {
          openDetailFromMap(info)
          setHover(null)
        },
      }),
    ]
  }, [places, openDetailFromMap])

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
        <LoadingPill show={!!loading} />

        <Map
          mapboxAccessToken={token}
          mapStyle={MAP_STYLE}
          onLoad={(e) => add3dBuildingsLayer(e.target)}
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
          row={selected as ResultRow}
          onClose={closeDetail}
          onToggleSaved={() => toggleSaved(selected as ResultRow)}
          isSaved={isSaved(selected as ResultRow)}
          onBack={detailFromSaved ? backToSavedList : undefined}
        />
      )}

      <SavedToggleButton count={savedCount} open={savedOpen} onToggle={toggleSavedPanel} />

      {savedOpen && (
        <SavedPanel
          saved={savedRows}
          onClose={toggleSavedPanel}
          onSelect={selectFromSavedList}
          onRemove={removeSaved}
        />
      )}
    </div>
  )
}