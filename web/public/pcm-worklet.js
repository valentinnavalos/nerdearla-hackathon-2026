// AudioWorkletProcessor: resamples the mic's native rate to 16 kHz (linear interpolation,
// works in any browser without depending on AudioContext({sampleRate}) being honored),
// and posts 100 ms (1600-sample) PCM16 LE chunks to the main thread. Also posts a
// level (RMS, dBFS) message a few times a second for the mic meter.

const TARGET_RATE = 16000;
const FRAME_SAMPLES = 1600; // 100 ms @ 16kHz
const LEVEL_INTERVAL_SAMPLES = 4800; // ~0.3s @ 16kHz

class PcmWorklet extends AudioWorkletProcessor {
  constructor() {
    super();
    this.ratio = sampleRate / TARGET_RATE; // native samples consumed per output sample
    this.srcPos = 0; // fractional position in the current input block, in native samples
    this.pending = []; // Int16 samples not yet flushed as a 100ms frame
    this.sinceLevel = 0;
    this.levelSumSq = 0;
    this.levelCount = 0;
  }

  process(inputs) {
    const input = inputs[0];
    const channel = input && input[0];
    if (!channel || channel.length === 0) return true;

    let pos = this.srcPos;
    while (pos < channel.length) {
      const i0 = Math.floor(pos);
      const i1 = Math.min(i0 + 1, channel.length - 1);
      const frac = pos - i0;
      const sample = channel[i0] * (1 - frac) + channel[i1] * frac;
      const clamped = Math.max(-1, Math.min(1, sample));
      const int16 = clamped < 0 ? clamped * 0x8000 : clamped * 0x7fff;
      this.pending.push(int16 | 0);

      this.levelSumSq += sample * sample;
      this.levelCount += 1;
      this.sinceLevel += 1;
      if (this.sinceLevel >= LEVEL_INTERVAL_SAMPLES) {
        this._postLevel();
      }
      if (this.pending.length >= FRAME_SAMPLES) {
        this._flush();
      }
      pos += this.ratio;
    }
    this.srcPos = pos - channel.length;
    return true;
  }

  _flush() {
    const chunk = this.pending.splice(0, FRAME_SAMPLES);
    const buf = new ArrayBuffer(chunk.length * 2);
    const view = new DataView(buf);
    for (let i = 0; i < chunk.length; i++) view.setInt16(i * 2, chunk[i], true);
    this.port.postMessage({ type: "frame", buffer: buf }, [buf]);
  }

  _postLevel() {
    const mean = this.levelCount > 0 ? this.levelSumSq / this.levelCount : 0;
    const dbfs = mean > 0 ? 10 * Math.log10(mean) : -120;
    this.port.postMessage({ type: "level", dbfs });
    this.sinceLevel = 0;
    this.levelSumSq = 0;
    this.levelCount = 0;
  }
}

registerProcessor("pcm-worklet", PcmWorklet);
