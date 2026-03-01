type ScoreKey = "similarity" | "hotness" | "crowd" | "urgency"

function clamp01(n: number) {
  const x = Number.isFinite(n) ? n : 0
  return Math.max(0, Math.min(1, x))
}

function scoreLabel(v: number) {
  const x = clamp01(v)
  if (x >= 0.9) return "Extremely high"
  if (x >= 0.75) return "High"
  if (x >= 0.55) return "Good"
  if (x >= 0.35) return "Mixed"
  return "Low"
}

function relevantCopy(similarity: number) {
  const x = clamp01(similarity)
  if (x >= 0.85) return "Highly relevant to you"
  if (x >= 0.65) return "Pretty relevant"
  if (x >= 0.45) return "Somewhat relevant"
  return "Not very relevant"
}

function hotCopy(popularity: number) {
  const x = clamp01(popularity)
  if (x >= 0.85) return "Gaining traction fast"
  if (x >= 0.65) return "Popular right now"
  if (x >= 0.45) return "Some buzz"
  return "Under the radar"
}

function urgencyCopy(urgency: number, type: "place" | "event") {
  const x = clamp01(urgency)
  if (x >= 0.85) return type === "event" ? "Hurry — closing soon" : "Busy window right now"
  if (x >= 0.65) return type === "event" ? "Time-sensitive" : "Best to go soon"
  if (x >= 0.45) return "No rush"
  return "Plenty of time"
}

function weatherCopy(weather: number) {
  const x = clamp01(weather)
  if (x >= 0.85) return "Perfect weather for this"
  if (x >= 0.65) return "Weather is on your side"
  if (x >= 0.45) return "Weather is okay"
  return "Weather might be rough"
}

function topDriver(b: Record<ScoreKey, number>): ScoreKey {
  const entries = Object.entries(b) as [ScoreKey, number][]
  entries.sort((a, b) => clamp01(b[1]) - clamp01(a[1]))
  return entries[0]?.[0] ?? "similarity"
}

/**
 * Mode-aware “headline” + one-liner insight
 */
export function formatPlaceInsight(args: {
  mode: "relevant" | "hotness" | "urgency" | "crowd" // adjust to your ScoreMode union
  type: "place" | "event"
  score: number
  breakdown: Record<ScoreKey, number>
}) {
  const { mode, type, score, breakdown } = args

  const sim = clamp01(breakdown.similarity)
  const pop = clamp01(breakdown.hotness)
  const wea = clamp01(breakdown.crowd)
  const urg = clamp01(breakdown.urgency)

  // headline depends on your selected mode
  const headline =
    mode === "relevant"
      ? relevantCopy(sim)
      : mode === "hotness"
      ? hotCopy(pop)
      : mode === "urgency"
      ? urgencyCopy(urg, type)
      : weatherCopy(wea)

  // one-liner: biggest driver overall (feels “smart”)
  const driver = topDriver(breakdown)
  const driverLine =
    driver === "similarity"
      ? `Matches your vibe (${scoreLabel(sim).toLowerCase()} similarity).`
      : driver === "hotness"
      ? `Momentum is ${scoreLabel(pop).toLowerCase()} right now.`
      : driver === "urgency"
      ? `${type === "event" ? "Timing" : "Best window"} is ${scoreLabel(urg).toLowerCase()}.`
      : `Conditions are ${scoreLabel(wea).toLowerCase()} today.`

  const pct = Math.round(clamp01(score) * 100)

  return { headline, driverLine, pct }
}