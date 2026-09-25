import { useState } from "react"
import { toast } from "sonner"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"
import { deleteSession, getExportUrl, startSession, stopSession } from "@/lib/api"
import { STATUS_LABELS, statusBadgeVariant } from "@/lib/constants"
import type { ExportFormat, Lang, Session } from "@/types/session"

interface RoomsTableProps {
  token: string
  rooms: Session[]
  onChanged: () => void
}

function ExportControls({ id }: { id: string }) {
  const [fmt, setFmt] = useState<ExportFormat>("srt")
  const [lang, setLang] = useState<Lang>("es")

  return (
    <div className="flex items-center gap-1">
      <Select value={fmt} onValueChange={(v) => setFmt(v as ExportFormat)}>
        <SelectTrigger size="sm" className="w-24">
          <SelectValue />
        </SelectTrigger>
        <SelectContent>
          <SelectItem value="srt">SRT</SelectItem>
          <SelectItem value="vtt">VTT</SelectItem>
          <SelectItem value="txt">TXT</SelectItem>
          <SelectItem value="md">MD (ambos)</SelectItem>
        </SelectContent>
      </Select>
      <Select value={lang} onValueChange={(v) => setLang(v as Lang)} disabled={fmt === "md"}>
        <SelectTrigger size="sm" className="w-16">
          <SelectValue />
        </SelectTrigger>
        <SelectContent>
          <SelectItem value="es">ES</SelectItem>
          <SelectItem value="en">EN</SelectItem>
        </SelectContent>
      </Select>
      <Button
        type="button"
        size="sm"
        variant="outline"
        onClick={() => window.open(getExportUrl(id, fmt, lang), "_blank")}
      >
        Exportar
      </Button>
    </div>
  )
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
                  <ExportControls id={room.id} />
                </div>
              </TableCell>
            </TableRow>
          )
        })}
      </TableBody>
    </Table>
  )
}
