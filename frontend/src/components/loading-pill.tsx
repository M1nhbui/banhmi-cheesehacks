export function LoadingPill({ show }: { show: boolean }) {
    if (!show) return null
    return (
      <div className="absolute z-20 top-4 left-4 bg-black/60 text-white px-3 py-1 rounded-md text-sm">
        Loading places...
      </div>
    )
  }