// Shared helpers for every page (no build step: plain ES modules).

export const LANG_LABELS = { es: "Español", en: "English" };

export const STATUS_LABELS = {
  CREATED: "Por empezar",
  RUNNING: "En vivo",
  ROTATING: "En vivo",
  RECONNECTING: "Reconectando",
  ERROR: "Con problemas",
  STOPPED: "Terminó",
};

export function qs(name) {
  return new URLSearchParams(location.search).get(name);
}

export function wsUrl(path) {
  const proto = location.protocol === "https:" ? "wss:" : "ws:";
  return `${proto}//${location.host}${path}`;
}

export async function fetchJSON(url, options) {
  const res = await fetch(url, options);
  if (!res.ok) throw new Error(`${res.status} ${res.statusText}`);
  return res.json();
}

// localStorage can throw (private mode, blocked storage): it only holds per-viewer conveniences.
export const storage = {
  get(key, fallback) {
    try {
      const value = localStorage.getItem(key);
      return value === null ? fallback : JSON.parse(value);
    } catch {
      return fallback;
    }
  },
  set(key, value) {
    try {
      localStorage.setItem(key, JSON.stringify(value));
    } catch {
      /* ignore */
    }
  },
};

// Same shape as `storage`, but sessionStorage (the admin token must not survive
// the browser tab closing).
export const sessionStore = {
  get(key, fallback) {
    try {
      const value = sessionStorage.getItem(key);
      return value === null ? fallback : JSON.parse(value);
    } catch {
      return fallback;
    }
  },
  set(key, value) {
    try {
      sessionStorage.setItem(key, JSON.stringify(value));
    } catch {
      /* ignore */
    }
  },
};

const LANG_SHORT = { es: "ES", en: "EN" };

// The translation direction is fixed for the whole session (backend never
// re-derives target_lang once the Session is created), so this is a
// read-only badge, distinct from the interactive .lang-toggle.
export function renderDirectionBadge(sourceLang, targetLang) {
  const source = LANG_SHORT[sourceLang] ?? sourceLang;
  const target = LANG_SHORT[targetLang] ?? targetLang;
  return el(
    "span",
    { class: "badge badge-direction", title: "Dirección fija de la sesión: no se puede cambiar" },
    document.createTextNode(`${source} → ${target} 🔒`)
  );
}

export function el(tag, attrs = {}, ...children) {
  const node = document.createElement(tag);
  for (const [key, value] of Object.entries(attrs)) {
    if (key === "class") node.className = value;
    else if (key === "dataset") Object.assign(node.dataset, value);
    else node.setAttribute(key, value);
  }
  node.append(...children);
  return node;
}
