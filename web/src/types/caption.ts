import type { Lang, SessionStatus } from "./session"

// backend/core/events.py CaptionEvent, as sent over /ws/captions/{id}
export interface CaptionEventMessage {
  type: "caption"
  session_id: string
  lang: Lang
  kind: "orig" | "trans"
  seg: number
  final: boolean
  text: string
  t0: number
  t1: number
  lat_ms?: number | null
}

export interface SessionStatusMessage {
  type: "session_status"
  session_id: string
  status: SessionStatus
}

export type CaptionSocketMessage = CaptionEventMessage | SessionStatusMessage

// UI-facing view of one segment, keyed by `seg` (interim and final share the id)
export interface CaptionSegment {
  seg: number
  text: string
  final: boolean
}
