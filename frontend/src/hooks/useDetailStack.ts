"use client"

import { useCallback, useState } from "react"
import type { ResultRow } from "@/types/result"
import type { PickingInfo } from "@deck.gl/core"

export function useDetailStack() {
  const [selected, setSelected] = useState<ResultRow | null>(null)
  const [savedOpen, setSavedOpen] = useState(false)
  const [detailFromSaved, setDetailFromSaved] = useState(false)

  const closeDetail = useCallback(() => {
    setSelected(null)
    setDetailFromSaved(false)
  }, [])

  const openDetailFromMap = useCallback((info: PickingInfo<any>) => {
    if (!info?.object) return
    setSelected(info.object as ResultRow)
    setSavedOpen(false)
    setDetailFromSaved(false)
  }, [])

  const openSavedPanel = useCallback(() => {
    setSavedOpen(true)
    setSelected(null)
    setDetailFromSaved(false)
  }, [])

  const toggleSavedPanel = useCallback(() => {
    setSavedOpen((v) => {
      const next = !v
      if (next) {
        setSelected(null)
        setDetailFromSaved(false)
      }
      return next
    })
  }, [])

  const selectFromSavedList = useCallback((row: ResultRow) => {
    setSelected(row)
    setSavedOpen(false)
    setDetailFromSaved(true)
  }, [])

  const backToSavedList = useCallback(() => {
    setSelected(null)
    setSavedOpen(true)
    setDetailFromSaved(false)
  }, [])

  return {
    selected,
    savedOpen,
    detailFromSaved,

    setSelected,
    setSavedOpen,

    closeDetail,
    openDetailFromMap,
    openSavedPanel,
    toggleSavedPanel,
    selectFromSavedList,
    backToSavedList,
  }
}