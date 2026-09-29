// A user-controlled paper turn. Preview faces contain no live audio/video.
Studio.bookTurn = {
  active: null,
  update() {
    const stage = document.getElementById('book-stage');
    if (!stage) return;
    [-1, 1].forEach(delta => {
      const corner = document.getElementById(delta < 0 ? 'book-corner-prev' : 'book-corner-next');
      corner.disabled = !this.canTurn(delta);
      if (corner.dataset.bound) return;
      corner.dataset.bound = 'true';
      corner.addEventListener('pointerdown', event => {
        if (event.button === 0 && window.matchMedia('(prefers-reduced-motion: reduce)').matches) {
          event.preventDefault(); this.turn(delta); return;
        }
        if (event.button !== 0 || !this.begin(delta)) return;
        event.preventDefault(); corner.setPointerCapture(event.pointerId);
        Object.assign(this.active, { pointer: event.pointerId, startX: event.clientX, corner });
      });
      corner.addEventListener('pointermove', event => {
        const state = this.active;
        if (!state || state.pointer !== event.pointerId || state.settling) return;
        this.draw(Math.max(0, Math.min(1, (state.startX - event.clientX) * delta / state.width)));
      });
      corner.addEventListener('pointerup', event => {
        const state = this.active;
        if (!state || state.pointer !== event.pointerId) return;
        // A tap also turns; a short deliberate drag springs back.
        this.finish(Math.abs(state.startX - event.clientX) < 8 || state.progress > .22);
      });
      corner.addEventListener('pointercancel', () => this.cancel());
      corner.addEventListener('lostpointercapture', () => { if (this.active && !this.active.settling) this.cancel(); });
      corner.addEventListener('click', event => { if (event.detail === 0) this.turn(delta); });
    });
  },
  canTurn(delta) { const i = Studio.book.i + delta; return i >= 0 && i < Studio.book.pages.length; },
  face(page, index, current = false) {
    const face = document.createElement('div'); face.className = 'book flip-face';
    const visual = document.createElement('div'); visual.className = 'book-visual';
    if (page.url || page.video_url) {
      const art = document.createElement('div'); art.className = 'page-art';
      let picture = page.url;
      if (current && page.video_url) {
        const video = document.getElementById('page-video');
        if (video.readyState >= 2) {
          try {
            const canvas = document.createElement('canvas'); canvas.width = video.videoWidth; canvas.height = video.videoHeight;
            canvas.getContext('2d').drawImage(video, 0, 0);
            canvas.className = 'flip-video-frame'; art.appendChild(canvas); picture = '';
          } catch (_) { /* The original is still a safe preview if a frame cannot be captured. */ }
        }
      }
      art.style.backgroundImage = picture ? 'url(' + JSON.stringify(picture) + ')' : 'none'; visual.appendChild(art);
    } else {
      face.classList.add('is-ending');
    }
    face.appendChild(visual);
    const copy = document.createElement('div'); copy.className = 'book-copy';
    const label = document.createElement('span'); label.className = 'book-kicker';
    label.textContent = Studio.i18n.t(Studio.ending.label(page), { n: index + 1 });
    const text = document.createElement('div'); text.className = 'page-text';
    text.textContent = page.text || Studio.i18n.t(Studio.book.readOnly ? 'portfolio.noEnding' : 'book.then');
    const rule = document.createElement('span'); rule.className = 'book-page-rule';
    copy.append(label, text, rule); face.appendChild(copy);
    if (current) { const shown = document.getElementById('page-text'); text.style.fontSize = shown.style.fontSize; text.scrollTop = shown.scrollTop; }
    return face;
  },
  begin(delta) {
    if (this.active || !this.canTurn(delta)) return false;
    const stage = document.getElementById('book-stage'), sheet = document.getElementById('book-sheet');
    const rect = sheet.getBoundingClientRect();
    const preview = this.face(Studio.book.pages[Studio.book.i + delta], Studio.book.i + delta);
    preview.classList.add('flip-preview'); preview.setAttribute('aria-hidden', 'true');
    const paper = document.createElement('div'); paper.className = 'flip-paper'; paper.setAttribute('aria-hidden', 'true');
    paper.style.transformOrigin = delta > 0 ? 'left center' : 'right center';
    paper.appendChild(this.face(Studio.book.pages[Studio.book.i], Studio.book.i, true));
    const back = document.createElement('div'); back.className = 'flip-back'; paper.appendChild(back);
    const video = document.getElementById('page-video'); const resume = !video.paused && !video.hidden;
    video.pause();
    stage.append(preview, paper); stage.classList.add('turning');
    this.active = { delta, stage, paper, preview, width: Math.max(1, rect.width), progress: 0, video, resume };
    this.draw(0); return true;
  },
  draw(progress) {
    const state = this.active; if (!state) return;
    state.progress = progress;
    // Keep the printed face visible throughout, without a blank 180-degree back
    // or per-frame brightness filters. Only compositor-friendly properties move.
    state.paper.style.transform = 'translate3d(' + (-state.delta * progress * 105) + '%,0,0) rotateY(' + (-state.delta * progress * 24) + 'deg)';
    state.paper.style.opacity = String(1 - progress);
    state.preview.style.transform = 'translate3d(' + (state.delta * (1 - progress) * 8) + '%,0,0)';
  },
  finish(commit) {
    const state = this.active; if (!state || state.settling) return;
    state.settling = true;
    const distance = commit ? 1 - state.progress : state.progress;
    const duration = window.matchMedia('(prefers-reduced-motion: reduce)').matches ? 0 : Math.round(320 + 400 * distance);
    const easing = 'ms cubic-bezier(.22,.61,.36,1)';
    state.paper.style.transition = 'transform ' + duration + easing + ', opacity ' + duration + easing;
    state.preview.style.transition = 'transform ' + duration + easing;
    this.draw(commit ? 1 : 0);
    state.timer = setTimeout(() => {
      if (this.active !== state) return;
      this.cleanup(!commit);
      if (commit) Studio.book.goTo(state.delta);
    }, duration);
  },
  turn(delta) {
    if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) {
      if (!this.active && this.canTurn(delta)) Studio.book.goTo(delta);
      return;
    }
    if (this.begin(delta)) {
      // Commit the initial transform before starting the CSS transition.
      this.active.paper.getBoundingClientRect(); this.finish(true);
    }
  },
  cleanup(resume) {
    const state = this.active; if (!state) return;
    this.active = null; clearTimeout(state.timer);
    state.paper.remove(); state.preview.remove(); state.stage.classList.remove('turning');
    if (state.corner?.hasPointerCapture(state.pointer)) state.corner.releasePointerCapture(state.pointer);
    if (resume && state.resume) { const play = state.video.play(); if (play?.catch) play.catch(() => {}); }
  },
  cancel() { this.cleanup(true); }
};
