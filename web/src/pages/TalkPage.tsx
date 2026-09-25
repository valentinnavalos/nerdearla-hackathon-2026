import { useEffect, useState, type ReactNode } from "react"
import { Link, useParams, useSearchParams } from "react-router-dom"
import { PageShell } from "@/components/layout/PageShell"
import { AskBox } from "@/components/talk/AskBox"
import { NotebookLMActions } from "@/components/talk/NotebookLMActions"
import { Quiz } from "@/components/talk/Quiz"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Skeleton } from "@/components/ui/skeleton"
import { getExportUrl, getKnowledge, getPublicSessions } from "@/lib/api"
import { BRAND_NAME } from "@/lib/brand"
import type { KnowledgeResponse, Lang, PublicSession } from "@/types/session"

const POLL_MS = 5000

const LABELS = {
  es: {
    title: "Después de la charla",
    live: "La charla sigue en vivo.",
    watch: "Ver subtítulos",
    pending: "Generando resumen…",
    error: "El resumen no está disponible, pero podés descargar la transcripción o llevarla a NotebookLM.",
    summary: "Resumen",
    keyPoints: "Puntos clave",
    quiz: "Quiz",
    ask: "Preguntale a la charla",
    notebooklm: "Seguir estudiando en NotebookLM",
    notebooklmHint:
      "Copiá la transcripción con el resumen y pegala como fuente en un notebook nuevo: podés chatear con la charla o generar un podcast.",
    downloads: "Descargas",
    notFound: "Sala no encontrada",
  },
  en: {
    title: "After the talk",
    live: "The talk is still live.",
    watch: "Watch captions",
    pending: "Generating summary…",
    error: "The summary is not available, but you can still download the transcript or take it to NotebookLM.",
    summary: "Summary",
    keyPoints: "Key points",
    quiz: "Quiz",
    ask: "Ask the talk",
    notebooklm: "Keep studying in NotebookLM",
    notebooklmHint:
      "Copy the transcript with its summary and paste it as a source in a new notebook: chat with the talk or generate a podcast.",
    downloads: "Downloads",
    notFound: "Room not found",
  },
}

function Section({ title, children }: { title: string; children: ReactNode }) {
  return (
    <section className="space-y-3">
      <h2 className="text-lg font-semibold tracking-tight">{title}</h2>
      {children}
    </section>
  )
}

