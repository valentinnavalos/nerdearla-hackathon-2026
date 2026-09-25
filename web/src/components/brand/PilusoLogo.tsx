import { PARTNER_NAME } from "@/lib/brand"
import { cn } from "@/lib/utils"

interface PilusoLogoProps {
  variant?: "full" | "mark"
  showPartner?: boolean
  className?: string
}

// The mark is always decorative: in "full" the accessible name comes from the
// visible wordmark text, and "mark" relies on the enclosing link's aria-label.
function PilusoMark({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 32 32" aria-hidden="true" focusable="false" className={cn("size-7 shrink-0", className)}>
      <rect x="2" y="3" width="28" height="21" rx="6" className="fill-primary" />
      <path d="M8 23 L8 30 L15 23 Z" className="fill-primary" />
      <rect x="7" y="9" width="18" height="3" rx="1.5" className="fill-background" />
      <rect x="7" y="15" width="11" height="3" rx="1.5" className="fill-background" />
    </svg>
  )
}

export function PilusoLogo({ variant = "full", showPartner = false, className }: PilusoLogoProps) {
  if (variant === "mark") return <PilusoMark className={className} />

  return (
    <span className={cn("inline-flex items-center gap-2.5", className)}>
      <PilusoMark />
      <span className="flex flex-col gap-px">
        <span className="flex items-baseline gap-1.5 font-display leading-none">
          <span className="text-[1.2rem] font-bold tracking-[-0.03em]">piluso</span>
          <span className="text-[0.8rem] font-medium text-muted-foreground">Live Captions</span>
        </span>
        {showPartner && PARTNER_NAME && (
          <span className="text-xs text-muted-foreground">para {PARTNER_NAME}</span>
        )}
      </span>
    </span>
  )
}
