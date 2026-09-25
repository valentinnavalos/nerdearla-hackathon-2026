import { useEffect, useState } from "react"
import { AudioLevelMeter } from "@/components/stage/AudioLevelMeter"
import { Button } from "@/components/ui/button"
import { startSession } from "@/lib/api"
import { useMicCapture } from "@/hooks/useMicCapture"

interface MicPanelProps {
  sessionId: string
  token: string
  currentStatus: string | null
}

const RUNNING_STATUSES = new Set(["RUNNING", "ROTATING", "RECONNECTING"])

const STATUS_LABELS: Record<string, string> = {
  idle: "",
  starting: "iniciando…",
  capturing: "capturando",
  stopped: "",
  error: "error de mic: sala no iniciada",
}

export function MicPanel({ sessionId, token, currentStatus }: MicPanelProps) {
  const { status, level, ingestStatus, start, stop, listDevices } = useMicCapture()
  const [devices, setDevices] = useState<MediaDeviceInfo[]>([])
  const [deviceId, setDeviceId] = useState<string>("")
  const capturing = status === "capturing" || status === "starting"

  useEffect(() => {
    listDevices()
      .then(setDevices)
      .catch(() => {})
  }, [listDevices])

  async function ensureSessionStarted() {
    if (currentStatus && RUNNING_STATUSES.has(currentStatus)) return
    try {
      await startSession(token, sessionId)
    } catch (err) {
      // a room already running (race with another admin, or a stale `status`) is fine
      const msg = String(err instanceof Error ? err.message : err)
      if (!msg.startsWith("409") && !msg.startsWith("500")) throw err
    }
  }

  async function toggle() {
    if (capturing) {
      stop()
      return
    }
    try {
      await ensureSessionStarted()
      await start(sessionId, token, deviceId || undefined)
      const next = await listDevices()
      setDevices(next)
    } catch (err) {
      alert(`No se pudo iniciar la captura: ${err instanceof Error ? err.message : err}`)
    }
  }

  const micStatusText =
    ingestStatus?.mic_connected === false ? "mic desconectado" : STATUS_LABELS[status] ?? ""

  return (
    <div className="mx-5 mt-4 flex flex-wrap items-center gap-2">
      <AudioLevelMeter dbfs={level} />
      <Button type="button" onClick={toggle}>
        {capturing ? "Detener" : "Iniciar captura"}
      </Button>
      <select
        aria-label="Micrófono"
        value={deviceId}
        onChange={(e) => setDeviceId(e.target.value)}
        className="min-h-11 rounded-lg border border-input bg-secondary px-2.5 text-foreground"
      >
        {devices.map((d, i) => (
          <option key={d.deviceId} value={d.deviceId}>
            {d.label || `Micrófono ${i + 1}`}
          </option>
        ))}
      </select>
      <span className="text-sm text-muted-foreground">{micStatusText}</span>
      {typeof ingestStatus?.lat_p50_ms === "number" && (
        <span className="rounded-full bg-secondary px-3 py-1 text-xs font-bold">
          {Math.round(ingestStatus.lat_p50_ms)} ms
        </span>
      )}
    </div>
  )
}