export function TalkPage() {
  const { sessionId } = useParams<{ sessionId: string }>()
  const [searchParams, setSearchParams] = useSearchParams()
  const lang: Lang = searchParams.get("lang") === "en" ? "en" : "es"
  const t = LABELS[lang]

  const [room, setRoom] = useState<PublicSession | null | undefined>(undefined)
  const [kp, setKp] = useState<KnowledgeResponse | null>(null)

  const live = room ? room.status !== "STOPPED" && room.status !== "ERROR" && room.status !== "CREATED" : false
  const pending = kp?.kp_status === "pending"
  // first load, then keep polling while the talk is live or the Knowledge Pack is being generated (T3.5)
  const polling = live || pending

  useEffect(() => {
    if (!sessionId) return
    let cancelled = false
    const load = () =>
      Promise.all([getPublicSessions().catch(() => null), getKnowledge(sessionId).catch(() => null)]).then(
        ([rooms, knowledge]) => {
          if (cancelled) return
          if (rooms) setRoom(rooms.find((r) => r.id === sessionId) ?? null)
          if (knowledge) setKp(knowledge)
        },
      )
    load()
    const id = polling ? window.setInterval(load, POLL_MS) : undefined
    return () => {
      cancelled = true
      window.clearInterval(id)
    }
  }, [sessionId, polling])

  useEffect(() => {
    if (room) document.title = `${room.title} · ${t.title} · ${BRAND_NAME}`
  }, [room, t.title])

  function setLang(next: Lang) {
    setSearchParams((prev) => {
      const params = new URLSearchParams(prev)
      params.set("lang", next)
      return params
    })
  }

  if (!sessionId) return null
  const knowledge = kp?.knowledge ?? null

  return (
    <PageShell title={t.title}>
      <div className="space-y-8">
        <header className="flex flex-wrap items-start justify-between gap-3">
          <div className="space-y-1">
            {room === undefined ? (
              <Skeleton className="h-8 w-64" />
            ) : (
              <h1 className="text-2xl font-bold tracking-tight">{room ? room.title : t.notFound}</h1>
            )}
            {room?.speaker && <p className="text-muted-foreground">{room.speaker}</p>}
          </div>
          <div className="flex gap-1" role="group" aria-label="Idioma · Language">
            {(["es", "en"] as const).map((l) => (
              <Button key={l} size="sm" variant={lang === l ? "default" : "outline"} onClick={() => setLang(l)}>
                {l.toUpperCase()}
              </Button>
            ))}
          </div>
        </header>

        {live && (
          <p className="flex flex-wrap items-center justify-between gap-2 rounded-xl border border-border bg-card p-3">
            {t.live}
            <Button size="sm" variant="outline" asChild>
              <Link to={`/watch/${sessionId}?lang=${lang}`}>{t.watch}</Link>
            </Button>
          </p>
        )}

        {pending && (
          <div className="space-y-3" aria-live="polite">
            <p className="text-muted-foreground">{t.pending}</p>
            <Skeleton className="h-4 w-full" />
            <Skeleton className="h-4 w-5/6" />
            <Skeleton className="h-4 w-2/3" />
          </div>
        )}
        {kp?.kp_status === "error" && <p className="text-muted-foreground">{t.error}</p>}

        {knowledge && (
          <>
            <Section title={t.summary}>
              <p className="leading-relaxed">{lang === "es" ? knowledge.summary_es : knowledge.summary_en}</p>
              {knowledge.terms.length > 0 && (
                <div className="flex flex-wrap gap-1.5">
                  {knowledge.terms.map((term) => (
                    <Badge key={term} variant="secondary">
                      {term}
                    </Badge>
                  ))}
                </div>
              )}
            </Section>

            {knowledge.key_points.length > 0 && (
              <Section title={t.keyPoints}>
                <ul className="space-y-2">
                  {knowledge.key_points.map((p, i) => (
                    <li key={i} className="flex gap-3">
                      <span className="shrink-0 font-mono text-sm text-muted-foreground">[{p.t}]</span>
                      <span>{lang === "es" ? p.es : p.en}</span>
                    </li>
                  ))}
                </ul>
              </Section>
            )}

            {knowledge.quiz.length > 0 && (
              <Section title={t.quiz}>
                <Quiz key={lang} questions={knowledge.quiz} lang={lang} />
              </Section>
            )}
          </>
        )}

        {room && !live && (
          <Section title={t.ask}>
            <AskBox sessionId={sessionId} lang={lang} />
          </Section>
        )}

        <Section title={t.notebooklm}>
          <p className="text-sm text-muted-foreground">{t.notebooklmHint}</p>
          <NotebookLMActions
            sessionId={sessionId}
            lang={lang}
            notebookUrl={kp?.notebooklm_url ?? null}
            version={`${kp?.kp_status}-${room?.status}`}
          />
        </Section>

        <Section title={t.downloads}>
          <div className="flex flex-wrap gap-2">
            {(["srt", "vtt", "txt"] as const).map((fmt) => (
              <Button key={fmt} variant="outline" asChild>
                <a href={getExportUrl(sessionId, fmt, lang)} target="_blank" rel="noreferrer">
                  {fmt.toUpperCase()} ({lang.toUpperCase()})
                </a>
              </Button>
            ))}
            <Button variant="outline" asChild>
              <a href={getExportUrl(sessionId, "md")} target="_blank" rel="noreferrer">
                MD (ES + EN)
              </a>
            </Button>
          </div>
        </Section>
      </div>
    </PageShell>
  )
}
