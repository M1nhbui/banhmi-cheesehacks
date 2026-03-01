// viz/event-style.ts
export type RGBA = [number, number, number, number]

export function clamp01(x: number) {
  const n = Number.isFinite(x) ? x : 0
  return Math.max(0, Math.min(1, n))
}

function lerp(a: number, b: number, t: number) {
  return a + (b - a) * t
}

// Events should be cool on top of warm heatmap
const EVENT_CORE: [number, number, number] = [80, 190, 255]   // cyan-blue
const EVENT_HALO: [number, number, number] = [80, 190, 255]   // same hue

export function eventCoreColor(score?: number): RGBA {
  const t = clamp01(score ?? 0.8)
  const a = lerp(190, 240, t)
  return [EVENT_CORE[0], EVENT_CORE[1], EVENT_CORE[2], Math.round(a)]
}

export function eventHaloColor(score?: number): RGBA {
  const t = clamp01(score ?? 0.8)
  // halo is more transparent
  const a = lerp(40, 90, t)
  return [EVENT_HALO[0], EVENT_HALO[1], EVENT_HALO[2], Math.round(a)]
}

export function eventCoreRadiusMeters(score?: number) {
  const t = clamp01(score ?? 0.8)
  return lerp(18, 34, t)
}

export function eventHaloRadiusMeters(score?: number) {
  const t = clamp01(score ?? 0.8)
  return lerp(45, 80, t)
}