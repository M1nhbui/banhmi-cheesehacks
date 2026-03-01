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
        className="shadow-lg"
        onClick={onToggle}
      >
        <Bookmark className="h-4 w-4 mr-2" />
        Saved
        <span className="ml-2 rounded-md bg-background/30 px-2 py-0.5 text-xs tabular-nums">
          {count}
        </span>
      </Button>
    </div>
  )
}