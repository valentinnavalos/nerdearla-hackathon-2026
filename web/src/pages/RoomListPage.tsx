import { useEffect, useState } from "react"
import { Link } from "react-router-dom"
import { PageShell } from "@/components/layout/PageShell"
import { Badge } from "@/components/ui/badge"
import { Card } from "@/components/ui/card"
import { Skeleton } from "@/components/ui/skeleton"
import { getPublicSessions } from "@/lib/api"
import { LANG_LABELS, STATUS_LABELS, statusBadgeVariant } from "@/lib/constants"
import type { PublicSession } from "@/types/session"

const POLL_MS = 5000

export function RoomListPage() {
  const [rooms, setRooms] = useState<PublicSession[] | null>(null)
  const [error, setError] = useState(false)

  useEffect(() => {
    let cancelled = false
    async function refresh() {
      try {
        const data = await getPublicSessions()
        if (!cancelled) {
          setRooms(data)
          setError(false)
        }
      } catch {
        if (!cancelled) setError(true)
      }
    }
    refresh()
    const id = setInterval(refresh, POLL_MS)
    return () => {
      cancelled = true
      clearInterval(id)
    }
  }, [])

  return (
    <PageShell>
      <div className="mb-6">
        <h1 className="text-2xl font-bold tracking-tight">Subtítulos en vivo</h1>
        <p className="text-muted-foreground">Elegí la sala y el idioma · Pick a room and a language</p>
      </div>

      {rooms === null && !error && (
        <div className="grid gap-3">
          <Skeleton className="h-24 w-full" />
          <Skeleton className="h-24 w-full" />
        </div>
      )}

      {error && <p className="text-center text-muted-foreground">No se pudo cargar la lista, reintentando…</p>}

      {rooms !== null && rooms.length === 0 && !error && (
        <p className="text-center text-muted-foreground">Todavía no hay salas activas · No rooms yet</p>
      )}

      <div className="grid gap-3">
        {rooms?.map((room) => (
          <Card key={room.id} className="gap-3 p-4">
            <div className="flex items-start justify-between gap-3">
              <span className="text-lg font-bold">{room.title}</span>
              <Badge variant={statusBadgeVariant(room.status)}>{STATUS_LABELS[room.status]}</Badge>
            </div>
            {room.speaker && <span className="text-sm text-muted-foreground">{room.speaker}</span>}
            <div className="flex flex-wrap gap-2">
              {[room.target_lang, room.source_lang].map((lang) => (
                <Link
                  key={lang}
                  to={`/watch/${room.id}?lang=${lang}`}
                  className="flex-1 rounded-full border border-input px-4 py-2 text-center text-sm font-semibold hover:border-primary"
                >
                  {LANG_LABELS[lang]}
                </Link>
              ))}
            </div>
          </Card>
        ))}
      </div>
    </PageShell>
  )
}
