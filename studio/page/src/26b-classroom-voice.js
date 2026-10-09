// The classroom and voice lab share the tested PCM player, with one local voice channel.
(function () {
  const voice = Studio.voice, browserSpeak = voice.speak;
  voice.init = function () {
    const audio = document.getElementById('classroom-audio');
    const status = document.getElementById('voice-status');
    const stop = document.getElementById('voice-stop'), box = document.getElementById('classroom-voice');
    stop.hidden = true;
    this.player = new Studio.StreamingQuestionVoice(audio, function (text, selected, opts) {
      const course = opts && opts.courseId !== undefined ? opts.courseId : voice.courseId;   // a prepared line names its own
      if (course) return Studio.portfolio.speak(course, text, selected, opts);
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
  // An iPhone or iPad in silent mode mutes the web's sound unless the page says it plays media (operator: no voice
  // on an iPhone with the ring switch off). Not while recording, which is left to the browser (27b-listen.js).
  voice.media = function () { const s = window.navigator?.audioSession; if (s && !Studio.listen?.on) s.type = 'playback'; };
  voice.unlock = function () {
    this.media();
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
  // The lines in the pieces the voice reads: at most 60 characters, cut after punctuation where it can.
  function pieces(texts, opts) {
    return texts.map(item => typeof item === 'string' ? { text: item, voice: opts.voice } : item)
      .filter(item => item?.text?.trim()).flatMap(item => {
      const points = Array.from(item.text), parts = [];
      while (points.length) {
        let end = Math.min(60, points.length);
        if (points.length > end) {
          for (let i = end - 1; i >= 20; i--) {
            if ('。！？；，.!?;'.includes(points[i])) { end = i + 1; break; }
          }
        }
        parts.push({ text: points.splice(0, end).join(''), voice: item.voice || opts.voice });
      }
      return parts;
    });
  }
  voice.playAll = function (texts, opts = {}) {
    this.stop();
    const token = this.queueToken, queue = pieces(texts, opts);
    const next = () => {
      if (this.queueToken !== token || !queue.length) return;
      const part = queue.shift();
      this.speak(part.text, Object.assign({}, opts, { voice: part.voice, queueToken: token, onend: next }));
      // The next piece is fetched while this one plays, so a conversation plays without a pause (operator).
      if (queue.length) this.prepare(queue[0].text, { voice: queue[0].voice, courseId: opts.courseId || null });
    };
    next();
  };
  // What Play would read first, fetched as soon as the conversation is on screen, so it starts at once (operator).
  voice.prepareStart = function (texts, opts = {}) {
    const first = pieces(texts, opts)[0];
    if (first) this.prepare(first.text, { voice: first.voice, courseId: opts.courseId || null });
  };
  voice.prepare = function (text, opts = {}) {
    if (Studio.state.transport?.name !== 'http' || !this.player || !this.available) return;
    const selected = opts.voice || this.selected();
    // A child's voice is only made ahead on the studio, which keeps it; never held here (see speak).
    this.player.prepare(text, selected, { courseId: opts.courseId, keep: !/^child(-words)?:/.test(selected) });
  };
  voice.speak = function (text, opts) {
    if (Studio.state.transport?.name !== 'http') return browserSpeak.call(this, text, opts);
    this.media();
    Studio.bus.emit('speaking');
    this.stop(opts && opts.queueToken === this.queueToken);
    // Another class's line keeps what is ready: the same words in the same voice are the same sound in any class,
    // a child's voice is never held here, and a new player started without a tap may stay silent on a phone.
    const courseId = opts && opts.courseId || null;
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
    // here, a book spoke in the voice taken back (studio/voice/child_voice.py). The chat's playback of a child's own
    // answers ("child-words:") the same.
    if (/^child(-words)?:/.test(selected)) this.player.cache.delete(JSON.stringify([text, selected]));
    return this.player.play(text, selected).then(function () {
      while (self.player.cache.size > 12) self.player.cache.delete(self.player.cache.keys().next().value);
    });
  };
})();
