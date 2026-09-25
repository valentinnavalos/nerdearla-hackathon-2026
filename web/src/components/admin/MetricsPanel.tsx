import { Badge } from "@/components/ui/badge"
import { Card } from "@/components/ui/card"
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"
import { STATUS_LABELS, statusBadgeVariant } from "@/lib/constants"
import type { AdminSnapshot } from "@/types/admin"
import { cn } from "@/lib/utils"

function fmtUptime(s: number | null): string {
  if (s == null) return "-"
  const m = Math.floor(s / 60)
  const sec = Math.floor(s % 60)
  return `${m}:${String(sec).padStart(2, "0")}`
}

function fmtLatency(bucket: { p50?: number | null; p95?: number | null } | null | undefined): string {
  if (!bucket || (bucket.p50 == null && bucket.p95 == null)) return "-"
  const p50 = bucket.p50 != null ? Math.round(bucket.p50) : "-"
  const p95 = bucket.p95 != null ? Math.round(bucket.p95) : "-"
  return `${p50} / ${p95} ms`
}

interface MetricsPanelProps {
  snapshot: AdminSnapshot
}

export function MetricsPanel({ snapshot }: MetricsPanelProps) {
  const { live_usage, quota } = snapshot
  const quotaPct = quota.limit > 0 ? quota.used / quota.limit : 0

  return (
    <div className="space-y-3">
      <Card
        className={cn(
          "p-4 font-semibold",
          quota.limit > 0 && quotaPct > 0.8 && "text-destructive",
        )}
      >
        Live: {live_usage.used}/{live_usage.max} · Cuota hoy: {quota.used}
        {quota.limit > 0 ? `/${quota.limit}` : ""} · Costo: USD 0
      </Card>
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>Sala</TableHead>
            <TableHead>Estado</TableHead>
            <TableHead>Uptime</TableHead>
            <TableHead>Mic</TableHead>
            <TableHead>Silencio</TableHead>
            <TableHead>Latencia p50/p95 (final)</TableHead>
            <TableHead>Rot./Recon./Err.</TableHead>
            <TableHead>Último error</TableHead>
            <TableHead>Oyentes</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {snapshot.sessions.map((room) => {
            const audio = room.metrics?.audio
            const runner = room.metrics?.runner ?? {}
            const listeners = Object.entries(room.metrics?.listeners ?? {})
              .map(([l, n]) => `${l}:${n}`)
              .join(" ")
            const micAlert = room.source === "mic" && room.mic_connected === false
            const silenceAlert = !!audio?.silence_alert
            const errorAlert = room.status === "ERROR"
            const micCell =
              room.source === "mic"
                ? `${room.mic_connected ? "conectado" : "desconectado"}${
                    audio?.last_frame_age_s != null ? ` (${audio.last_frame_age_s}s)` : ""
                  }`
                : "-"
            return (
              <TableRow key={room.id} className={cn(errorAlert && "bg-destructive/10")}>
                <TableCell>{room.title}</TableCell>
                <TableCell>
                  <Badge variant={statusBadgeVariant(room.status)}>{STATUS_LABELS[room.status]}</Badge>
                </TableCell>
                <TableCell>{fmtUptime(room.uptime_s)}</TableCell>
                <TableCell className={cn(micAlert && "font-bold text-destructive")}>{micCell}</TableCell>
                <TableCell className={cn(silenceAlert && "font-bold text-destructive")}>
                  {silenceAlert ? "⚠ silencio" : "-"}
                </TableCell>
                <TableCell>{fmtLatency(audio?.final_latency_ms)}</TableCell>
                <TableCell>
                  {runner.rotations ?? 0} / {runner.reconnects ?? 0} / {runner.errors ?? 0}
                </TableCell>
                <TableCell className={cn(errorAlert && "font-bold text-destructive")}>
                  {room.last_error ?? "-"}
                </TableCell>
                <TableCell>{listeners || "-"}</TableCell>
              </TableRow>
            )
          })}
        </TableBody>
      </Table>
    </div>
  )
}
