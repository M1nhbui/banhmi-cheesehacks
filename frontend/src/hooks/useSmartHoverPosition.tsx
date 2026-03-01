import { useLayoutEffect, useRef, useState } from "react"

type Pos = { left: number; top: number }

/**
 * Keeps a floating element fully inside viewport.
 * Flips sides if needed and clamps to edges.
 */
export function useSmartHoverPosition(
  x: number,
  y: number,
  offset = 12
) {
  const ref = useRef<HTMLDivElement | null>(null)
  const [pos, setPos] = useState<Pos>({ left: x + offset, top: y + offset })

  useLayoutEffect(() => {
    const el = ref.current
    if (!el) return

    const rect = el.getBoundingClientRect()
    const vw = window.innerWidth
    const vh = window.innerHeight

    let left = x + offset
    let top = y + offset

    // flip horizontally if overflowing right
    if (left + rect.width > vw - offset) {
      left = x - rect.width - offset
    }

    // flip vertically if overflowing bottom
    if (top + rect.height > vh - offset) {
      top = y - rect.height - offset
    }

    // clamp final values
    left = Math.max(offset, Math.min(left, vw - rect.width - offset))
    top = Math.max(offset, Math.min(top, vh - rect.height - offset))

    setPos({ left, top })
  }, [x, y, offset])

  return { ref, pos }
}