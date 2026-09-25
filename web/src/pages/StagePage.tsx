import { useEffect, useState } from "react"
import { useParams, useSearchParams } from "react-router-dom"
import { PilusoLogo } from "@/components/brand/PilusoLogo"
import { CaptionView } from "@/components/captions/CaptionView"
import { DirectionBadge } from "@/components/layout/DirectionBadge"
import { MicPanel } from "@/components/stage/MicPanel"
import { QrCodePanel } from "@/components/stage/QrCodePanel"
import { Button } from "@/components/ui/button"
import { useCaptionSocket } from "@/hooks/useCaptionSocket"
import { getNetworkInfo, getPublicSessions, getSessions } from "@/lib/api"
import { BRAND_NAME } from "@/lib/brand"
import { connectionLabel } from "@/lib/connectionLabel"
import { cn } from "@/lib/utils"
import type { Lang, PublicSession } from "@/types/session"

export function StagePage() {
  const { sessionId } = useParams<{ sessionId: string }>()
  const [searchParams, setSearchParams] = useSearchParams()
  const token = searchParams.get("token") ?? ""
  const lang: Lang = searchParams.get("lang") === "en" ? "en" : "es"

  const [room, setRoom] = useState<PublicSession | null>(null)
  const [isMicRoom, setIsMicRoom] = useState(false)
  const [audienceHost, setAudienceHost] = useState(location.host)

  const { segments, status, connectionState, lastCloseCode } = useCaptionSocket(sessionId ?? null, lang)
  const notFound = connectionState === "closed" && lastCloseCode === 4404

  useEffect(() => {
    let cancelled = false
    getPublicSessions()
      .then((rooms) => {
        if (cancelled) return
        const found = rooms.find((r) => r.id === sessionId)
        if (found) {
          setRoom(found)
          document.title = `${found.title} · Escenario · ${BRAND_NAME}`
        }
      })
      .catch(() => {})
    return () => {
      cancelled = true
    }
  }, [sessionId])

  useEffect(() => {
    // localhost/127.0.0.1 is useless in a QR code for a phone on the same Wi-Fi:
    // swap it for the machine's LAN-facing IP, keeping the current port.
    if (!["localhost", "127.0.0.1"].includes(location.hostname)) return
    let cancelled = false
    getNetworkInfo()
      .then(({ lan_ip }) => {
        if (!cancelled && lan_ip) setAudienceHost(`${lan_ip}${location.port ? `:${location.port}` : ""}`)
      })
      .catch(() => {})
    return () => {
      cancelled = true
    }
  }, [])

  useEffect(() => {
    if (!token || !sessionId) return
    let cancelled = false
    getSessions(token)
      .then((data) => {
        if (cancelled) return
        const found = data.sessions.find((r) => r.id === sessionId)
        if (found?.source === "mic") setIsMicRoom(true)
      })
      .catch(() => {})
    return () => {
      cancelled = true
    }
  }, [token, sessionId])

  function setLang(next: Lang) {
    setSearchParams((prev) => {
      const params = new URLSearchParams(prev)
      params.set("lang", next)
      return params
    })
  }

  const audienceUrl = sessionId ? `${location.protocol}//${audienceHost}/watch/${sessionId}?lang=es` : ""

  return (
    <div className="relative flex h-dvh flex-col bg-background">
      <header className="sticky top-0 z-10 flex flex-wrap items-center gap-3 border-b border-border bg-background/80 px-5 py-3 backdrop-blur">
        <PilusoLogo showPartner className="border-r border-border pr-4" />
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
            aria-label="Pantalla completa"
            onClick={() => document.documentElement.requestFullscreen?.().catch(() => {})}
          >
            ⛶
          </Button>
        </div>
      </header>

      {isMicRoom && token && sessionId && (
        <MicPanel sessionId={sessionId} token={token} currentStatus={status} />
      )}

      {(status === "STOPPED" || notFound) && (
        <p className="mx-4 mt-3 rounded-xl border border-border bg-card p-3 text-center">
          {notFound ? "Sala no encontrada" : "La charla terminó"}
        </p>
      )}

      <CaptionView segments={segments} lines={2} overlay className="max-w-[90vw]" />

      {audienceUrl && <QrCodePanel url={audienceUrl} />}
    </div>
  )
}
