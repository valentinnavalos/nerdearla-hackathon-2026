import { useParams, useSearchParams } from "react-router-dom"
import { CaptionView } from "@/components/captions/CaptionView"
import { useCaptionSocket } from "@/hooks/useCaptionSocket"
import type { Lang } from "@/types/session"

// Loaded directly as an OBS/vMix Browser Source URL: no PageShell, no shadcn chrome,
// minimal DOM/JS footprint since this page runs indefinitely in a hidden Chromium
// instance ("Shutdown source when not visible" is off for these sources).
export function OverlayPage() {
  const { sessionId } = useParams<{ sessionId: string }>()
  const [searchParams] = useSearchParams()
  const lang: Lang = searchParams.get("lang") === "en" ? "en" : "es"
  const bg = searchParams.get("bg") === "green" ? "green" : "transparent"
  const lines = Number(searchParams.get("lines")) || 3
  const size = searchParams.get("size") === "L" ? 3.4 : 2.2

  const { segments } = useCaptionSocket(sessionId ?? null, lang)

  return (
    <div
      className="relative h-dvh w-dvw"
      style={{
        background: bg === "green" ? "#00ff00" : "transparent",
        ["--caption-size" as string]: `${size}rem`,
      }}
    >
      <CaptionView segments={segments} lines={lines} overlay />
    </div>
  )
}
