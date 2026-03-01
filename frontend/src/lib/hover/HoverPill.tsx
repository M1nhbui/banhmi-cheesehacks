// components/hover/HoverPill.tsx
import { cn } from "@/lib/utils"

type Props = {
  children: React.ReactNode
  variant?: "place" | "event" | "neutral" | "good" | "warn" | "fun"
  surface?: "dark" | "light"   // 👈 NEW
  className?: string
}

const VARIANT_DARK: Record<NonNullable<Props["variant"]>, string> = {
  place: "bg-emerald-500/15 text-emerald-200 border-emerald-400/20",
  event: "bg-sky-500/15 text-sky-200 border-sky-400/20",
  neutral: "bg-white/5 text-white/80 border-white/15",
  good: "bg-violet-500/15 text-violet-200 border-violet-400/20",
  warn: "bg-orange-500/15 text-orange-200 border-orange-400/20",
  fun: "bg-pink-500/15 text-pink-200 border-pink-400/20",
}

const VARIANT_LIGHT: Record<NonNullable<Props["variant"]>, string> = {
  place: "bg-emerald-50 text-emerald-700 border-emerald-200",
  event: "bg-sky-50 text-sky-700 border-sky-200",
  neutral: "bg-muted text-foreground border-border",
  good: "bg-violet-50 text-violet-700 border-violet-200",
  warn: "bg-orange-50 text-orange-700 border-orange-200",
  fun: "bg-pink-50 text-pink-700 border-pink-200",
}

export function HoverPill({
  children,
  variant = "neutral",
  surface = "dark",
  className,
}: Props) {
  const palette =
    surface === "light" ? VARIANT_LIGHT[variant] : VARIANT_DARK[variant]

  return (
    <span
      className={cn(
        "inline-flex items-center rounded-full border px-2 py-1 text-[11px] leading-none font-medium",
        palette,
        className
      )}
    >
      {children}
    </span>
  )
}