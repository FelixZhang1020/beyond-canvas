import { QuestionVoice } from './question-voice.mjs';
import { encodeWav } from './audio.mjs';

export async function* voiceEvents(response) {
  if (!response.body) throw new Error('浏览器没有收到声音，请重试。');
  const reader = response.body.getReader(), decoder = new TextDecoder();
  let pending = '';
  try {
    while (true) {
      const { value, done } = await reader.read();
      pending += decoder.decode(value, { stream: !done });
      if (pending.length > 2_000_000) throw new Error('声音数据异常，请重试。');
      let at;
      while ((at = pending.indexOf('\n')) >= 0) {
        const line = pending.slice(0, at); pending = pending.slice(at + 1);
        if (line.trim()) yield JSON.parse(line);
      }
      if (done) {
        if (pending.trim()) throw new Error('声音没有传输完整，请重试。');
        return;
      }
    }
  } finally {
    await reader.cancel().catch(() => {});
    reader.releaseLock();
  }
}

export class StreamingQuestionVoice extends QuestionVoice {
  constructor(audio, load, update, urls = URL, contextFactory = () => {
    const Context = window.AudioContext || window.webkitAudioContext;
    return new Context();
  }) {
    super(audio, load, update, urls);
    this.contextFactory = contextFactory;
    this.sources = new Set();
    this.ready = new Map(); this.preparing = new Set();
  }

  // Fetched before it is asked for; play() then runs it at once through the same Web Audio path (keep: false, server only).
  async prepare(questionId, voiceId = '', { keep = true, ...options } = {}) {
    const key = JSON.stringify([questionId, voiceId]);
    if (this.cache.has(key) || this.ready.has(key) || this.preparing.has(key)) return;
    this.preparing.add(key);
    try {
      const events = [];
      for await (const event of voiceEvents(await this.load(questionId, voiceId, options))) {
        if (event.type === 'error') return;
        if (event.type !== 'heartbeat') events.push(event);
      }
      if (keep && events.at(-1)?.type === 'done') {
        this.ready.set(key, events);
        while (this.ready.size > 6) this.ready.delete(this.ready.keys().next().value);
      }
    } catch (_) {   // not prepared: made when it is asked for
    } finally {
      this.preparing.delete(key);
    }
  }

  stop() {
    super.stop();
    this.stopStream();
  }

  stopStream() {
    ++this.version;
    this.controller?.abort(); this.controller = null;
    for (const source of this.sources) { try { source.stop(); } catch (_) {} source.disconnect(); }
    this.sources.clear();
    this.update({ streaming: false });
  }

  clear() {
    super.clear();
    this.ready.clear();
    const context = this.context; this.context = null;
    if (context) void context.close().catch(() => {});
  }

