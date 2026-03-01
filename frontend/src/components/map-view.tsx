import { useMemo, useState } from "react"
import DeckGL from "@deck.gl/react"
import type { PickingInfo } from "@deck.gl/core"
import { ColumnLayer } from "@deck.gl/layers"

import Map from "react-map-gl/mapbox"
import "mapbox-gl/dist/mapbox-gl.css"

import { useSearchResults } from "@/hooks/usePlaces"

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


  console.log("places length:", places?.length)
  console.log("first place:", places?.[0])

  const token = import.meta.env.VITE_MAPBOX_TOKEN as string

  const layers = useMemo(() => {
    return [
      new ColumnLayer({
        id: "place-columns",
        data: places,

        pickable: true,
        autoHighlight: true,

        // shape
        diskResolution: 16,
        radius: 18, // meters (world units)
        extruded: true,

        // position + height
        getPosition: (d: any) => [d.lon ?? d.lng, d.lat],
        getElevation: (d: any) => {
          const s = Math.max(0, Math.min(1, Number(d.score ?? 0)))
          return 50 + s * 800 // meters
        },

        // color
        getFillColor: (d: any) => {
          const t = Math.max(0, Math.min(1, Number(d.score ?? 0)))
          return [255 * t, 120, 255 * (1 - t), 200]
        },

        // hover
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

        <Map mapboxAccessToken={token} mapStyle={MAP_STYLE} />
      </DeckGL>

      {hover && (
        <div
          className="absolute z-10 rounded-xl px-3 py-2 text-sm bg-black/60 text-white backdrop-blur-md border border-white/10 shadow-xl"
          style={{ left: hover.x + 12, top: hover.y + 12 }}
        >
          <div className="font-semibold">{hover.object?.name ?? "Place"}</div>
          <div className="opacity-80 text-xs">
            Score {Number(hover.object?.score ?? 0).toFixed(2)}
          </div>
        </div>
      )}
    </div>
  )
}