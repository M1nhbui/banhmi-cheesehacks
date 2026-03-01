import { useMemo, useState } from "react"
import DeckGL from "@deck.gl/react"
import type { PickingInfo } from "@deck.gl/core"
import { ColumnLayer } from "@deck.gl/layers"

import Map from "react-map-gl/mapbox"
import "mapbox-gl/dist/mapbox-gl.css"

import { useSearchResults } from "@/hooks/usePlaces"
import { MapSidebar, type ScoreMode } from "./map-sidebar"
import {PlaceHoverCard} from "./hover-card"

type HoverInfo = PickingInfo<any> | null

const MAP_STYLE = "mapbox://styles/mapbox/dark-v11"

const INITIAL_VIEW = {
  longitude: -89.4012,
  latitude: 43.0731,
  zoom: 13,
  pitch: 45,
  bearing: 0,
}

export default function MapView() {
  const [hover, setHover] = useState<HoverInfo>(null)
  const { places, loading } = useSearchResults(true)

  const [mode, setMode] = useState<ScoreMode>("relevant")

  const [emojis, setEmojis] = useState<string[] | []>([])
  const [query, setQuery] = useState("")

  const toggleEmojis = (key: string) => {
    setEmojis((prev: string[]) => (prev.includes(key) ? prev.filter((k) => k !== key) : [...prev, key]))
  }


  function refresh() {

  }

  const token = import.meta.env.VITE_MAPBOX_TOKEN as string

  const layers = useMemo(() => {
    return [
      new ColumnLayer({
        id: "place-columns",
        data: places,

        pickable: true,
        autoHighlight: true,

        diskResolution: 20,
        radius: 3,
        extruded: true,

        // ✅ easiest knob to make columns shorter:
        elevationScale: 1.5, // try 0.2–0.6

        getPosition: (d: any) => [d.lon ?? d.lng, d.lat],

        // keep this in "meters-ish" then control overall with elevationScale
        getElevation: (d: any) => {
          const s = Math.max(0, Math.min(1, Number(d.score ?? 0)))
          return s * 80
        },

        getFillColor: (d: any) => {
          const t = Math.max(0, Math.min(1, Number(d.score ?? 0)))
          return [255 * t, 120, 255 * (1 - t), 200]
        },

        onHover: info => setHover(info.object ? info : null),
      }),
    ]
  }, [places])

  return (
    <div className="relative h-full w-full">
      <DeckGL initialViewState={INITIAL_VIEW} controller layers={layers}>
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

            // insert under labels
            const layers = map.getStyle().layers
            const labelLayerId = layers?.find(
              (l: any) => l.type === "symbol" && l.layout?.["text-field"]
            )?.id

            map.addLayer(
              {
                id: "3d-buildings",
                source: "composite",
                "source-layer": "building",
                filter: ["==", "extrude", "true"],
                type: "fill-extrusion",
                minzoom: 13, // make buildings show earlier
                paint: {
                  "fill-extrusion-color": "#9aa0a6",
                  // make buildings SMALL/subtle
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
    </div>
  )
}