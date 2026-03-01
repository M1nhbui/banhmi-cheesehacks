"use client"

import { useCallback, useEffect, useMemo, useState } from "react"
import type { ResultRow } from "@/types/result"

const SAVED_KEY = "saved-results-v1"

function stableId(r: ResultRow) {
  return `${r.type}:${r.name}:${r.lat.toFixed(6)}:${r.lon.toFixed(6)}`
}

function readSaved(): ResultRow[] {
  try {
    const raw = localStorage.getItem(SAVED_KEY)
    if (!raw) return []
    const parsed = JSON.parse(raw)
    return Array.isArray(parsed) ? (parsed as ResultRow[]) : []
  } catch {
    return []
  }
}

function writeSaved(rows: ResultRow[]) {
  localStorage.setItem(SAVED_KEY, JSON.stringify(rows))
}

export function useSavedResults() {
  const [savedRows, setSavedRows] = useState<ResultRow[]>([])

  useEffect(() => {
    setSavedRows(readSaved())
  }, [])

  const savedIds = useMemo(() => new Set(savedRows.map(stableId)), [savedRows])
  const savedCount = savedRows.length

  const setAll = useCallback((rows: ResultRow[]) => {
    writeSaved(rows)
    setSavedRows(rows)
  }, [])

  const toggleSaved = useCallback(
    (row: ResultRow) => {
      const id = stableId(row)
      const exists = savedRows.some((r) => stableId(r) === id)
      const next = exists ? savedRows.filter((r) => stableId(r) !== id) : [row, ...savedRows]
      setAll(next)
    },
    [savedRows, setAll]
  )

  const removeSaved = useCallback(
    (row: ResultRow) => {
      const id = stableId(row)
      const next = savedRows.filter((r) => stableId(r) !== id)
      setAll(next)
    },
    [savedRows, setAll]
  )

  const isSaved = useCallback((row: ResultRow) => savedIds.has(stableId(row)), [savedIds])

  return { savedRows, savedIds, savedCount, toggleSaved, removeSaved, isSaved }
}

export { stableId }