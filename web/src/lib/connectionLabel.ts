import type { SessionStatus } from "@/types/session"
import { STATUS_LABELS } from "./constants"
import type { SocketConnectionState } from "@/hooks/useReconnectingSocket"

export function connectionLabel(
  connectionState: SocketConnectionState,
  status: SessionStatus | null,
  closedIsNotFound: boolean,
): string {
  if (connectionState === "connecting") return "conectando…"
  if (connectionState === "reconnecting") return "reconectando…"
  if (connectionState === "closed") return closedIsNotFound ? "Sala no encontrada" : ""
  // open
  if (status && status !== "RUNNING") return STATUS_LABELS[status]
  return "● en vivo"
}
