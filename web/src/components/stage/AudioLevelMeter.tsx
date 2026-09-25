import { cn } from "@/lib/utils"

interface AudioLevelMeterProps {
  dbfs: number
}

export function AudioLevelMeter({ dbfs }: AudioLevelMeterProps) {
  const pct = Math.max(0, Math.min(100, (dbfs + 60) * (100 / 60)))
  return (
    <div className="h-2 w-15 overflow-hidden rounded-full bg-border">
      <div
        className={cn("h-full transition-[width] duration-100 ease-linear", dbfs > -6 ? "bg-destructive" : "bg-emerald-500")}
        style={{ width: `${pct}%` }}
      />
    </div>
  )
}
