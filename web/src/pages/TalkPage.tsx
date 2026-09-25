import { useParams } from "react-router-dom"
import { PageShell } from "@/components/layout/PageShell"
import { Button } from "@/components/ui/button"
import { getExportUrl } from "@/lib/api"

// talk.html/talk.js in the old frontend were unimplemented stubs (TASKS.md T3.5:
// Knowledge Pack / quiz / ask-the-talk). That feature is separate follow-up work
// pending its backend; this route is only a placeholder so it's wired up already.
export function TalkPage() {
  const { sessionId } = useParams<{ sessionId: string }>()

  return (
    <PageShell title="Después de la charla">
      <div className="space-y-4">
        <h1 className="text-2xl font-bold tracking-tight">Próximamente</h1>
        <p className="text-muted-foreground">
          El Knowledge Pack, quiz y "preguntale a la charla" todavía no están disponibles. Mientras tanto,
          podés descargar la transcripción de esta sala.
        </p>
        {sessionId && (
          <div className="flex flex-wrap gap-2">
            {(["srt", "vtt", "txt", "md"] as const).map((fmt) => (
              <Button key={fmt} variant="outline" asChild>
                <a href={getExportUrl(sessionId, fmt)} target="_blank" rel="noreferrer">
                  {fmt.toUpperCase()}
                </a>
              </Button>
            ))}
          </div>
        )}
      </div>
    </PageShell>
  )
}
