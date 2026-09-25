import { useCallback, useEffect, useState } from "react"
import { toast } from "sonner"
import { AdminLoginGate } from "@/components/admin/AdminLoginGate"
import { CreateRoomDialog } from "@/components/admin/CreateRoomDialog"
import { MetricsPanel } from "@/components/admin/MetricsPanel"
import { RoomsTable } from "@/components/admin/RoomsTable"
import { PageShell } from "@/components/layout/PageShell"
import { Button } from "@/components/ui/button"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { useAdminSocket } from "@/hooks/useAdminSocket"
import { useAuthToken } from "@/hooks/useAuthToken"
import { ApiError, getSessions } from "@/lib/api"
import type { Session } from "@/types/session"

const REFRESH_MS = 4000

export function AdminPage() {
  const { token, setToken } = useAuthToken()
  const [authed, setAuthed] = useState(false)
  const [authError, setAuthError] = useState<string | null>(null)
  const [rooms, setRooms] = useState<Session[]>([])

  const refreshRooms = useCallback(
    async (currentToken: string) => {
      try {
        const data = await getSessions(currentToken)
        setRooms(data.sessions)
        return true
      } catch (err) {
        if (err instanceof ApiError) throw err
        toast.error("No se pudo actualizar la lista de salas")
        return false
      }
    },
    [],
  )

  async function tryEnter(candidate: string) {
    try {
      await refreshRooms(candidate)
      setToken(candidate)
      setAuthed(true)
      setAuthError(null)
    } catch (err) {
      setAuthError(`No se pudo entrar: ${err instanceof Error ? err.message : err}`)
    }
  }

  useEffect(() => {
    if (token) tryEnter(token)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  useEffect(() => {
    if (!authed) return
    const id = setInterval(() => refreshRooms(token).catch(() => {}), REFRESH_MS)
    return () => clearInterval(id)
  }, [authed, token, refreshRooms])

  const { snapshot, unauthorized } = useAdminSocket(authed ? token : null)

  useEffect(() => {
    if (unauthorized) {
      setAuthed(false)
      setAuthError("Sesión expirada, ingresá el token de nuevo")
    }
  }, [unauthorized])

  if (!authed) {
    return (
      <PageShell title="Consola de operador">
        <AdminLoginGate onSubmit={tryEnter} error={authError} />
      </PageShell>
    )
  }

  return (
    <PageShell title="Consola de operador">
      <div className="space-y-10">
        <section className="flex items-center justify-between">
          <h1 className="text-xl font-bold tracking-tight">Consola de operador</h1>
          <div className="flex gap-2">
            <Button variant="outline" onClick={() => refreshRooms(token)}>
              Actualizar
            </Button>
            <CreateRoomDialog token={token} onCreated={() => refreshRooms(token)} />
          </div>
        </section>

        <Tabs defaultValue="rooms">
          <TabsList>
            <TabsTrigger value="rooms">Salas</TabsTrigger>
            <TabsTrigger value="monitoring">Monitoreo</TabsTrigger>
          </TabsList>
          <TabsContent value="rooms">
            <RoomsTable token={token} rooms={rooms} onChanged={() => refreshRooms(token)} />
          </TabsContent>
          <TabsContent value="monitoring">
            {snapshot ? <MetricsPanel snapshot={snapshot} /> : <p className="text-muted-foreground">Conectando…</p>}
          </TabsContent>
        </Tabs>
      </div>
    </PageShell>
  )
}
