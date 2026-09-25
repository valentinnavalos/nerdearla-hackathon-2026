import type {
  AdminSessionsResponse,
  CreateSessionPayload,
  ExportFormat,
  Lang,
  PublicSession,
  Session,
} from "@/types/session"

export class ApiError extends Error {
  status: number
  body: unknown

  constructor(status: number, statusText: string, body: unknown) {
    super(`${status} ${statusText}`)
    this.status = status
    this.body = body
  }
}

async function request<T>(url: string, options?: RequestInit): Promise<T> {
  const res = await fetch(url, options)
  if (!res.ok) {
    let body: unknown = null
    try {
      body = await res.json()
    } catch {
      /* no JSON body */
    }
    throw new ApiError(res.status, res.statusText, body)
  }
  if (res.status === 204) return undefined as T
  return (await res.json()) as T
}

function authHeaders(token: string, extra?: Record<string, string>) {
  return { Authorization: `Bearer ${token}`, ...extra }
}

export function getPublicSessions(): Promise<PublicSession[]> {
  return request("/api/public/sessions")
}

export function getSessions(token: string): Promise<AdminSessionsResponse> {
  return request("/api/sessions", { headers: authHeaders(token) })
}

export function createSession(token: string, payload: CreateSessionPayload): Promise<Session> {
  return request("/api/sessions", {
    method: "POST",
    headers: authHeaders(token, { "Content-Type": "application/json" }),
    body: JSON.stringify(payload),
  })
}

export function startSession(token: string, id: string): Promise<Session> {
  return request(`/api/sessions/${encodeURIComponent(id)}/start`, {
    method: "POST",
    headers: authHeaders(token),
  })
}

export function stopSession(token: string, id: string): Promise<Session> {
  return request(`/api/sessions/${encodeURIComponent(id)}/stop`, {
    method: "POST",
    headers: authHeaders(token),
  })
}

export function deleteSession(token: string, id: string): Promise<{ ok: boolean }> {
  return request(`/api/sessions/${encodeURIComponent(id)}`, {
    method: "DELETE",
    headers: authHeaders(token),
  })
}

export function uploadFile(token: string, file: File): Promise<{ file: string }> {
  const form = new FormData()
  form.append("file", file)
  return request("/api/uploads", { method: "POST", headers: authHeaders(token), body: form })
}

export function getExportUrl(id: string, fmt: ExportFormat, lang: Lang = "es"): string {
  const params = fmt === "md" ? "" : `?lang=${encodeURIComponent(lang)}`
  return `/api/sessions/${encodeURIComponent(id)}/export.${fmt}${params}`
}

export function getNetworkInfo(): Promise<{ lan_ip: string | null }> {
  return request("/api/network-info")
}
