import { cn } from "@/lib/utils"
import type { CaptionSegment } from "@/types/caption"
import { CaptionSegmentItem } from "./CaptionSegmentItem"

interface CaptionViewProps {
  segments: CaptionSegment[]
  lines?: number
  overlay?: boolean
  className?: string
}

export function CaptionView({ segments, lines = 3, overlay = false, className }: CaptionViewProps) {
  const visible = segments.slice(-lines)

  return (
    <section
      aria-live="polite"
      className={cn(
        "flex flex-1 min-h-0 flex-col justify-end gap-[0.35em] overflow-hidden px-4 pb-6 pt-4 [overflow-wrap:anywhere]",
        overlay && "pointer-events-none absolute inset-0 items-center justify-end pb-12 text-center",
        className,
      )}
    >
      {visible.map((segment, i) => (
        <CaptionSegmentItem
          key={segment.seg}
          segment={segment}
          isLast={i === visible.length - 1}
          overlay={overlay}
        />
      ))}
    </section>
  )
}
