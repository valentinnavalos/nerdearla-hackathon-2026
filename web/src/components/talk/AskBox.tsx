import { useState, type FormEvent } from "react"
import { Button } from "@/components/ui/button"
import { Textarea } from "@/components/ui/textarea"
import { ApiError, askTalk } from "@/lib/api"
import type { Lang } from "@/types/session"

const MAX_CHARS = 300 // backend/post/knowledge.py ASK_MAX_CHARS

const LABELS = {
  es: {
    placeholder: "¿Qué dijo sobre…? Respondo solo con lo que se habló en la charla.",
    ask: "Preguntar",
    asking: "Pensando…",
    error: "No se pudo responder, probá de nuevo.",
  },
  en: {
    placeholder: "What did the speaker say about…? Answers come only from the talk.",
    ask: "Ask",
    asking: "Thinking…",
    error: "Could not answer, please try again.",
  },
}

export function AskBox({ sessionId, lang }: { sessionId: string; lang: Lang }) {
  const [q, setQ] = useState("")
  const [answer, setAnswer] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)
  const t = LABELS[lang]

  async function onSubmit(e: FormEvent) {
    e.preventDefault()
    const question = q.trim()
    if (!question || loading) return
    setLoading(true)
    setError(null)
    try {
      const res = await askTalk(sessionId, question)
      setAnswer(res.answer)
    } catch (err) {
      setAnswer(null)
      // 429 carries a friendly Spanish message from the backend (rate limit / Gemini busy)
      setError(err instanceof ApiError && err.detail ? err.detail : t.error)
    } finally {
      setLoading(false)
    }
  }

  return (
    <form onSubmit={onSubmit} className="space-y-3">
      <Textarea
        value={q}
        maxLength={MAX_CHARS}
        onChange={(e) => setQ(e.target.value)}
        placeholder={t.placeholder}
        aria-label={t.ask}
      />
      <div className="flex items-center justify-between gap-2">
        <span className="text-xs text-muted-foreground">
          {q.length}/{MAX_CHARS}
        </span>
        <Button type="submit" disabled={loading || !q.trim()}>
          {loading ? t.asking : t.ask}
        </Button>
      </div>
      {answer && <p className="whitespace-pre-line rounded-lg border border-border bg-card p-3">{answer}</p>}
      {error && <p className="text-sm text-destructive">{error}</p>}
    </form>
  )
}
