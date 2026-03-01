// lib/hover/aestheticScore.ts
import { clamp01 } from "./text"

/**
 * Deterministic "random" based on a string seed.
 * (So the UI doesn't flicker on re-render.)
 */
function hashToUnit(seed: string) {
  let h = 2166136261
  for (let i = 0; i < seed.length; i++) {
    h ^= seed.charCodeAt(i)
    h = Math.imul(h, 16777619)
  }
  // 0..1
  return (h >>> 0) / 4294967295
}

/**
 * Adds a small, aesthetic-only jitter to the score.
 * - bounded
 * - stable per item
 * - proportional to score (so high scores stay high-ish)
 */
export function aestheticScore(score: number, seed: string, strength = 0.05) {
  const s = clamp01(score)
  const u = hashToUnit(seed) * 2 - 1 // -1..1
  const jitter = u * strength

  // Make jitter smaller when score is extreme to avoid "lying"
  const damp = 0.6 + 0.4 * (1 - Math.abs(0.5 - s) * 2) // biggest near mid
  return clamp01(s + jitter * damp)
}

export function displaySimilarity(totalScore: number, seed: string, strength = 0.015) {
    // start from total score
    const s = clamp01(totalScore)
  
    // small deterministic jitter so it doesn’t look identical everywhere
    // reuse your hashToUnit from aestheticScore.ts if you want (recommended)
    let h = 2166136261
    for (let i = 0; i < seed.length; i++) {
      h ^= seed.charCodeAt(i)
      h = Math.imul(h, 16777619)
    }
    const u = ((h >>> 0) / 4294967295) * 2 - 1 // -1..1
  
    return clamp01(s + u * strength)
  }