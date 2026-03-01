import { Button } from "@/components/ui/button"
import { Bookmark } from "lucide-react"

export function SavedToggleButton({
  count,
  open,
  onToggle,
}: {
  count: number
  open: boolean
  onToggle: () => void
}) {
  return (
    <div className="absolute z-40 bottom-4 right-4">
      <Button
        type="button"
        variant={open ? "default" : "secondary"}
        className="relative h-12 w-12 rounded-full shadow-lg p-0 cursor-pointer"
        onClick={onToggle}
      >
        <Bookmark className="h-5 w-5" />

        {/* count badge */}
        {count > 0 && (
          <span className="absolute -top-1 -right-1 min-w-[20px] h-[20px] px-1 flex items-center justify-center rounded-full bg-primary text-primary-foreground text-[11px] font-semibold leading-none tabular-nums">
            {count}
          </span>
        )}
      </Button>
    </div>
  )
}