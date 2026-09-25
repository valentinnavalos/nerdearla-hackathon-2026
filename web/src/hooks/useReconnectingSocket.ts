import { useEffect, useRef, useState } from "react"

const DEFAULT_BACKOFF_MS = [1000, 2000, 4000, 8000, 10000]

// Close codes the backend uses for auth/validation failures (backend/api/ws.py):
// retrying these forever would just loop silently, so they end the connection for good.
const TERMINAL_CLOSE_CODES = new Set([4400, 4401, 4404])

export type SocketConnectionState = "connecting" | "open" | "reconnecting" | "closed"

interface UseReconnectingSocketOptions {
  url: string | null // null = don't connect
  binaryType?: BinaryType
  onMessage: (ev: MessageEvent) => void
  onOpen?: () => void
  backoffMs?: number[]
}

interface UseReconnectingSocketResult {
  send: (data: string | ArrayBufferLike | Blob | ArrayBufferView) => void
  connectionState: SocketConnectionState
  lastCloseCode: number | null
}

// Consolidates the reconnect-with-backoff logic duplicated across the old
// captions.js / admin.js / mic.js into one hook, shared by useCaptionSocket,
// useAdminSocket, and useMicCapture's outbound ingest socket.
export function useReconnectingSocket({
  url,
  binaryType,
  onMessage,
  onOpen,
  backoffMs = DEFAULT_BACKOFF_MS,
}: UseReconnectingSocketOptions): UseReconnectingSocketResult {
  const [connectionState, setConnectionState] = useState<SocketConnectionState>("connecting")
  const [lastCloseCode, setLastCloseCode] = useState<number | null>(null)
  const wsRef = useRef<WebSocket | null>(null)
  const attemptRef = useRef(0)
  const retryTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null)
  const onMessageRef = useRef(onMessage)
  const onOpenRef = useRef(onOpen)
  onMessageRef.current = onMessage
  onOpenRef.current = onOpen

  useEffect(() => {
    if (!url) {
      setConnectionState("closed")
      return
    }

    let cancelled = false

    function open() {
      setConnectionState(attemptRef.current === 0 ? "connecting" : "reconnecting")
      const ws = new WebSocket(url!)
      if (binaryType) ws.binaryType = binaryType
      wsRef.current = ws

      ws.onopen = () => {
        attemptRef.current = 0
        setConnectionState("open")
        onOpenRef.current?.()
      }
      ws.onmessage = (ev) => onMessageRef.current(ev)
      ws.onclose = (ev) => {
        if (wsRef.current !== ws || cancelled) return
        wsRef.current = null
        setLastCloseCode(ev.code)
        if (TERMINAL_CLOSE_CODES.has(ev.code)) {
          setConnectionState("closed")
          return
        }
        const delay = backoffMs[Math.min(attemptRef.current, backoffMs.length - 1)]
        attemptRef.current += 1
        setConnectionState("reconnecting")
        retryTimerRef.current = setTimeout(open, delay)
      }
    }

    open()

    return () => {
      cancelled = true
      if (retryTimerRef.current) clearTimeout(retryTimerRef.current)
      const ws = wsRef.current
      wsRef.current = null
      ws?.close()
      attemptRef.current = 0
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [url, binaryType])

  const send = (data: string | ArrayBufferLike | Blob | ArrayBufferView) => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(data as never)
    }
  }

  return { send, connectionState, lastCloseCode }
}
