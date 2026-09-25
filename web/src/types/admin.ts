import type { LiveUsage, Quota, Session } from "./session"

// backend/api/ws.py WS /ws/admin snapshot, every 1s
export interface AdminSnapshot {
  type: "admin_snapshot"
  sessions: Session[]
  live_usage: LiveUsage
  quota: Quota
}

// backend/api/ws.py WS /ws/ingest status messages
export interface IngestStatusMessage {
  type: "ingest_status"
  status: string
  mic_connected: boolean
  lat_p50_ms: number | null
}
