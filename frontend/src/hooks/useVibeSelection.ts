import { useCallback, useMemo, useState } from "react"

export function useVibeSelection(initial: string[] = []) {
  const [selectedVibes, setSelectedVibes] = useState<string[]>(initial)

  const toggleVibe = useCallback((key: string) => {
    setSelectedVibes((prev) => (prev.includes(key) ? prev.filter((k) => k !== key) : [...prev, key]))
  }, [])

  const clearVibes = useCallback(() => setSelectedVibes([]), [])

  const hasVibes = useMemo(() => selectedVibes.length > 0, [selectedVibes])

  return { selectedVibes, toggleVibe, clearVibes, hasVibes, setSelectedVibes }
}