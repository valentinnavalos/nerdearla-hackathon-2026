// CaptionView: connects to /ws/captions/{id}?lang= and renders the last lines.
// Reused by the audience page (index.html) and the stage view (stage.html, T2.8).

import { wsUrl } from "./common.js";

const BACKOFF_S = [1, 2, 4, 8, 10];
const MAX_SEGS = 50;

export class CaptionView {
  /**
   * @param {HTMLElement} container where the lines are rendered
   * @param {{lines?: number, onStatus?: (status: string) => void,
   *          onConnection?: (state: string, retryInS?: number) => void}} options
   *   onConnection states: "connecting" | "open" | "reconnecting" | "not_found"
   */
  constructor(container, { lines = 3, onStatus = () => {}, onConnection = () => {} } = {}) {
    this.container = container;
    this.lines = lines;
    this.onStatus = onStatus;
    this.onConnection = onConnection;
    this.segs = new Map(); // seg -> {text, final}; interim and final of a segment share the seg
    this.els = new Map(); // seg -> rendered <p>, reused across renders for smooth updates
    this.ws = null;
    this.attempt = 0;
    this.retryTimer = null;
    this.status = null;
  }

  connect(sessionId, lang) {
    this.disconnect();
    this.sessionId = sessionId;
    this.lang = lang;
    this.segs.clear();
    this.els.clear();
    this.container.replaceChildren();
    this._open();
  }

  disconnect() {
    clearTimeout(this.retryTimer);
    const ws = this.ws;
    this.ws = null;
    if (ws) ws.close();
  }

  _open() {
    const path = `/ws/captions/${encodeURIComponent(this.sessionId)}?lang=${encodeURIComponent(this.lang)}`;
    const ws = new WebSocket(wsUrl(path));
    this.ws = ws;
    this.onConnection("connecting");
    ws.onopen = () => {
      this.attempt = 0;
      this.segs.clear(); // the server resends the history of finals
      this.els.clear();
      this.container.replaceChildren();
      this.onConnection("open");
    };
    ws.onmessage = (e) => this._handle(JSON.parse(e.data));
    ws.onclose = (e) => {
      if (this.ws !== ws) return; // closed on purpose (disconnect / language change)
      this.ws = null;
      if (e.code === 4404) {
        this.onConnection("not_found");
        return;
      }
      const delay = BACKOFF_S[Math.min(this.attempt, BACKOFF_S.length - 1)];
      this.attempt += 1;
      this.onConnection("reconnecting", delay);
      this.retryTimer = setTimeout(() => this._open(), delay * 1000);
    };
  }

  _handle(msg) {
    if (msg.type === "session_status") {
      if (msg.status === "RUNNING" && this.status && this.status !== "RUNNING") {
        this.segs.clear(); // restarted room: segment ids start over
        this.els.clear();
        this.container.replaceChildren();
      }
      this.status = msg.status;
      this.onStatus(msg.status);
      return;
    }
    if (msg.type !== "caption") return;
    const current = this.segs.get(msg.seg);
    if (current && current.final && !msg.final) return; // late interim after its final
    this.segs.set(msg.seg, { text: msg.text, final: msg.final });
    if (this.segs.size > MAX_SEGS) {
      const oldest = [...this.segs.keys()].sort((a, b) => a - b).slice(0, this.segs.size - MAX_SEGS);
      for (const seg of oldest) this.segs.delete(seg);
    }
    this.render();
  }

  render() {
    const segs = [...this.segs.keys()].sort((a, b) => a - b).slice(-this.lines);
    const wanted = new Set(segs);

    // Drop elements for segments no longer shown (scrolled out).
    for (const [seg, el] of this.els ?? (this.els = new Map())) {
      if (!wanted.has(seg)) {
        el.remove();
        this.els.delete(seg);
      }
    }

    let prevEl = null;
    for (const seg of segs) {
      const { text, final } = this.segs.get(seg);
      let el = this.els.get(seg);
      const wasFinal = el ? el.dataset.final === "1" : null;
      if (!el) {
        el = document.createElement("p");
        el.className = "line entering";
        this.container.appendChild(el);
        this.els.set(seg, el);
        // next frame: trigger the enter transition
        requestAnimationFrame(() => el.classList.remove("entering"));
      } else if (prevEl ? el.previousElementSibling !== prevEl : el !== this.container.firstChild) {
        // keep DOM order in sync with seg order (rare: happens after a room restart)
        this.container.insertBefore(el, prevEl ? prevEl.nextSibling : this.container.firstChild);
      }
      el.textContent = text;
      el.dataset.final = final ? "1" : "0";
      el.classList.toggle("interim", !final);
      if (final && wasFinal === false) {
        // brief highlight when a line settles from interim to final
        el.classList.remove("settled");
        void el.offsetWidth; // restart the animation if it was still running
        el.classList.add("settled");
      }
      prevEl = el;
    }
  }
}
