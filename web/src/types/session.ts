export type Lang = "en" | "es"

export type SessionStatus =
  | "CREATED"
  | "RUNNING"
  | "ROTATING"
  | "RECONNECTING"
  | "ERROR"
  | "STOPPED"

export type SessionSource = "mic" | "file"

// backend/core/session.py KP_STATUSES (null until the post-talk pipeline runs)
export type KpStatus = "pending" | "ready" | "error" | null

// backend/core/session.py Session.public_info()
export interface PublicSession {
  id: string
  title: string
  speaker: string
  source_lang: Lang
  target_lang: Lang
  status: SessionStatus
  kp_status: KpStatus
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

// backend/post/knowledge.py SCHEMA (T3.4)
export interface KeyPoint {
  t: string
  es: string
  en: string
}

export interface QuizQuestion {
  q_es: string
  q_en: string
  options_es: string[]
  options_en: string[]
  answer_idx: number
  explanation_es: string
  explanation_en: string
}

export interface Knowledge {
  summary_es: string
  summary_en: string
  key_points: KeyPoint[]
  terms: string[]
  quiz: QuizQuestion[]
}

// backend/api/sessions.py GET /api/sessions/{id}/knowledge
export interface KnowledgeResponse {
  kp_status: KpStatus
  knowledge: Knowledge | null
  notebooklm_url: string | null
}

// backend/api/sessions.py POST /api/sessions/{id}/ask (T3.6)
export interface AskResponse {
  answer: string
  cached: boolean
}
