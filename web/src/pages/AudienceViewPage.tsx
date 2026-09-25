import { useEffect, useState } from "react"
import { Link, useParams, useSearchParams } from "react-router-dom"
import { PilusoLogo } from "@/components/brand/PilusoLogo"
import { CaptionView } from "@/components/captions/CaptionView"
import { DirectionBadge } from "@/components/layout/DirectionBadge"
import { Button } from "@/components/ui/button"
import { useCaptionSocket } from "@/hooks/useCaptionSocket"
import { getPublicSessions } from "@/lib/api"
import { BRAND_NAME } from "@/lib/brand"
import { connectionLabel } from "@/lib/connectionLabel"
import { cn } from "@/lib/utils"
import { storage } from "@/lib/storage"
import type { Lang, PublicSession } from "@/types/session"

const FONT_STEPS = [1.4, 1.75, 2.2, 2.75, 3.4] // rem

export function AudienceViewPage() {
  const { sessionId } = useParams<{ sessionId: string }>()
  const [searchParams, setSearchParams] = useSearchParams()
  const lang: Lang = searchParams.get("lang") === "en" ? "en" : "es"

  const [room, setRoom] = useState<PublicSession | null>(null)
  const [fontStep, setFontStep] = useState(() => storage.get("captions.fontStep", 2))
  const [contrast, setContrast] = useState(() => storage.get("captions.contrast", false))

  const { segments, status, connectionState, lastCloseCode } = useCaptionSocket(sessionId ?? null, lang)

  useEffect(() => {
    storage.set("captions.fontStep", fontStep)
  }, [fontStep])
  useEffect(() => {
    storage.set("captions.contrast", contrast)
  }, [contrast])

  useEffect(() => {
    let cancelled = false
    getPublicSessions()
      .then((rooms) => {
        if (cancelled) return
        const found = rooms.find((r) => r.id === sessionId)
        if (found) {
          setRoom(found)
          document.title = `${found.title} · Subtítulos · ${BRAND_NAME}`
        }
      })
      .catch(() => {})
    return () => {
      cancelled = true
    }
  }, [sessionId])

  function setLang(next: Lang) {
    setSearchParams((prev) => {
      const params = new URLSearchParams(prev)
      params.set("lang", next)
      return params
    })
  }

  const notFound = connectionState === "closed" && lastCloseCode === 4404
  const stopped = status === "STOPPED"

  return (
    <div
      className={cn("relative flex h-dvh flex-col", contrast && "bg-black text-white")}
      style={{ ["--caption-size" as string]: `${FONT_STEPS[fontStep]}rem` }}
    >
      <header className="sticky top-0 z-10 flex flex-wrap items-center gap-3 border-b border-border bg-background/80 px-5 py-3 backdrop-blur">
        <Link to="/" className="flex items-center gap-1.5 text-lg" aria-label="Volver a las salas">
          <span aria-hidden="true">←</span>
          <PilusoLogo variant="mark" className="size-6" />
        </Link>
        <div className="min-w-0 flex-1">
          <div className="truncate font-semibold">{room?.title ?? sessionId}</div>
          <div className="text-sm text-muted-foreground">
            {connectionLabel(connectionState, status, notFound)}
          </div>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          {room && <DirectionBadge sourceLang={room.source_lang} targetLang={room.target_lang} />}
          <div className="inline-flex overflow-hidden rounded-full border border-input">
            {(["es", "en"] as const).map((l) => (
              <button
                key={l}
                type="button"
                aria-pressed={lang === l}
                onClick={() => l !== lang && setLang(l)}
                className={cn(
                  "min-h-11 px-4 text-sm font-semibold",
                  lang === l ? "bg-primary text-primary-foreground" : "bg-secondary",
                )}
              >
                {l.toUpperCase()}
              </button>
            ))}
          </div>
          <Button
            variant="outline"
            size="icon"
            aria-label="Achicar letra"
            onClick={() => setFontStep((s) => Math.max(0, s - 1))}
          >
            A−
          </Button>
          <Button
            variant="outline"
            size="icon"
            aria-label="Agrandar letra"
            onClick={() => setFontStep((s) => Math.min(FONT_STEPS.length - 1, s + 1))}
          >
            A+
          </Button>
          <Button
            variant="outline"
            size="icon"
            aria-pressed={contrast}
            aria-label="Alto contraste"
            onClick={() => setContrast((c) => !c)}
          >
            ◐
          </Button>
        </div>
      </header>

      {(stopped || notFound) && (
        <p className="mx-4 mt-3 rounded-xl border border-border bg-card p-3 text-center">
          {notFound ? "Sala no encontrada · Room not found" : "La charla terminó · The talk has ended"}
          {stopped && !notFound && (
            <>
              {" "}
              <Link to={`/talk/${sessionId}?lang=${lang}`} className="font-medium text-primary underline">
                {lang === "es" ? "Ver resumen →" : "See summary →"}
              </Link>
            </>
          )}
        </p>
      )}

      <CaptionView segments={segments} lines={3} className="items-center text-center" />
    </div>
  )
}
