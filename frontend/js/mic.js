// MicCapture: captures the mic, resamples to 16kHz PCM16 via an AudioWorklet, and
// streams 100ms frames over /ws/ingest/{id}?token= (T2.7). Used by the stage view (T2.8).

import { wsUrl } from "./common.js";

const BACKOFF_S = [1, 2, 4, 8, 10];
const BUFFER_WHILE_DISCONNECTED = 30; // 3s of frames

export class MicCapture {
  /**
   * @param {{onLevel?: (dbfs: number) => void, onStatus?: (state: string) => void,
   *          onIngestStatus?: (msg: object) => void}} options
   *   onStatus states: "idle" | "starting" | "capturing" | "stopped" | "error"
   */
  constructor({ onLevel = () => {}, onStatus = () => {}, onIngestStatus = () => {} } = {}) {
    this.onLevel = onLevel;
    this.onStatus = onStatus;
    this.onIngestStatus = onIngestStatus;
    this.stream = null;
    this.ctx = null;
    this.node = null;
    this.ws = null;
    this.attempt = 0;
    this.retryTimer = null;
    this.buffer = [];
    this.wakeLock = null;
    this.sessionId = null;
    this.token = null;
    this.stopped = true;
  }

  async listDevices() {
    const devices = await navigator.mediaDevices.enumerateDevices();
    return devices.filter((d) => d.kind === "audioinput");
  }

  /** Must be called from inside a click handler (browsers require a user gesture
   * before letting a page open an AudioContext / use the mic). */
  async start(sessionId, token, deviceId) {
    this.stop();
    this.stopped = false;
    this.sessionId = sessionId;
    this.token = token;
    this.onStatus("starting");
    try {
      // create the AudioContext synchronously-ish, before other awaits eat the user gesture
      this.ctx = new AudioContext();
      this.stream = await navigator.mediaDevices.getUserMedia({
        audio: {
          deviceId: deviceId ? { exact: deviceId } : undefined,
          channelCount: 1,
          echoCancellation: false,
          noiseSuppression: false,
          autoGainControl: false,
        },
      });
      await this.ctx.audioWorklet.addModule("./js/pcm-worklet.js");
      this.node = new AudioWorkletNode(this.ctx, "pcm-worklet");
      this.node.port.onmessage = (e) => this._onWorkletMessage(e.data);
      this.ctx.createMediaStreamSource(this.stream).connect(this.node);
      this._openWs();
      try {
        this.wakeLock = await navigator.wakeLock?.request("screen");
      } catch {
        /* not fatal: screen may just dim */
      }
      this.onStatus("capturing");
    } catch (err) {
      this.onStatus("error");
      this.stop();
      throw err;
    }
  }

  stop(finalStatus = "stopped") {
    this.stopped = true;
    clearTimeout(this.retryTimer);
    if (this.ws) {
      const ws = this.ws;
      this.ws = null;
      ws.close();
    }
    if (this.node) {
      this.node.port.onmessage = null;
      this.node.disconnect();
      this.node = null;
    }
    if (this.stream) {
      for (const track of this.stream.getTracks()) track.stop();
      this.stream = null;
    }
    if (this.ctx) {
      this.ctx.close().catch(() => {});
      this.ctx = null;
    }
    if (this.wakeLock) {
      this.wakeLock.release().catch(() => {});
      this.wakeLock = null;
    }
    this.buffer.length = 0;
    this.onStatus(finalStatus);
  }

  _onWorkletMessage(msg) {
    if (msg.type === "level") {
      this.onLevel(msg.dbfs);
    } else if (msg.type === "frame") {
      this._send(msg.buffer);
    }
  }

  _send(buffer) {
    if (this.ws && this.ws.readyState === WebSocket.OPEN) {
      this.ws.send(buffer);
    } else {
      this.buffer.push(buffer);
      if (this.buffer.length > BUFFER_WHILE_DISCONNECTED) this.buffer.shift();
    }
  }

  _openWs() {
    if (this.stopped) return;
    const path = `/ws/ingest/${encodeURIComponent(this.sessionId)}?token=${encodeURIComponent(this.token)}`;
    const ws = new WebSocket(wsUrl(path));
    ws.binaryType = "arraybuffer";
    this.ws = ws;
    ws.onopen = () => {
      this.attempt = 0;
      while (this.buffer.length) ws.send(this.buffer.shift());
    };
    ws.onmessage = (e) => {
      try {
        this.onIngestStatus(JSON.parse(e.data));
      } catch {
        /* ignore malformed status messages */
      }
    };
    ws.onclose = (e) => {
      if (this.ws !== ws || this.stopped) return;
      this.ws = null;
      if (e.code === 4404) {
        // the room doesn't exist or was never started (session._mic_source is only created
        // by POST /start): retrying forever would just loop silently, so surface it instead.
        this.stop("error");
        return;
      }
      const delay = BACKOFF_S[Math.min(this.attempt, BACKOFF_S.length - 1)];
      this.attempt += 1;
      this.retryTimer = setTimeout(() => this._openWs(), delay * 1000);
    };
  }
}
