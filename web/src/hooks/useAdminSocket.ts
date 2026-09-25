import { useCallback, useState } from "react"
import { wsUrl } from "@/lib/ws"
import type { AdminSnapshot } from "@/types/admin"
import { useReconnectingSocket } from "./useReconnectingSocket"

export function useAdminSocket(token: string | null) {
  const [snapshot, setSnapshot] = useState<AdminSnapshot | null>(null)

  const url = token ? wsUrl(`/ws/admin?token=${encodeURIComponent(token)}`) : null

  const onMessage = useCallback((ev: MessageEvent) => {
    setSnapshot(JSON.parse(ev.data) as AdminSnapshot)
  }, [])

  const { connectionState, lastCloseCode } = useReconnectingSocket({ url, onMessage })

  // 4401 = bad/expired token: the caller should bounce back to the login gate.
  const unauthorized = lastCloseCode === 4401

  return { snapshot, connectionState, unauthorized }
}
