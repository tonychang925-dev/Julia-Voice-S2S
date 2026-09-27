// @ts-check
/**
 * AudioWorkletProcessor that plays back Float32 mono samples received from
 * the main thread, upsampling whatever incoming rate the server uses
 * (typically 24 kHz PCM16) to the AudioContext rate (typically 48 kHz).
 *
 * Lifecycle / messaging:
 *
 *   main -> worklet:
 *     { kind: "config", inputRate: 24000 }              one-shot at startup
 *     { kind: "audio", samples: Float32Array }          (transferable) per chunk
 *     { kind: "clear" }                                 wipe queue (barge-in)
 *
 *   worklet -> main:
 *     { kind: "stats", queuedMs, played }               every ~250 ms
 *     { kind: "underrun" }                              every time the queue
 *                                                      runs dry mid-playback
 *
 * Underrun strategy: output silence. We do NOT hold the last sample (that
 * tends to produce audible clicks/buzzes when long gaps appear between
 * TTS chunks). A short ramp-out + ramp-in at boundaries would be nicer but
 * the server's 30 ms cadence makes underruns visible only at end of turn.
 */

const STATS_INTERVAL_FRAMES = 12000;
const FADE_FRAMES = 32;

class AudioPlaybackProcessor extends AudioWorkletProcessor {
  constructor() {
    super();
    this._inputRate = 24000;
    this._stepRatio = this._inputRate / sampleRate;
    this._queue = [];
    this._readIdx = 0;
    this._fracPos = 0;
    this._playing = false;
    this._framesSinceStats = 0;
    this._totalPlayed = 0;
    this._fadeIn = 0;
    this._fadeOut = 0;
    this._lastSample = 0;
    this._responseBeginPending = false;
    this._responseEnded = false;
    this._completionReported = false;
    this._underrunReported = false;
    this._responseQueuedSamples = 0;
    this._responsePlayedSamples = 0;
    this._responseDroppedSamples = 0;
    this._queueResetCount = 0;

    this.port.onmessage = (e) => {
      const data = e.data;
      if (!data || typeof data !== "object") return;
      switch (data.kind) {
        case "config":
          if (typeof data.inputRate === "number" && data.inputRate > 0) {
            this._inputRate = data.inputRate;
            this._stepRatio = this._inputRate / sampleRate;
          }
          break;
        case "response-begin":
          this._responseQueuedSamples = 0;
          this._responsePlayedSamples = 0;
          this._responseDroppedSamples = 0;
          this._responseBeginPending = true;
          this._responseEnded = false;
          this._completionReported = false;
          this._underrunReported = false;
          break;
        case "response-end":
          this._responseEnded = true;
          if (this._queuedSamples() === 0) {
            this._playing = false;
            this._lastSample = 0;
            this._fadeOut = 0;
            this._completionReported = true;
            this.port.postMessage({
              kind: "playback-complete",
              queuedMs: 0,
              queuedByteCount: this._responseQueuedSamples * 2,
              playedByteCount: this._responsePlayedSamples * 2,
              queueResetCount: this._queueResetCount,
            });
          }
          break;
        case "audio":
          if (ArrayBuffer.isView(data.samples) && data.samples.length > 0) {
            this._queue.push(data.samples);
            this._responseQueuedSamples += data.samples.length;
            this._underrunReported = false;
            this._maybeStartPlayback();
          }
          break;
        case "clear": {
          const droppedSamples = this._queuedSamples();
          this._queueResetCount += 1;
          this._queue.length = 0;
          this._readIdx = 0;
          this._fracPos = 0;
          this._responseBeginPending = false;
          this._responseEnded = false;
          this._completionReported = true;
          this._underrunReported = false;
          if (this._playing || droppedSamples > 0) {
            this.port.postMessage({
              kind: "playback-stopped",
              reason: typeof data.reason === "string" ? data.reason : "clear",
              queuedByteCount: droppedSamples * 2,
              playedByteCount: this._responsePlayedSamples * 2,
              queueResetCount: this._queueResetCount,
            });
          }
          this._responseDroppedSamples += droppedSamples;
          this.port.postMessage({
            kind: "queue-reset",
            reason: typeof data.reason === "string" ? data.reason : "clear",
            droppedByteCount: droppedSamples * 2,
            playedByteCount: this._responsePlayedSamples * 2,
            queueResetCount: this._queueResetCount,
          });
          this._playing = false;
          this._lastSample = 0;
          this._fadeOut = 0;
          break;
        }
      }
    };
  }

  _queuedSamples() {
    let total = -this._readIdx;
    for (const buf of this._queue) total += buf.length;
    return Math.max(0, total);
  }

