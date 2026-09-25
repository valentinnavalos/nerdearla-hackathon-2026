// Operator console (T2.9): thin wrappers around the admin API, all with the Bearer token.

import { fetchJSON, sessionStore, wsUrl } from "./common.js";

const TOKEN_KEY = "admin.token";

export function getToken() {
  return sessionStore.get(TOKEN_KEY, "");
}

export function setToken(token) {
  sessionStore.set(TOKEN_KEY, token);
}

function authHeaders(extra = {}) {
  return { Authorization: `Bearer ${getToken()}`, ...extra };
}

export async function listSessions() {
  return fetchJSON("/api/sessions", { headers: authHeaders() });
}

export async function createSession(payload) {
  return fetchJSON("/api/sessions", {
    method: "POST",
    headers: authHeaders({ "Content-Type": "application/json" }),
    body: JSON.stringify(payload),
  });
}

export async function startSession(id) {
  return fetchJSON(`/api/sessions/${encodeURIComponent(id)}/start`, { method: "POST", headers: authHeaders() });
}

export async function stopSession(id) {
  return fetchJSON(`/api/sessions/${encodeURIComponent(id)}/stop`, { method: "POST", headers: authHeaders() });
}

export async function deleteSession(id) {
  return fetchJSON(`/api/sessions/${encodeURIComponent(id)}`, { method: "DELETE", headers: authHeaders() });
}

export async function uploadFile(file) {
  const form = new FormData();
  form.append("file", file);
  return fetchJSON("/api/uploads", { method: "POST", headers: authHeaders(), body: form });
}

// --- monitoring panel (T3.2) -----------------------------------------------------

const ADMIN_WS_BACKOFF = [1000, 2000, 4000, 8000, 10000];

// Opens /ws/admin (state snapshot every 1s) and calls onSnapshot(data) on every message,
// reconnecting with backoff if the socket drops. Returns a function that closes it for good.
export function openAdminSocket(onSnapshot) {
  let closed = false;
  let attempt = 0;
  let ws = null;

  function connect() {
    if (closed) return;
    ws = new WebSocket(wsUrl(`/ws/admin?token=${encodeURIComponent(getToken())}`));
    ws.onmessage = (e) => {
      attempt = 0;
      onSnapshot(JSON.parse(e.data));
    };
    ws.onclose = () => {
      if (closed) return;
      const delay = ADMIN_WS_BACKOFF[Math.min(attempt, ADMIN_WS_BACKOFF.length - 1)];
      attempt += 1;
      setTimeout(connect, delay);
    };
    ws.onerror = () => ws.close();
  }
  connect();

  return () => {
    closed = true;
    if (ws) ws.close();
  };
}
