// One playback channel per session. A stopped request may finish and be cached,
// but must never start speaking over a recording or a later conversation.
export class QuestionVoice {
  constructor(audio, load, update, urls = URL) {
    Object.assign(this, { audio, load, update, urls });
    this.cache = new Map(); this.version = 0; this.url = '';
  }

  stop() {
    ++this.version;
    this.audio.pause();
    this.update({ loading: false, stopped: true });
  }

  clearSource() {
    this.audio.removeAttribute('src'); this.audio.load(); this.audio.hidden = true;
    if (this.url) this.urls.revokeObjectURL(this.url);
    this.url = '';
  }

  clear() {
    this.stop(); this.clearSource(); this.cache.clear();
  }

  async play(questionId, voiceId = '', voiceName = '对话伙伴') {
    this.stop(); this.clearSource();
    const key = JSON.stringify([questionId, voiceId]);
    const version = this.version, started = performance.now(), cached = this.cache.has(key);
    this.update({ loading: true, text: cached ? '正在准备重听…' : `${voiceName}正在准备声音…`, failed: false });
    try {
      if (!cached) {
        const request = this.load(questionId, voiceId).catch(error => {
          if (this.cache.get(key) === request) this.cache.delete(key);
          throw error;
        });
        this.cache.set(key, request);
      }
      const blob = await this.cache.get(key);
      if (version !== this.version) return;
      this.url = this.urls.createObjectURL(blob);
      this.audio.src = this.url; this.audio.hidden = false;
      this.update({ loading: false, text: cached ? '已缓存，重听无需再次生成。' : `声音已就绪 · 等待 ${((performance.now() - started) / 1000).toFixed(1)} 秒`, failed: false });
      try { await this.audio.play(); }
      catch (_) {
        if (version === this.version) this.update({ loading: false, blocked: true, text: '声音已就绪，点击播放器或“重听问题”开始听。', failed: false });
      }
    } catch (error) {
      if (version === this.version) this.update({ loading: false, text: error.message, failed: true });
    }
  }
}