  _maybeStartPlayback() {
    if (this._playing) return;
    if (this._queue.length === 0) return;
    const queuedMs = (this._queuedSamples() / this._inputRate) * 1000;
    this._playing = true;
    this._responseBeginPending = false;
    this._fadeIn = FADE_FRAMES;
    this._fadeOut = 0;
    this.port.postMessage({
      kind: "playback-started",
      queuedMs,
      queuedByteCount: this._responseQueuedSamples * 2,
    });
  }

  /** Linear-interp read at the current fractional position. */
  _readInterpolated() {
    if (this._queue.length === 0) return null;
    const head = this._queue[0];
    const idx = this._readIdx;
    const frac = this._fracPos;

    let a = head[idx];
    let b;
    if (idx + 1 < head.length) {
      b = head[idx + 1];
    } else if (this._queue.length > 1) {
      b = this._queue[1][0];
    } else {
      b = a;
    }
    return a + (b - a) * frac;
  }

  /** Advance the read position by `stepRatio`; pop consumed buffers. */
  _advance() {
    this._fracPos += this._stepRatio;
    while (this._fracPos >= 1) {
      this._fracPos -= 1;
      this._readIdx += 1;
    }
    while (this._queue.length > 0 && this._readIdx >= this._queue[0].length) {
      this._readIdx -= this._queue[0].length;
      this._queue.shift();
    }
  }

  process(_, outputs) {
    const channels = outputs[0];
    if (!channels || channels.length === 0) return true;
    const out = channels[0];
    const stereo = channels.length > 1 ? channels[1] : null;

    for (let i = 0; i < out.length; i++) {
      let sample = 0;

      if (this._playing) {
        const v = this._readInterpolated();
        if (v === null) {
          const queuedMs = (this._queuedSamples() / this._inputRate) * 1000;
          if (this._responseEnded && !this._completionReported) {
            this._completionReported = true;
            this.port.postMessage({
              kind: "playback-complete",
              queuedMs,
              queuedByteCount: Math.round(this._responseQueuedSamples * 2),
              playedByteCount: Math.round(this._responsePlayedSamples * 2),
              droppedByteCount: Math.round(this._responseDroppedSamples * 2),
              queueResetCount: this._queueResetCount,
            });
          } else if (!this._responseEnded && !this._underrunReported) {
            this._underrunReported = true;
            this.port.postMessage({
              kind: "underrun",
              queuedMs,
              queuedByteCount: Math.round(this._responseQueuedSamples * 2),
              playedByteCount: Math.round(this._responsePlayedSamples * 2),
              droppedByteCount: Math.round(this._responseDroppedSamples * 2),
            });
          }
          // Underrun: try to ramp out cleanly to avoid clicks.
          sample = this._lastSample * Math.max(0, 1 - 1 / FADE_FRAMES);
          this._lastSample = sample;
          if (Math.abs(sample) < 1e-4) {
            this._playing = false;
            this._lastSample = 0;
          }
        } else {
          sample = v;
          this._lastSample = v;
          this._advance();
          this._responsePlayedSamples += this._stepRatio;
        }

        if (this._fadeIn > 0) {
          const gain = 1 - this._fadeIn / FADE_FRAMES;
          sample *= gain;
          this._fadeIn -= 1;
        }
        if (this._fadeOut > 0) {
          const gain = this._fadeOut / FADE_FRAMES;
          sample *= gain;
          this._fadeOut -= 1;
          if (this._fadeOut === 0) {
            this._playing = false;
            this._lastSample = 0;
          }
        }

        this._totalPlayed += 1;
      }

      out[i] = sample;
      if (stereo) stereo[i] = sample;
    }

    this._framesSinceStats += out.length;
    if (this._framesSinceStats >= STATS_INTERVAL_FRAMES) {
      this._framesSinceStats = 0;
      const queuedSamples = this._queuedSamples();
      const queuedMs = (queuedSamples / this._inputRate) * 1000;
      this.port.postMessage({
        kind: "stats",
        queuedMs,
        played: this._totalPlayed,
        responseQueuedByteCount: Math.round(this._responseQueuedSamples * 2),
        responsePlayedByteCount: Math.round(this._responsePlayedSamples * 2),
        responseDroppedByteCount: Math.round(this._responseDroppedSamples * 2),
        queueResetCount: this._queueResetCount,
      });
    }

    if (
      this._responseEnded
      && !this._completionReported
      && !this._playing
      && this._queuedSamples() === 0
    ) {
      this._completionReported = true;
      this.port.postMessage({
        kind: "playback-complete",
        queuedMs: 0,
        queuedByteCount: Math.round(this._responseQueuedSamples * 2),
        playedByteCount: Math.round(this._responsePlayedSamples * 2),
        droppedByteCount: Math.round(this._responseDroppedSamples * 2),
        queueResetCount: this._queueResetCount,
      });
    }

    return true;
  }
}

registerProcessor("audio-playback", AudioPlaybackProcessor);
