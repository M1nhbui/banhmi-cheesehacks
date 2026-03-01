// lib/hover/tags.ts
import type { MapPlace } from "@/hooks/usePlaces"
import { clamp01 } from "./text"

export type HoverTag = {
  key: string
  text: string
  tone?: "neutral" | "good" | "warn" | "fun"
}

const FUNNY_FALLBACKS = [
  "🫥 nothing’s calling",
  "😴 vibes unclear",
  "🤷‍♂️ roll the dice",
  "🧊 too quiet to rank",
]

function pickFunny() {
  return FUNNY_FALLBACKS[Math.floor(Math.random() * FUNNY_FALLBACKS.length)]
}

/**
 * Main “status” label based on FINAL score (sigmoid output).
 * This is what people see instead of a percent.
 */
export function scoreToStatus(score: number): HoverTag {
  const s = clamp01(score)

  // If the whole thing is basically zero, don’t say "not relevant"
  if (s <= 0.02) return { key: "meh", text: pickFunny(), tone: "fun" }

  if (s >= 0.85) return { key: "top", text: "✨ top pick", tone: "good" }
  if (s >= 0.65) return { key: "strong", text: "✅ great fit", tone: "good" }
  if (s >= 0.45) return { key: "good", text: "👍 worth it", tone: "neutral" }
  if (s >= 0.25) return { key: "maybe", text: "👀 maybe", tone: "neutral" }

  return { key: "low", text: "🫧 low signal", tone: "neutral" }
}

/**
 * Converts component scores into short, human tags.
 * Tune thresholds to your taste.
 *
 * NOTE: Your MapPlace.breakdown fields are:
 * similarity, popularity, weather, urgency
 */
export function breakdownToTags(b: MapPlace["breakdown"], score: number): HoverTag[] {
  const tags: HoverTag[] = []

  const urgency = clamp01(b.urgency)
  const hotness = clamp01(b.hotness)
  const crowd = clamp01(b.crowd)
  // similarity exists, but you said it’s often ~0; we don’t surface it.
  // const similarity = clamp01(b.similarity)

  // urgency -> “hurry”
  if (urgency >= 0.2) tags.push({ key: "urgent", text: "🔥 hurry", tone: "warn" })
  else if (urgency >= 0.08) tags.push({ key: "soon", text: "⏳ soon", tone: "neutral" })

  // popularity -> “party / busy”
  if (hotness >= 0.35) tags.push({ key: "party", text: "🎉 you know what's up!!!", tone: "fun" })
  else if (hotness >= 0.18) tags.push({ key: "buzz", text: "🧑‍🤝‍🧑 buzzing", tone: "fun" })

  // weather -> “nice out”
  if (crowd >= 0.25) tags.push({ key: "weather", text: "🍾 par-teyyyy", tone: "good" })

  // If we somehow got tags but overall score is low, be honest without being harsh
  const s = clamp01(score)
  if (tags.length === 0 && s <= 0.08) tags.push({ key: "weak", text: "🫧 low signal", tone: "neutral" })

  // Cap to keep it tidy
  return tags.slice(0, 3)
}