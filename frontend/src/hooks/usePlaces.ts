// hooks/usePlaces.ts
import { useCallback, useEffect, useState } from "react"
import type { SearchResults } from "@/types/result"

export type MapPlace = {
    id: string
    name: string
    type: "place" | "event"
    lon: number
    lat: number
    address: string
    description: string
    score: number
    breakdown: {
        similarity: number
        popularity: number
        weather: number
        urgency: number
    }
}

export type ScoreMode = "relevant" | "hottest" | "chill" | "hidden_gems"

async function fetchJson<T>(url: string, init?: RequestInit): Promise<T> {
    const res = await fetch(url, init)
    if (!res.ok) {
        const text = await res.text().catch(() => "")
        throw new Error(`${res.status} ${res.statusText}${text ? ` — ${text}` : ""}`)
    }
    return (await res.json()) as T
}

function rowsToPlaces(rows: SearchResults["rows"]): MapPlace[] {
    return rows.map((r: any, i: number) => ({
        id: `${r.type}-${i}`,
        name: r.name,
        type: r.type,
        lon: r.lon,
        lat: r.lat,
        address: r.address,
        description: r.description,
        score: r.score,
        breakdown: r.breakdown,
    }))
}

type RefreshArgs = {
    mode: ScoreMode
    keywords: string[]
    query?: string
}

type HookOpts = {
    /**
     * Initial request (used on mount + reload)
     */
    initialMode: ScoreMode
    initialKeywords?: string[]
    initialQuery?: string

    /**
     * If true, skip backend and load from /mock/map-data2.json instead.
     * Useful for UI work when backend is down.
     */
    mock?: boolean

    /**
     * Backend base URL (only used when mock=false)
     */
    apiBase?: string // default: "http://localhost:8000"
}

export function useSearchResults({
    initialMode,
    initialKeywords = [],
    initialQuery = "",
    mock = false,
    apiBase = "http://localhost:8000",
}: HookOpts) {
    const [places, setPlaces] = useState<MapPlace[]>([])
    const [meta, setMeta] = useState<SearchResults["meta"] | null>(null)
    const [loading, setLoading] = useState(true)
    const [error, setError] = useState<string | null>(null)

    const refresh = useCallback(
        async ({ mode, keywords, query }: RefreshArgs) => {
            setLoading(true)
            setError(null)

            try {
                // ✅ Mock path: ignore mode/keywords/query and just load the file
                if (mock) {
                    const json = await fetchJson<SearchResults>("/mock/map-data2.json")
                    setMeta(json.meta)
                    setPlaces(rowsToPlaces(json.rows))
                    return json
                }

                const cleanedKeywords = [...keywords, ...(query?.trim() ? [query.trim()] : [])]
                    .map((s) => s.trim())
                    .filter(Boolean)

                const finalKeywords =
                    cleanedKeywords.length > 0
                        ? cleanedKeywords
                        : ["places to go"] // ✅ neutral fallback

                const body = { keywords: finalKeywords }

                const scored = await fetchJson<Partial<SearchResults> & { rows: SearchResults["rows"] }>(
                    `${apiBase}/score?mode=${encodeURIComponent(mode)}`,
                    {
                        method: "POST",
                        headers: { "Content-Type": "application/json" },
                        body: JSON.stringify(body),
                    }
                )

                if (scored.meta) setMeta(scored.meta as SearchResults["meta"])
                if (!scored.rows) throw new Error("Score response missing `rows`")

                setPlaces(rowsToPlaces(scored.rows))
                return scored
            } catch (e: any) {
                setError(e?.message || "Failed to load results")
                throw e
            } finally {
                setLoading(false)
            }
        },
        [apiBase, mock]
    )

    // Initial load
    useEffect(() => {
        refresh({
            mode: initialMode,
            keywords: initialKeywords,
            query: initialQuery,
        }).catch(() => {
            // error already captured in state
        })
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, []) // run once on mount

    // reload replays the initial request
    const reload = useCallback(() => {
        return refresh({
            mode: initialMode,
            keywords: initialKeywords,
            query: initialQuery,
        })
    }, [refresh, initialMode, initialKeywords, initialQuery])

    return { places, meta, loading, error, refresh, reload }
}