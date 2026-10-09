// One page at a time: manual turns or narration-led continuous reading.
window.Studio = window.Studio || {};
Studio.book = {
  pages: [], i: 0, playing: false, audio: null,
  open: function (title, out, drawings, context) {
    this.stop();
    if (Studio.media && Studio.media.pauseVideos) Studio.media.pauseVideos();
    this.renderedPage = null;
    this.courseId = context && context.courseId || Studio.state.courseId || Studio.state.session;
    this.artifactId = out.artifact_id; this.history = !!(context && context.history);
    // So an ending saved now is there when the book opens again.
    this.out = out; this.quiet = false;
    this.readOnly = context && context.readOnly !== undefined ? context.readOnly : this.history;
    if (Studio.relight) Studio.relight.close();
    if (Studio.motion) Studio.motion.stop();
    const ov = document.getElementById('viewer-overlay');
    const book = document.getElementById('book');
    const inlineHost = context && context.inlineHost;
    if (inlineHost) {
      this.overlayHost ||= book.parentNode;
      inlineHost.appendChild(book);
      this.inlineHost = inlineHost;
    } else if (this.inlineHost) {
      this.closeInline();
    }
    document.getElementById('viewer-title').textContent = title || out.title;
    document.getElementById('media').hidden = true; book.hidden = false;
    if (Studio.voice.place) Studio.voice.place(document.getElementById('book-voice-slot') || document.getElementById('book'));
    document.getElementById('book').onkeydown = event => {
      if (event.altKey || event.ctrlKey || event.metaKey || event.target.closest?.('input,textarea,select,video,audio')) return;
      if (event.key === 'ArrowLeft' || event.key === 'ArrowRight') { event.preventDefault(); this.keyed = true; this.go(event.key === 'ArrowLeft' ? -1 : 1); }
    };
    this.pages = out.pages.map(function (p) {
      const d = drawings.find(function (x) { return x.id === p.drawing_id; });
      // A picture-book page shows its redrawn picture (29l-book-look.js); the originals show the drawing.
      return { text: p.text, audio_url: p.audio_url, video_url: p.video_url, url: p.picture_url || (d ? d.url : '') };
    });
    // The last page is blank and belongs to the child; see Studio.ending.
    this.pages = Studio.ending.add(this.pages);
    if (out.ending) this.pages = Studio.ending.answer(this.pages, out.ending);
    // Visible first, so the passage can be measured.
    this.i = 0; this.playing = false; ov.hidden = !!inlineHost; this.show();
    document.getElementById('page-text').scrollTop = 0;
    this.read();
  },
  closeInline: function () {
    if (!this.inlineHost) return;
    this.stop();
    document.getElementById('page-video').pause();
    const book = document.getElementById('book');
    book.hidden = true;
    this.overlayHost.appendChild(book);
    this.inlineHost = null;
    if (Studio.voice.restore) Studio.voice.restore();
  },
  show: function () {
    const p = this.pages[this.i]; if (!p) return;
    const waiting = Studio.ending.waiting(p);
    const sheet = document.getElementById('book-sheet');
    if (sheet) sheet.classList.toggle('is-ending', !p.url && !p.video_url);
    const label = document.getElementById('book-page-label');
    if (label) label.textContent = Studio.i18n.t(Studio.ending.label(p), { n: this.i + 1 });
    document.getElementById('page-art').setAttribute?.('aria-label', Studio.i18n.t('picture.index', { n: this.i + 1 }));
    document.getElementById('page-art').style.backgroundImage = p.url ? 'url("' + p.url + '")' : '';
    document.getElementById('page-art').hidden = !p.url || !!p.video_url;
    const video = document.getElementById('page-video');
    const motion = document.getElementById('book-video-toggle');
    if (motion && video) {
      motion.hidden = !p.video_url;
      const updateMotion = () => { motion.textContent = Studio.i18n.t(video.paused ? 'book.playMotion' : 'book.pauseMotion'); };
      video.onplay = video.onpause = updateMotion;
      video.onerror = () => { motion.textContent = Studio.i18n.t('book.motionFailed'); };
      motion.onclick = () => { if (video.paused) { if (video.error) video.load(); const play = video.play(); if (play?.catch) play.catch(updateMotion); } else video.pause(); updateMotion(); };
      updateMotion();
    }
    if (video && this.renderedPage !== p) {
      this.renderedPage = p;
      video.pause(); video.hidden = !p.video_url;
      video.loop = true; video.muted = true;
      window.clearTimeout?.(this.clipWait); this.clipGo = null;
      if (p.video_url) {
        // The drawing shows until the clip plays (without it, a blank page). A page about to be read fetches its clip
        // once its voice is heard, or after 3 s: both come down one slow link, the voice first.
        video.poster = p.url || ''; video.removeAttribute('src'); video.load();
        let fetched = false;
        const go = () => {
          if (fetched || this.renderedPage !== p) return;
          fetched = true; video.src = p.video_url; video.load();
          const play = video.play(); if (play && play.catch) play.catch(function () {});
        };
        if (this.quiet || !p.text) go(); else { this.clipGo = go; this.clipWait = window.setTimeout?.(go, 3000); }
      } else { video.removeAttribute('src'); video.removeAttribute('poster'); video.load(); }
    }
    document.getElementById('page-text').textContent = waiting ? Studio.i18n.t(this.readOnly ? 'portfolio.noEnding' : 'book.then') : p.text;
    document.getElementById('page-text').classList.toggle('asking', waiting);
    document.getElementById('ending').hidden = !waiting || this.readOnly;
    document.getElementById('book-read').hidden = waiting || (!p.text && !p.audio_url);
    document.getElementById('book-edit-ending').hidden = this.readOnly || !p.ending || waiting;
    document.getElementById('book-n').textContent = Studio.i18n.t('book.page', { i: this.i + 1, n: this.pages.length });
    document.getElementById('book-prev').disabled = this.i === 0;
    document.getElementById('book-next').disabled = this.i >= this.pages.length - 1;
    if (Studio.bookTurn) Studio.bookTurn.update();
    document.getElementById('book-read').firstChild.textContent =
      Studio.i18n.t(this.playing ? 'book.stop' : 'book.read');
    this.fit();
  },
  // The whole passage shows: the type steps down to 15px, then the page scrolls and fades (lines used to be hidden).
  fit: function () {
    const box = document.getElementById('page-text');
    if (!box || !box.style || !box.clientHeight || typeof getComputedStyle !== 'function') return;
    if (!this.refits) { this.refits = true; window.addEventListener?.('resize', () => this.fit()); }
    box.style.fontSize = '';
    let size = parseFloat(getComputedStyle(box).fontSize) || 15;
    while (size > 15 && box.scrollHeight > box.clientHeight + 1) { size -= 1; box.style.fontSize = size + 'px'; }
    const more = () => box.classList.toggle('more', box.scrollTop + box.clientHeight < box.scrollHeight - 1);
    box.onscroll = more; more();
  },
  // The ending: typed by the teacher, or said by the child and written down (moved out of 30-main.js).
  saveEnding: async function (e, toast) {
    e.preventDefault();
    if (this.readOnly) return;
    const text = document.getElementById('ending-text').value.trim();
    if (!text) { toast(Studio.i18n.t('book.thenEmpty')); return; }
    const button = document.getElementById('ending').querySelector('button[type="submit"]'), pages = this.pages;
    button.disabled = true;
    try {
      if (this.artifactId) await Studio.portfolio.saveEnding(this.courseId, this.artifactId, text);
      if (this.pages !== pages || !this.answer(text)) return;
      document.getElementById('ending-text').value = '';
      // A recording still running is let go with the box, and the child hears the ending read back, as every page
      // is on arriving, unless the reading was stopped.
      if (this.i === this.pages.length - 1) { this.stop(); if (!this.quiet) this.read(); }
    } catch (_) { toast(Studio.i18n.t('portfolio.failed')); }
    finally { button.disabled = false; }
  },
  editEnding: function () {
    const page = this.pages[this.i];
    if (this.readOnly || !page || !page.ending) return;
    this.stop();
    document.getElementById('ending').hidden = false;
    document.getElementById('ending-text').value = page.text || '';
    document.getElementById('ending-text').focus();
  },
  go: function (delta) {
    if (Studio.bookTurn) return Studio.bookTurn.turn(delta);
    this.goTo(delta);
  },
  goTo: function (delta) {
    if (this.i + delta < 0 || this.i + delta >= this.pages.length) return;
    this.stop();
    this.i = Math.max(0, Math.min(this.pages.length - 1, this.i + delta));
    this.show();
    document.getElementById('page-text').scrollTop = 0;
    // A keyboard turn keeps the keyboard (the turn hides the page); a stopped book stays quiet.
    if (this.keyed) { this.keyed = false; document.getElementById('page-text').focus?.({ preventScroll: true }); }
    if (!this.quiet) this.read();
  },
  // Returns the clip still waiting for the voice, which only a Stop on the same page lets go (read).
  stop: function () {
    if (Studio.bookTurn) Studio.bookTurn.cancel();
    // A recording of the ending goes with its page, from its start to its words: the book closed or turned, the
    // microphone used to stay on. Only the ending's own: the chat's recording is not the book's to end.
    const listen = document.getElementById('ending-listen');
    if (listen && (listen.disabled || listen.classList.contains?.('on')) && Studio.microphones) Studio.microphones.release();
    const clip = this.clipGo; this.clipGo = Studio.voice.onstart = null; window.clearTimeout?.(this.clipWait);
    this.readVersion = (this.readVersion || 0) + 1;
    this.playing = false; if (this.audio) { this.audio.pause(); this.audio = null; }
    if (Studio.voice.stop) Studio.voice.stop();
    else if ('speechSynthesis' in window) speechSynthesis.cancel(); this.show();
    return clip;
  },
  // What the child says at the end is the ending, and the book stops waiting.
  answer: function (text) {
    if (this.readOnly) return false;
    this.pages = Studio.ending.answer(this.pages, text);
    if (this.out) this.out.ending = text;
    this.show();
    return !Studio.ending.waiting(this.pages[this.pages.length - 1]);
  },
  read: function () {
    const self = this, p = this.pages[this.i];
    if (!p || Studio.ending.waiting(p) || (!p.text && !p.audio_url)) return;
    if (this.playing) { const clip = this.stop(); this.quiet = true; if (clip) clip(); return; }
    this.quiet = false; this.playing = true; this.show();
    const version = this.readVersion = (this.readVersion || 0) + 1;
    const done = function () { if (self.readVersion !== version) return; self.playing = false; self.show(); };
    const ended = function () {
      if (self.readVersion !== version) return;
      done();
      // A pending manual gesture owns the next page; never race it.
      if (!Studio.bookTurn?.active && self.i < self.pages.length - 1 &&
          !Studio.ending.waiting(self.pages[self.i + 1])) self.go(1);
    };
    if (p.audio_url && !p.text?.trim()) {
      this.audio = new Audio(p.audio_url); this.audio.onended = ended; this.audio.onerror = done;
      const play = this.audio.play(); if (play && play.catch) play.catch(done);
      return;
    }
    // In the voice of the child who first talked about this page's drawing out loud, and the ending in the voice of the
    // page before it; the studio answers with its own storybook voice where no child's is kept (studio/voice/child_voice.py).
    const q = this.out.pages[this.i] || this.out.pages[this.i - 1];
    Studio.voice.speak(p.text, { rate: .9, voice: q && q.drawing_id ? 'child:' + q.drawing_id : 'soft-child', onend: ended,
      onerror: done, onstart: this.clipGo, courseId: this.history ? this.courseId : null });
  }
};
