// Operator console (T2.9): thin wrappers around the admin API, all with the Bearer token.

import { fetchJSON, sessionStore } from "./common.js";

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
