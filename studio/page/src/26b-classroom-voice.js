// The classroom and voice lab share the tested PCM player, with one local voice channel.
(function () {
  const voice = Studio.voice, browserSpeak = voice.speak;
  voice.init = function () {
    const audio = document.getElementById('classroom-audio');
    const status = document.getElementById('voice-status');
    const stop = document.getElementById('voice-stop'), box = document.getElementById('classroom-voice');
    stop.hidden = true;
    this.player = new Studio.StreamingQuestionVoice(audio, function (text, selected, opts) {
      if (voice.courseId) return Studio.portfolio.speak(voice.courseId, text, selected, opts);
      return Studio.state.transport.speak(Studio.state.session, text, selected, opts);
    }, function (state) {
      if (state.firstPlaySeconds != null) voice.started();
      if (state.stopped || state.failed || state.ended) stop.hidden = true;
      else if (state.loading || state.blocked || state.preparedSeconds != null || state.firstPlaySeconds != null) stop.hidden = false;
      if (state.failed) { status.textContent = Studio.i18n.t('voice.failed'); voice.complete(false); }
      else if (state.ended) { status.textContent = ''; voice.complete(); }
      else if (state.blocked) {
        status.textContent = Studio.i18n.t('voice.tapPlay');
        if (audio.hidden) voice.complete(false);
      }
      else if (state.preparedSeconds != null) status.textContent = Studio.i18n.t('voice.preparingProgress', { seconds: state.preparedSeconds.toFixed(1) });
      else if (state.loading) status.textContent = Studio.i18n.t('voice.loading');
      else if (state.firstPlaySeconds != null) status.textContent = Studio.i18n.t('voice.playing');
      else if (state.streaming === false && state.text && !state.stopped) {
        status.textContent = audio.hidden ? '' : Studio.i18n.t('voice.tapPlay');
        if (audio.hidden) voice.complete(false);
      }
      else if (state.stopped) status.textContent = '';
      // The chat hides its player bar (04b-chat-panel.css) except when a press on Play is the only way to
      // hear the line: the browser blocked playing on its own (code review).
      box.classList.toggle('voice-manual', status.textContent === Studio.i18n.t('voice.tapPlay'));
    });
    // Start PCM playback as it arrives; expose native seeking only for the completed replay.
    this.player.bufferedPlayback = false;
    audio.addEventListener('ended', function () { stop.hidden = true; status.textContent = Studio.i18n.t('voice.ready'); voice.complete(); });
    audio.addEventListener('error', function () { stop.hidden = true; status.textContent = Studio.i18n.t('voice.failed'); voice.complete(false); });
    audio.addEventListener('play', function () {
      stop.hidden = false; status.textContent = Studio.i18n.t('voice.playing'); box.classList.remove('voice-manual');
    });
    document.getElementById('voice-stop').addEventListener('click', function () { voice.stop(); });
    const select = document.getElementById('f-voice');
    select.value = this.selected();
    select.addEventListener('change', function () {
      voice.stop();
      try { localStorage.setItem('beyond-canvas.companion-voice-v3', select.value); } catch (_) {}
    });
    Studio.bus.on('session', function () { voice.clear(); });
    Studio.bus.on('ended', function () { voice.clear(); });
    Studio.bus.on('current', function () { voice.stop(); });
  };
  voice.selected = function () {
    let selected;
    try { selected = localStorage.getItem('beyond-canvas.companion-voice-v3'); } catch (_) {}
    return selected === 'gentle-male' ? selected : 'gentle-female';
  };
  voice.configure = function (health) { this.available = !!(health && health.speech && health.speech.available); };
  voice.place = function (host) { host.appendChild(document.getElementById('classroom-voice')); };
  voice.restore = function () {
    const home = document.getElementById('buddy');
    home.insertBefore(document.getElementById('classroom-voice'), document.getElementById('buddy-dialogue'));
  };
  voice.unlock = function () {
    if (!this.player || Studio.state.transport?.name !== 'http') return;
    try {
      this.player.context ||= this.player.contextFactory();
      void this.player.context.resume().catch(function () {});
    } catch (_) {}
  };
  voice.complete = function (success = true) {
    const done = success ? this.onend : this.onerror;
    this.started(); this.onend = this.onerror = null; if (done) done();
  };
  // Heard, finished or given up: what waited for the voice (a book page's clip, 28-book.js) goes ahead once.
  voice.started = function () { const go = this.onstart; this.onstart = null; if (go) go(); };
  voice.stop = function (keepQueue) {
    if (!keepQueue) this.queueToken = (this.queueToken || 0) + 1;
    this.started(); this.onend = this.onerror = null;
    if (this.player) { this.player.stop(); this.player.clearSource(); }
    if ('speechSynthesis' in window) speechSynthesis.cancel();
  };
  voice.clear = function () { this.stop(); if (this.player) this.player.clear(); this.courseId = null; };
  voice.playAll = function (texts, opts = {}) {
    this.stop();
    const token = this.queueToken, queue = texts.map(item => typeof item === 'string' ? { text: item, voice: opts.voice } : item)
      .filter(item => item?.text?.trim()).flatMap(item => {
      const points = Array.from(item.text), parts = [];
      while (points.length) {
        let end = Math.min(60, points.length);
        if (points.length > end) {
          for (let i = end - 1; i >= 20; i--) {
            if ('。！？；，.!?;'.includes(points[i])) { end = i + 1; break; }
          }
        }
        parts.push({ text: points.splice(0, end).join(''), voice: item.voice });
      }
      return parts;
    });
    const next = () => {
      if (this.queueToken !== token || !queue.length) return;
      const part = queue.shift();
      this.speak(part.text, Object.assign({}, opts, { voice: part.voice || opts.voice, queueToken: token, onend: next }));
    };
    next();
  };
  voice.speak = function (text, opts) {
    if (Studio.state.transport?.name !== 'http') return browserSpeak.call(this, text, opts);
    Studio.bus.emit('speaking');
    this.stop(opts && opts.queueToken === this.queueToken);
    const courseId = opts && opts.courseId || null;
    if (this.courseId !== courseId && this.player) this.player.clear();
    this.courseId = courseId; this.onend = opts && opts.onend; this.onerror = opts && opts.onerror;
    this.onstart = opts && opts.onstart;
    if (!text) { this.complete(false); return null; }
    if (!this.available || !this.player || (!Studio.state.session && !this.courseId)) {
      document.getElementById('voice-status').textContent = Studio.i18n.t('voice.unavailable');
      this.complete(false); return null;
    }
    const self = this, selected = opts && opts.voice || this.selected();
    // A child's voice is asked for afresh every time: the recording behind it can change while the page is open (an
    // answer taken back and said again), and the studio keeps each reading, so asking again is instant. Played from
    // here, a book spoke in the voice taken back (studio/voice/child_voice.py).
    if (/^child:/.test(selected)) this.player.cache.delete(JSON.stringify([text, selected]));
    return this.player.play(text, selected).then(function () {
      while (self.player.cache.size > 12) self.player.cache.delete(self.player.cache.keys().next().value);
    });
  };
})();
