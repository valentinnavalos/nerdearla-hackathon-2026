import { useEffect, useRef, useState } from "react"
import { cn } from "@/lib/utils"
import type { CaptionSegment } from "@/types/caption"

interface CaptionSegmentItemProps {
  segment: CaptionSegment
  isLast: boolean
  overlay?: boolean
}

// Rendered with key={segment.seg} by the caller: React's key-based reconciliation
// updates this node's text in place across interim -> final transitions instead of
// remounting it, which is what avoids the flicker the old captions.js hand-rolled
// via manual DOM node reuse.
export function CaptionSegmentItem({ segment, isLast, overlay }: CaptionSegmentItemProps) {
  const [entered, setEntered] = useState(false)
  const [settled, setSettled] = useState(false)
  const wasFinalRef = useRef(segment.final)

  useEffect(() => {
    const raf = requestAnimationFrame(() => setEntered(true))
    return () => cancelAnimationFrame(raf)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  useEffect(() => {
    if (segment.final && !wasFinalRef.current) {
      setSettled(false)
      // restart the flash animation even if it's still running
      requestAnimationFrame(() => setSettled(true))
    }
    wasFinalRef.current = segment.final
  }, [segment.final])

  return (
    <p
      className={cn(
        "m-0 max-w-[32ch] text-[length:var(--caption-size)] font-semibold leading-tight transition-[opacity,transform] duration-200 ease-out",
        !isLast && "opacity-70",
        segment.final ? "text-foreground" : "italic font-medium text-muted-foreground opacity-100",
        !entered && "opacity-0 translate-y-2",
        settled && "animate-caption-settle",
        overlay &&
          "max-w-[80ch] text-white [text-shadow:-2px_-2px_0_#000,2px_-2px_0_#000,-2px_2px_0_#000,2px_2px_0_#000]",
        overlay && !segment.final && "text-neutral-200",
      )}
    >
      {segment.text}
    </p>
  )
}
