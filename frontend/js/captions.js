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
    this.render();
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
        this.render();
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
    this.container.replaceChildren(
      ...segs.map((seg) => {
        const { text, final } = this.segs.get(seg);
        const p = document.createElement("p");
        p.className = final ? "line" : "line interim";
        p.textContent = text;
        return p;
      }),
    );
  }
}
