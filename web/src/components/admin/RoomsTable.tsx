import { toast } from "sonner"
import { ExportMenu } from "@/components/admin/ExportMenu"
import { OverlayConfigDialog } from "@/components/admin/OverlayConfigDialog"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"
import { deleteSession, startSession, stopSession } from "@/lib/api"
import { STATUS_LABELS, statusBadgeVariant } from "@/lib/constants"
import type { Session } from "@/types/session"

interface RoomsTableProps {
  token: string
  rooms: Session[]
  onChanged: () => void
}

export function RoomsTable({ token, rooms, onChanged }: RoomsTableProps) {
  async function act(action: "start" | "stop" | "delete", id: string) {
    try {
      if (action === "start") await startSession(token, id)
      else if (action === "stop") await stopSession(token, id)
      else {
        if (!confirm("¿Borrar esta sala?")) return
        await deleteSession(token, id)
      }
      onChanged()
    } catch (err) {
      toast.error(`No se pudo ${action}: ${err instanceof Error ? err.message : err}`)
    }
  }

  return (
    <Table>
      <TableHeader>
        <TableRow>
          <TableHead>Título</TableHead>
          <TableHead>Estado</TableHead>
          <TableHead>Fuente</TableHead>
          <TableHead>Oyentes</TableHead>
          <TableHead>Acciones</TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        {rooms.map((room) => {
          const listeners = Object.values(room.metrics?.listeners ?? {}).reduce((a, b) => a + (b ?? 0), 0)
          const canStart = room.status === "CREATED" || room.status === "STOPPED" || room.status === "ERROR"
          return (
            <TableRow key={room.id}>
              <TableCell className="font-medium">{room.title}</TableCell>
              <TableCell>
                <Badge variant={statusBadgeVariant(room.status)}>{STATUS_LABELS[room.status]}</Badge>
              </TableCell>
              <TableCell>{room.source}</TableCell>
              <TableCell>{listeners}</TableCell>
              <TableCell>
                <div className="flex flex-wrap items-center gap-1.5">
                  {canStart ? (
                    <Button size="sm" onClick={() => act("start", room.id)}>
                      Start
                    </Button>
                  ) : (
                    <Button size="sm" variant="secondary" onClick={() => act("stop", room.id)}>
                      Stop
                    </Button>
                  )}
                  <Button size="sm" variant="destructive" onClick={() => act("delete", room.id)}>
                    Borrar
                  </Button>
                  <Button size="sm" variant="outline" asChild>
                    <a href={`/stage/${room.id}?token=${encodeURIComponent(token)}`} target="_blank" rel="noreferrer">
                      Escenario
                    </a>
                  </Button>
                  <Button size="sm" variant="outline" asChild>
                    <a href={`/watch/${room.id}`} target="_blank" rel="noreferrer">
                      Audiencia
                    </a>
                  </Button>
                  <OverlayConfigDialog id={room.id} />
                  <ExportMenu id={room.id} status={room.status} />
                </div>
              </TableCell>
            </TableRow>
          )
        })}
      </TableBody>
    </Table>
  )
}
