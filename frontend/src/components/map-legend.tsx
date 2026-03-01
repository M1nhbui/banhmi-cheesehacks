import { Card, CardContent } from "@/components/ui/card"

function Dot({ className }: { className: string }) {
  return <span className={`inline-block h-2 w-2 rounded-full ${className}`} />
}

export function MapLegend() {
  return (
    <>
      {/* small floating title */}
      <div className="absolute z-30 right-4 top-[452px] w-[340px] text-center pointer-events-none">
        <span className="text-[11px] text-muted-foreground bg-background/70 backdrop-blur px-2 py-0.5 rounded-md border border-border shadow-sm">
          Map key
        </span>
      </div>

      {/* legend card */}
      <Card className="absolute z-30 right-4 top-[480px] w-[340px] shadow-xl bg-background/80 backdrop-blur">
        <CardContent className="py-2 px-3 flex items-center justify-between text-[11px]">

          {/* score gradient */}
          <div className="flex items-center gap-2 min-w-0">
            <div className="h-1.5 w-24 rounded-full bg-gradient-to-r from-yellow-400 via-orange-500 to-red-600 shrink-0" />
            <span className="text-muted-foreground whitespace-nowrap">
              maybe → strong pick
            </span>
          </div>

          {/* events */}
          <div className="flex items-center gap-2 text-muted-foreground whitespace-nowrap">
            <Dot className="bg-sky-400" />
            <span>events</span>
          </div>

        </CardContent>
      </Card>
    </>
  )
}