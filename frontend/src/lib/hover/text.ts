// lib/hover/text.ts
export function clamp01(n: number) {
    return Math.max(0, Math.min(1, Number(n ?? 0)))
  }
  
  export function clampText(s: string | undefined | null, max = 120) {
    const t = (s ?? "").trim()
    if (!t) return ""
    return t.length > max ? t.slice(0, max - 1) + "…" : t
  }