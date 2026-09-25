export type Lang = "en" | "es"

export type SessionStatus =
  | "CREATED"
  | "RUNNING"
  | "ROTATING"
  | "RECONNECTING"
  | "ERROR"
  | "STOPPED"

export type SessionSource = "mic" | "file"

// backend/core/session.py Session.public_info()
export interface PublicSession {
  id: string
  title: string
  speaker: string
  source_lang: Lang
  target_lang: Lang
  status: SessionStatus
}

// backend/core/session.py Session.info()
export interface Session extends PublicSession {
  source: SessionSource
  file: string | null
  loop: boolean
  started_at: number | null
  stopped_at: number | null
  last_error: string | null
  uptime_s: number | null
  mic_connected: boolean | null
  metrics: SessionMetrics
}

export interface LatencyBucket {
  p50?: number | null
  p95?: number | null
}

export interface AudioMetrics {
  final_latency_ms?: LatencyBucket | null
  silence_alert?: boolean
  last_frame_age_s?: number | null
  [key: string]: unknown
}

export interface RunnerStats {
  state?: string
  rotations?: number
  reconnects?: number
  errors?: number
  [key: string]: unknown
}

export interface SessionMetrics {
  events: number
  dropped_frames: number
  listeners: Partial<Record<Lang, number>>
  captions_written: number
  write_errors: number
  runner: RunnerStats | null
  audio: AudioMetrics | null
}

export interface LiveUsage {
  used: number
  max: number
}

export interface Quota {
  used: number
  limit: number
}

// backend/api/sessions.py GET /api/sessions
export interface AdminSessionsResponse {
  sessions: Session[]
  live_usage: LiveUsage
  quota: Quota
}

// backend/api/sessions.py CreateSessionBody
export interface CreateSessionPayload {
  title: string
  speaker?: string
  source_lang: Lang
  source: SessionSource
  file?: string | null
  loop?: boolean
  glossary_text?: string | null
}

export type ExportFormat = "srt" | "vtt" | "txt" | "md"