  async play(questionId, voiceId = '', voiceName = '对话伙伴') {
    const key = JSON.stringify([questionId, voiceId]);
    if (this.cache.has(key)) return super.play(questionId, voiceId, voiceName);
    this.stop(); this.clearSource();
    const ready = this.ready.get(key); this.ready.delete(key);
    const version = this.version, started = performance.now();
    const controller = new AbortController(); this.controller = controller;
    this.update({ loading: true, streaming: true, firstPlaySeconds: null, text: `${voiceName}正在准备声音…`, failed: false });
    let canPlay = false, firstPlay = null, tail = 0, finished = false, rate = 0, total = 0;
    // One kind per stream: raw sound and MP3 are scheduled at different rates, so a mixed stream
    // would play at the wrong speed; it is refused instead (review).
    let kind = null;
    const chunks = [], waiting = [];
    let waitingSamples = 0;
    // Resume within the initiating click, before the first network await.
    let resume;
    try {
      this.context ||= this.contextFactory();
      resume = this.context.resume().then(() => { canPlay = this.context?.state === 'running'; }, () => {});
    } catch (_) { resume = Promise.resolve(); }
    const completePlayback = () => {
      if (version === this.version && finished && this.sources.size === 0) {
        this.audio.hidden = !this.audio.src;
        this.update({ streaming: false, ended: true, text: '朗读完了。可以回答，也可以重听。' });
      }
    };
    const schedule = (force = false) => {
      if (this.bufferedPlayback || !canPlay || !waiting.length || (!force && firstPlay === null && waitingSamples < rate * .32)) return;
      const context = this.context;
      for (const data of waiting.splice(0)) {
        const buffer = context.createBuffer(1, data.length, rate);
        buffer.copyToChannel(data, 0);
        const source = context.createBufferSource(); source.buffer = buffer; source.connect(context.destination);
        tail = Math.max(tail, context.currentTime + .03);
        source.onended = () => { this.sources.delete(source); source.disconnect(); completePlayback(); };
        this.sources.add(source); source.start(tail); tail += buffer.duration;
      }
      waitingSamples = 0;
      if (firstPlay === null) {
        firstPlay = (performance.now() - started) / 1000;
        this.update({ loading: false, firstPlaySeconds: firstPlay, text: `正在朗读 · 起播等待约 ${firstPlay.toFixed(1)} 秒`, failed: false });
      }
    };
    try {
      await resume;
      if (version !== this.version) return;
      const events = ready || voiceEvents(await this.load(questionId, voiceId, { signal: controller.signal }));
      if (version !== this.version) return;
      for await (const event of events) {
        if (version !== this.version) return;
        if (event.type === 'error') throw new Error(event.error || '声音生成中断，请重试。');
        if (event.type === 'format') {
          if (rate || ![16000, 24000, 44100, 48000].includes(event.sample_rate)) throw new Error('声音格式不受支持。');
          rate = event.sample_rate;
        } else if (event.type === 'pcm') {
          if (kind === 'mp3') throw new Error('声音数据异常。');
          kind = 'pcm';
          if (!rate || finished || typeof event.data !== 'string') throw new Error('声音数据异常。');
          const raw = atob(event.data);
          if (!raw.length || raw.length % 2) throw new Error('声音数据不完整。');
          const bytes = Uint8Array.from(raw, c => c.charCodeAt(0)), view = new DataView(bytes.buffer);
          const data = new Float32Array(bytes.length / 2);
          for (let i = 0; i < data.length; ++i) data[i] = view.getInt16(i * 2, true) / 32768;
          total += data.length;
          if (total > rate * 120) throw new Error('声音过长，请缩短文字后重试。');
          chunks.push(data); waiting.push(data); waitingSamples += data.length; schedule();
          if (this.bufferedPlayback) this.update({ loading: true, preparedSeconds: total / rate });
        } else if (event.type === 'mp3') {
          if (kind === 'pcm') throw new Error('声音数据异常。');
          kind = 'mp3';
          // One whole sentence, compressed (raw sound outran a 29 KB/s relay and played
          // in bursts). It plays only once all of it is here, so a slow link delays the next sentence
          // instead of cutting this one. Decoding resamples to the player's own rate, which becomes
          // the rate everything after it is scheduled and saved at.
          if (!rate || finished || typeof event.data !== 'string' || !this.context) throw new Error('声音数据异常。');
          const raw = atob(event.data);
          let decoded;
          try { decoded = await this.context.decodeAudioData(Uint8Array.from(raw, c => c.charCodeAt(0)).buffer); }
          catch (_) { throw new Error('声音数据异常。'); }
          if (version !== this.version) return;
          if (!total) rate = decoded.sampleRate;
          const data = decoded.getChannelData(0).slice();
          total += data.length;
          if (total > rate * 120) throw new Error('声音过长，请缩短文字后重试。');
          chunks.push(data); waiting.push(data); waitingSamples += data.length; schedule();
          if (this.bufferedPlayback) this.update({ loading: true, preparedSeconds: total / rate });
        } else if (event.type === 'done') {
          if (!rate || !total || finished) throw new Error('没有收到完整声音。');
          finished = true; schedule(true);
        } else if (event.type !== 'heartbeat') throw new Error('声音数据异常。');
      }
      if (version !== this.version) return;
      if (!finished) throw new Error('声音连接中断，请点击重试。');
      const samples = new Float32Array(total); let offset = 0;
      for (const chunk of chunks) { samples.set(chunk, offset); offset += chunk.length; }
      const blob = encodeWav(samples, rate); this.cache.set(key, blob);
      this.url = this.urls.createObjectURL(blob); this.audio.src = this.url;
      this.audio.hidden = !this.bufferedPlayback && firstPlay !== null && this.sources.size > 0;
      this.update({ loading: false });
      if (this.bufferedPlayback) {
        // The classroom uses one native channel for play, pause, seeking and stop.
        // Do not schedule Web Audio sources behind a different progress bar.
        try {
          await this.audio.play();
          if (version === this.version) this.update({ loading: false, firstPlaySeconds: (performance.now() - started) / 1000 });
        } catch (_) {
          if (version === this.version) this.update({ blocked: true, loading: false });
        }
        return;
      }
      if (firstPlay === null) {
        this.update({ streaming: false, text: '声音已就绪，点击播放器开始听。', failed: false });
      } else completePlayback();
    } catch (error) {
      if (version === this.version) {
        this.stop(); this.clearSource();
        this.update({ loading: false, streaming: false, text: error.message || '声音播放中断，请重试。', failed: true });
      }
    } finally {
      if (this.controller === controller) this.controller = null;
    }
  }
}
