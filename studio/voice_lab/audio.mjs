export function encodeWav(samples, rate = 24000) {
  const bytes = new ArrayBuffer(44 + samples.length * 2), view = new DataView(bytes);
  const text = (at, s) => Array.from(s).forEach((ch, i) => view.setUint8(at + i, ch.charCodeAt(0)));
  text(0, 'RIFF'); view.setUint32(4, 36 + samples.length * 2, true); text(8, 'WAVE');
  text(12, 'fmt '); view.setUint32(16, 16, true); view.setUint16(20, 1, true); view.setUint16(22, 1, true);
  view.setUint32(24, rate, true); view.setUint32(28, rate * 2, true); view.setUint16(32, 2, true); view.setUint16(34, 16, true);
  text(36, 'data'); view.setUint32(40, samples.length * 2, true);
  samples.forEach((s, i) => { const n = Math.max(-1, Math.min(1, Number.isFinite(s) ? s : 0)); view.setInt16(44 + 2 * i, n * (n < 0 ? 32768 : 32767), true); });
  return new Blob([bytes], { type: 'audio/wav' });
}

export async function toWav(blob) {
  if (!blob || !blob.size || blob.size > 25_000_000) throw new Error('请选择不超过 25 MB 的录音。');
  const Context = window.AudioContext || window.webkitAudioContext;
  const context = new Context();
  try {
    const audio = await context.decodeAudioData(await blob.arrayBuffer());
    if (audio.duration < 1 || audio.duration > 45) throw new Error('请使用 1–45 秒的录音。');
    const offline = new OfflineAudioContext(1, Math.ceil(audio.duration * 24000), 24000);
    const source = offline.createBufferSource(); source.buffer = audio; source.connect(offline.destination); source.start();
    const mono = await offline.startRendering();
    return encodeWav(mono.getChannelData(0));
  } finally { await context.close(); }
}

export class Recorder {
  async start(onLevel) {
    if (!navigator.mediaDevices?.getUserMedia || !window.MediaRecorder) throw new Error('这个浏览器不能录音，请使用 Chrome，或导入自己的录音。');
    try {
      this.stream = await navigator.mediaDevices.getUserMedia({ audio: { echoCancellation: true, noiseSuppression: true } });
      this.chunks = [];
      const recorder = this.recorder = new MediaRecorder(this.stream);
      recorder.addEventListener('dataavailable', e => {
        if (this.recorder === recorder && e.data.size) this.chunks.push(e.data);
      });
      const Context = window.AudioContext || window.webkitAudioContext;
      this.context = new Context();
      this.source = this.context.createMediaStreamSource(this.stream);
      this.analyser = this.context.createAnalyser(); this.analyser.fftSize = 256;
      this.source.connect(this.analyser);
      const values = new Uint8Array(256);
      this.levelTimer = setInterval(() => {
        this.analyser.getByteTimeDomainData(values);
        onLevel(Math.min(1, Math.sqrt(values.reduce((sum, n) => sum + ((n - 128) / 128) ** 2, 0) / values.length) * 5));
      }, 80);
      this.recorder.start();
    } catch (error) { this.release(); throw error; }
  }
  async stop() {
    const recorder = this.recorder;
    if (!recorder || recorder.state === 'inactive') return null;
    try {
      const blob = await new Promise((resolve, reject) => {
        recorder.addEventListener('stop', () => resolve(new Blob(this.chunks, { type: recorder.mimeType })), { once: true });
        recorder.addEventListener('error', () => reject(new Error('录音中断，请重试。')), { once: true });
        recorder.stop();
      });
      this.release();
      return await toWav(blob);
    } finally { this.release(); }
  }
  release() {
    clearInterval(this.levelTimer);
    if (this.recorder?.state === 'recording') this.recorder.stop();
    this.stream?.getTracks().forEach(track => track.stop());
    if (this.context && this.context.state !== 'closed') this.context.close().catch(() => {});
    this.recorder = null; this.stream = null; this.chunks = []; this.context = null;
  }
}
