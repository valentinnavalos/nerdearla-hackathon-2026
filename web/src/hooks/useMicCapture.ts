import { useCallback, useRef, useState } from "react"
import { wsUrl } from "@/lib/ws"
import type { IngestStatusMessage } from "@/types/admin"

const BACKOFF_S = [1, 2, 4, 8, 10]
const BUFFER_WHILE_DISCONNECTED = 30 // ~3s of 100ms frames, capped to avoid unbounded memory growth

export type MicCaptureStatus = "idle" | "starting" | "capturing" | "stopped" | "error"

// Ported near-verbatim from frontend/js/mic.js: getUserMedia -> AudioWorklet (pcm-worklet.js,
// served unbundled from public/) -> 100ms PCM16 16kHz frames -> binary WS to /ws/ingest/{id}.
// Kept as a plain class (not React state) since none of this belongs in React's render cycle.
class MicCapture {
  private stream: MediaStream | null = null
  private ctx: AudioContext | null = null
  private node: AudioWorkletNode | null = null
  private ws: WebSocket | null = null
  private attempt = 0
  private retryTimer: ReturnType<typeof setTimeout> | null = null
  private buffer: ArrayBuffer[] = []
  private wakeLock: WakeLockSentinel | null = null
  private sessionId: string | null = null
  private token: string | null = null
  private stopped = true

  private onLevel: (dbfs: number) => void
  private onStatus: (status: MicCaptureStatus) => void
  private onIngestStatus: (msg: IngestStatusMessage) => void

  constructor(
    onLevel: (dbfs: number) => void,
    onStatus: (status: MicCaptureStatus) => void,
    onIngestStatus: (msg: IngestStatusMessage) => void,
  ) {
    this.onLevel = onLevel
    this.onStatus = onStatus
    this.onIngestStatus = onIngestStatus
  }

  async listDevices(): Promise<MediaDeviceInfo[]> {
    const devices = await navigator.mediaDevices.enumerateDevices()
    return devices.filter((d) => d.kind === "audioinput")
  }

  // Must be called from inside a click handler: browsers require a user gesture
  // before letting a page open an AudioContext / use the mic.
  async start(sessionId: string, token: string, deviceId?: string): Promise<void> {
    this.stop()
    this.stopped = false
    this.sessionId = sessionId
    this.token = token
    this.onStatus("starting")
    try {
      this.ctx = new AudioContext()
      this.stream = await navigator.mediaDevices.getUserMedia({
        audio: {
          deviceId: deviceId ? { exact: deviceId } : undefined,
          channelCount: 1,
          echoCancellation: false,
          noiseSuppression: false,
          autoGainControl: false,
        },
      })
      await this.ctx.audioWorklet.addModule("/pcm-worklet.js")
      this.node = new AudioWorkletNode(this.ctx, "pcm-worklet")
      this.node.port.onmessage = (e) => this.onWorkletMessage(e.data)
      this.ctx.createMediaStreamSource(this.stream).connect(this.node)
      this.openWs()
      try {
        this.wakeLock = (await navigator.wakeLock?.request("screen")) ?? null
      } catch {
        /* not fatal: screen may just dim */
      }
      this.onStatus("capturing")
    } catch (err) {
      this.onStatus("error")
      this.stop()
      throw err
    }
  }

  stop(finalStatus: MicCaptureStatus = "stopped"): void {
    this.stopped = true
    if (this.retryTimer) clearTimeout(this.retryTimer)
    if (this.ws) {
      const ws = this.ws
      this.ws = null
      ws.close()
    }
    if (this.node) {
      this.node.port.onmessage = null
      this.node.disconnect()
      this.node = null
    }
    if (this.stream) {
      for (const track of this.stream.getTracks()) track.stop()
      this.stream = null
    }
    if (this.ctx) {
      this.ctx.close().catch(() => {})
      this.ctx = null
    }
    if (this.wakeLock) {
      this.wakeLock.release().catch(() => {})
      this.wakeLock = null
    }
    this.buffer.length = 0
    this.onStatus(finalStatus)
  }

  private onWorkletMessage(msg: { type: string; dbfs?: number; buffer?: ArrayBuffer }) {
    if (msg.type === "level" && msg.dbfs !== undefined) {
      this.onLevel(msg.dbfs)
    } else if (msg.type === "frame" && msg.buffer) {
      this.send(msg.buffer)
    }
  }

  private send(buffer: ArrayBuffer) {
    if (this.ws && this.ws.readyState === WebSocket.OPEN) {
      this.ws.send(buffer)
    } else {
      this.buffer.push(buffer)
      if (this.buffer.length > BUFFER_WHILE_DISCONNECTED) this.buffer.shift()
    }
  }

  private openWs() {
    if (this.stopped) return
    const path = `/ws/ingest/${encodeURIComponent(this.sessionId!)}?token=${encodeURIComponent(this.token!)}`
    const ws = new WebSocket(wsUrl(path))
    ws.binaryType = "arraybuffer"
    this.ws = ws
    ws.onopen = () => {
      this.attempt = 0
      while (this.buffer.length) ws.send(this.buffer.shift()!)
    }
    ws.onmessage = (e) => {
      try {
        this.onIngestStatus(JSON.parse(e.data))
      } catch {
        /* ignore malformed status messages */
      }
    }
    ws.onclose = (e) => {
      if (this.ws !== ws || this.stopped) return
      this.ws = null
      if (e.code === 4404) {
        // the room doesn't exist or was never started: retrying forever would
        // just loop silently, so surface it instead.
        this.stop("error")
        return
      }
      const delay = BACKOFF_S[Math.min(this.attempt, BACKOFF_S.length - 1)]
      this.attempt += 1
      this.retryTimer = setTimeout(() => this.openWs(), delay * 1000)
    }
  }
}

export function useMicCapture() {
  const [status, setStatus] = useState<MicCaptureStatus>("idle")
  const [level, setLevel] = useState(0)
  const [ingestStatus, setIngestStatus] = useState<IngestStatusMessage | null>(null)
  const captureRef = useRef<MicCapture | null>(null)

  function capture(): MicCapture {
    if (!captureRef.current) {
      captureRef.current = new MicCapture(setLevel, setStatus, setIngestStatus)
    }
    return captureRef.current
  }

  const start = useCallback(async (sessionId: string, token: string, deviceId?: string) => {
    await capture().start(sessionId, token, deviceId)
  }, [])

  const stop = useCallback(() => {
    capture().stop()
  }, [])

  const listDevices = useCallback(() => capture().listDevices(), [])

  return { status, level, ingestStatus, start, stop, listDevices }
}
