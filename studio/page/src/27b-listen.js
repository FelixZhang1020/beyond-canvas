// The child speaks and the machine writes it down for the teacher to check.
// Nothing here decides anything: the transcript lands in the field, the teacher
// reads it, and only then does it go to a skill. Section 5a asks for exactly
// that, and it is why the recording is never sent anywhere but the same origin.
window.Studio = window.Studio || {};
Studio.listen = {
  recorder: null, chunks: [], stream: null, version: 0,
  get on() { return !!this.recorder; },
  start: function () {
    this.release();
    const self = this, version = this.version;
    if (!navigator.mediaDevices?.getUserMedia || typeof MediaRecorder === 'undefined') {
      return Promise.reject(new Error('no microphone'));
    }
    return navigator.mediaDevices.getUserMedia({ audio: { echoCancellation: true, noiseSuppression: true } }).then(function (stream) {
      if (version !== self.version) { stream.getTracks().forEach(function (track) { track.stop(); }); return false; }
      try {
        // Speech rate, not music rate: the browser's own default can be 128 kbps, which left the
        // recording only half the size of the same sound as WAV. At 24 kbps it is a tenth, and a
        // voice loses nothing a transcriber needs (see sendable below).
        const recorder = new MediaRecorder(stream, { audioBitsPerSecond: 24000 }), chunks = [];
        self.stream = stream; self.chunks = chunks; self.recorder = recorder;
        recorder.addEventListener('dataavailable', function (e) { if (e.data.size) chunks.push(e.data); });
        recorder.start(); return true;
      } catch (error) { self.release(); throw error; }
    });
  },
  stop: function () {
    const self = this, recorder = this.recorder, stream = this.stream, chunks = this.chunks, version = this.version;
    if (!recorder || recorder.state === 'inactive') return Promise.resolve(null);
    self.recorder = null; self.stream = null; self.chunks = [];
    return new Promise(function (done, reject) {
      recorder.addEventListener('stop', function () {
        stream.getTracks().forEach(function (track) { track.stop(); });
        if (version !== self.version) { done(null); return; }
        const blob = new Blob(chunks, { type: recorder.mimeType || 'audio/webm' });
        if (!blob.size) { done(null); return; }
        self.sendable(blob).then(function (wav) { done(version === self.version ? wav : null); }).catch(reject);
      }, { once: true });
      recorder.addEventListener('error', function () {
        stream.getTracks().forEach(function (track) { track.stop(); }); reject(new Error('recording interrupted'));
      }, { once: true });
      recorder.stop();
      stream.getTracks().forEach(function (track) { track.stop(); });
    });
  },
  // What goes to the studio. A WebM or Ogg recording goes as the browser made it, about an
  // eighth the size of the same sound as WAV, and the studio unpacks it (studio/voice/audio_in.py):
  // sending it unpacked used to be most of the wait between Stop and the words.
  // Anything else (Safari records MP4, which the studio cannot read from a pipe) is still
  // unpacked here, as every recording was before.
  sendable: function (blob) {
    return /webm|ogg/.test(blob.type) ? Promise.resolve(blob) : this.toWav(blob);
  },
  // Decode whatever the browser recorded and re-encode it as the one format
  // every speech model reads without help.
  toWav: function (blob) {
    const Ctx = window.AudioContext || window.webkitAudioContext;
    if (!Ctx) return Promise.reject(new Error('no audio context'));
    const context = new Ctx({ sampleRate: 16000 });
    return blob.arrayBuffer()
      .then(function (bytes) { return context.decodeAudioData(bytes); })
      .then(function (audio) { return Studio.listen.encodeWav(audio); })
      .finally(function () { return context.close(); });
  },
  // The second route to the child's voice: a recording the teacher made earlier,
  // on her phone, before the studio was ever opened. It takes the same road as a
  // live one — decoded and re-encoded here — so the model receives one format and
  // the page keeps one path to test.
  fromFile: function (file) {
    if (!file || !file.size) return Promise.reject(new Error('nothing to listen to'));
    return this.toWav(file).catch(function () {
      throw new Error('nothing to listen to in that file');
    });
  },
  encodeWav: function (audio) {
    const rate = 16000, samples = audio.getChannelData(0), n = samples.length;
    const buffer = new ArrayBuffer(44 + n * 2), view = new DataView(buffer);
    const text = function (at, s) { for (let i = 0; i < s.length; i++) view.setUint8(at + i, s.charCodeAt(i)); };
    text(0, 'RIFF'); view.setUint32(4, 36 + n * 2, true); text(8, 'WAVE');
    text(12, 'fmt '); view.setUint32(16, 16, true); view.setUint16(20, 1, true);
    view.setUint16(22, 1, true); view.setUint32(24, rate, true);
    view.setUint32(28, rate * 2, true); view.setUint16(32, 2, true); view.setUint16(34, 16, true);
    text(36, 'data'); view.setUint32(40, n * 2, true);
    for (let i = 0; i < n; i++) {
      const clamped = Math.max(-1, Math.min(1, samples[i]));
      view.setInt16(44 + i * 2, clamped < 0 ? clamped * 0x8000 : clamped * 0x7FFF, true);
    }
    return new Blob([view], { type: 'audio/wav' });
  },
  release: function () {
    this.version++;
    if (this.recorder && this.recorder.state === 'recording') this.recorder.stop();
    if (this.stream) this.stream.getTracks().forEach(function (t) { t.stop(); });
    this.recorder = null; this.chunks = []; this.stream = null;
  }
};
