import type { Lang, SessionStatus } from "@/types/session"

export const LANG_LABELS: Record<Lang, string> = { es: "Español", en: "English" }
export const LANG_SHORT: Record<Lang, string> = { es: "ES", en: "EN" }

export const STATUS_LABELS: Record<SessionStatus, string> = {
  CREATED: "Por empezar",
  RUNNING: "En vivo",
  ROTATING: "En vivo",
  RECONNECTING: "Reconectando",
  ERROR: "Con problemas",
  STOPPED: "Terminó",
}

export function statusBadgeVariant(status: SessionStatus): "default" | "secondary" | "destructive" | "outline" {
  if (status === "RUNNING" || status === "ROTATING") return "default"
  if (status === "ERROR") return "destructive"
  if (status === "RECONNECTING") return "secondary"
  return "outline"
}
