import { useEffect, useState } from "react"
import type { SearchResults, ResultRow } from "@/types/result"
import "mapbox-gl/dist/mapbox-gl.css"

export type MapPlace = {
    id: string
    name: string
    type: "place" | "event"
    lon: number
    lat: number
    score: number
    description: string
}

export function useSearchResults(mock = false) {
    const [places, setPlaces] = useState<MapPlace[]>([])
    const [meta, setMeta] = useState<SearchResults["meta"] | null>(null)
    const [loading, setLoading] = useState(true)
    const [error, setError] = useState<string | null>(null)

    useEffect(() => {
        async function load() {
            try {
                setLoading(true)
                setError(null)

                let json: SearchResults

                if (mock) {
                    const res = await fetch("/mock/map-data2.json")
                    console.log("mock status", res.status, res.statusText)
                    if (!res.ok) throw new Error(`Mock fetch failed: ${res.status}`)
                    json = (await res.json()) as SearchResults
                } else {
                    const res = await fetch("/api/search")
                    json = (await res.json()) as SearchResults
                }

                setMeta(json.meta)

                const mapped: MapPlace[] = json.rows.map((r: ResultRow, i) => ({
                    id: `${r.type}-${i}`,
                    name: r.name,
                    type: r.type,
                    lon: r.lon,
                    lat: r.lat,
                    score: r.score,
                    description: r.description,
                }))

                setPlaces(mapped)
            } catch (e: any) {
                setError(e?.message || "Failed to load search results")
            } finally {
                setLoading(false)
            }
        }

        load()
    }, [mock])

    return { places, meta, loading, error }
}