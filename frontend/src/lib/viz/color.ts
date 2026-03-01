// viz/color.ts
export type RGBA = [number, number, number, number]

export function clamp01(x: number) {
  const n = Number.isFinite(x) ? x : 0
  return Math.max(0, Math.min(1, n))
}

function lerp(a: number, b: number, t: number) {
  return a + (b - a) * t
}

function mixRGB(a: [number, number, number], b: [number, number, number], t: number): [number, number, number] {
  return [lerp(a[0], b[0], t), lerp(a[1], b[1], t), lerp(a[2], b[2], t)]
}

function toRGBA(rgb: [number, number, number], alpha: number): RGBA {
  return [Math.round(rgb[0]), Math.round(rgb[1]), Math.round(rgb[2]), Math.round(alpha)]
}

// Smoothstep makes the ramp feel less “linear / harsh”
function smoothstep(t: number) {
  const x = clamp01(t)
  return x * x * (3 - 2 * x)
}

/**
 * Dark-map friendly ramp:
 * low  -> teal/cyan (cool)
 * mid  -> yellow
 * high -> magenta/pink (hot)
 *
 * This tends to read well on Mapbox dark without washing out.
 */
const RAMP_STOPS: Array<{ t: number; rgb: [number, number, number] }> = [
    { t: 0.0, rgb: [255, 235, 120] }, // warm yellow (visible on dark, not neon)
    { t: 0.45, rgb: [255, 170, 60] }, // orange
    { t: 0.75, rgb: [255, 95, 45] },  // red-orange
    { t: 1.0, rgb: [210, 40, 35] },   // deep red
  ]

function sampleRamp(tRaw: number): [number, number, number] {
  const t = smoothstep(tRaw)

  // find neighboring stops
  for (let i = 0; i < RAMP_STOPS.length - 1; i++) {
    const a = RAMP_STOPS[i]
    const b = RAMP_STOPS[i + 1]
    if (t >= a.t && t <= b.t) {
      const local = (t - a.t) / (b.t - a.t)
      return mixRGB(a.rgb, b.rgb, local)
    }
  }
  return RAMP_STOPS[RAMP_STOPS.length - 1].rgb
}

/**
 * Places (columns): score -> ramp, alpha -> readable.
 * You can pass `dim` to fade things when filtered/unfocused.
 */
export function placeFillColor(score: number, dim = 1): RGBA {
  const t = clamp01(score)
  const rgb = sampleRamp(t)

  // higher score slightly more opaque
  const a = lerp(130, 210, t) * dim
  return toRGBA(rgb, a)
}

/**
 * Events (dots): use a dedicated "signal" color so it never blends with columns.
 * Optional: tie alpha to score if you want.
 */
export function eventFillColor(score?: number, dim = 1): RGBA {
  const t = clamp01(score ?? 0.8)
  const rgb: [number, number, number] = [255, 70, 70] // red-hot signal
  const a = lerp(170, 230, t) * dim
  return toRGBA(rgb, a)
}

/**
 * Optional: stroke color for outlines or highlight rings on dark maps.
 */
export function outlineColor(dim = 1): RGBA {
  return [255, 255, 255, Math.round(90 * dim)]
}