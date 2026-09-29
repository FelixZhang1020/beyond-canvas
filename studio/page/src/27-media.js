// Progress while media is made, and the viewer that shows it. Mock outputs draw on a canvas from the drawing itself.
window.Studio = window.Studio || {};
Studio.media = {
  raf: null,
  queue: function (stage, status, partial) {
    const meta = partial && partial.percent !== undefined ? partial.percent + '%' : undefined;
    Studio.companion.step(stage, status, meta);
  },
  clearQueue: function () {},
  open: function (title, kind, src, drawing) {
    Studio.sketchWorkbench?.close();
    this.pauseVideos();
    if (Studio.voice.restore) Studio.voice.restore();
    if (Studio.relight) Studio.relight.close();
    Studio.figureView?.close();
    if (Studio.motion) Studio.motion.stop();
    if (this.raf !== null) cancelAnimationFrame(this.raf); this.raf = null;
    const ov = document.getElementById('viewer-overlay'), media = document.getElementById('media'), book = document.getElementById('book');
    document.getElementById('viewer-title').textContent = title; book.hidden = true; media.hidden = false; media.innerHTML = '';
    media.classList.toggle('square', kind === 'turntable');
    media.classList.toggle('motion-view', kind === 'motion');
    media.classList.toggle('relight', kind === 'relight' || kind === 'figure');
    media.classList.toggle('keyframe-view', kind === 'keyframe');
    media.classList.toggle('clip', kind === 'video' && !(src && src.indexOf('mock:') === 0));
    if (kind === 'keyframe') this.keyframe(media, src, drawing);
    else if (kind === 'relight') Studio.relight.open(media, src, drawing);
    else if (kind === 'figure') Studio.figureView.open(media, src, drawing);
    else if (kind === 'motion') Studio.motion.open(media, src, drawing);
    else if (src && src.indexOf('mock:') === 0) this.mock(media, src.slice(5), drawing);
    else if (kind === 'video') { const v = document.createElement('video'); v.src = src; v.controls = true; v.autoplay = true; v.loop = true; v.muted = true; v.playsInline = true; media.appendChild(v); }
    else { const img = new Image(); img.src = src; media.appendChild(img); }
    ov.hidden = false;
  },
  pauseVideos: function () {
    document.querySelectorAll('#viewer-overlay video').forEach(function (v) { v.pause(); });
  },
  close: function () {
    this.pauseVideos();
    if (Studio.voice.restore) Studio.voice.restore();
    if (Studio.relight) Studio.relight.close();
    Studio.figureView?.close();
    if (Studio.motion) Studio.motion.stop();
    document.getElementById('viewer-overlay').hidden = true; if (this.raf) cancelAnimationFrame(this.raf); this.raf = null;
    Studio.sketchWorkbench?.refresh();
    if ('speechSynthesis' in window) speechSynthesis.cancel();
  },
  keyframe: function (host, frame, drawing) {
    const t = function (key) { return Studio.i18n.t(key); };
    if (!frame || frame.kind !== 'keyframe' || !/^data:image\/png;base64,/.test(frame.image || '') || !drawing) {
      host.textContent = t('keyframe.failed'); return;
    }
    const views = document.createElement('div'); views.className = 'keyframe-images';
    [['keyframe.original', drawing.url], ['keyframe.generated', frame.image]].forEach(function (part, index) {
      const figure = document.createElement('figure'), caption = document.createElement('figcaption'), img = new Image();
      caption.textContent = t(part[0]); img.alt = t(part[0]); img.src = part[1];
      if (index === 1) img.setAttribute('data-keyframe', 'true');
      img.onerror = function () { caption.textContent = t('keyframe.failed'); };
      figure.appendChild(caption); figure.appendChild(img); views.appendChild(figure);
    });
    const note = document.createElement('p'); note.className = 'keyframe-note'; note.textContent = t('keyframe.note');
    host.appendChild(views); host.appendChild(note);
  },
  mock: function (host, kind, drawing) {
    const self = this, c = document.createElement('canvas'), img = new Image();
    c.width = kind === 'turntable' ? 720 : 1280; c.height = kind === 'turntable' ? 720 : 720; host.appendChild(c);
    const g = c.getContext('2d');
    img.onload = function () {
      const t0 = performance.now();
      function fit(w, h, box) { const k = Math.min(box / w, box / h); return [w * k, h * k]; }
      function frame(now) {
        const t = (now - t0) / 1000, W = c.width, H = c.height;
        g.clearRect(0, 0, W, H);
        if (kind === 'turntable') {
          g.fillStyle = '#EAF6FF'; g.fillRect(0, 0, W, H);
          const s = fit(img.width, img.height, W * .7), a = t * 1.2, sx = Math.cos(a), shade = .6 + .4 * Math.abs(sx);
          g.save(); g.translate(W / 2, H / 2 + 20); g.scale(Math.max(.06, Math.abs(sx)), 1);
          g.globalAlpha = shade; g.drawImage(img, -s[0] / 2, -s[1] / 2, s[0], s[1]); g.restore();
          g.globalAlpha = .18; g.fillStyle = '#26224A'; g.beginPath(); g.ellipse(W / 2, H / 2 + s[1] / 2 + 30, s[0] * .5 * Math.abs(sx) + 40, 22, 0, 0, 7); g.fill();
          g.globalAlpha = 1;
        } else if (kind === 'scene') {
          const s = fit(img.width, img.height, Math.max(W, H) * 1.3), px = Math.sin(t * .6) * 60, py = Math.cos(t * .4) * 30;
          g.filter = 'blur(18px)'; g.drawImage(img, (W - s[0]) / 2 - px * .4, (H - s[1]) / 2 - py * .4, s[0], s[1]); g.filter = 'none';
          const f = fit(img.width, img.height, Math.min(W, H) * .78);
          g.drawImage(img, (W - f[0]) / 2 + px, (H - f[1]) / 2 + py, f[0], f[1]);
        } else {
          g.fillStyle = '#FFFDF8'; g.fillRect(0, 0, W, H);
          const z = 1.04 + .06 * Math.sin(t * .8), s = fit(img.width, img.height, Math.min(W, H) * .92);
          g.save(); g.translate(W / 2, H / 2); g.rotate(Math.sin(t * 1.3) * .03); g.scale(z, z);
          g.drawImage(img, -s[0] / 2, -s[1] / 2, s[0], s[1]); g.restore();
          g.fillStyle = '#fff';
          for (let i = 0; i < 10; i++) { const x = (i * 131 + t * 40) % W, y = (i * 97 + Math.sin(t + i) * 30 + H) % H; g.globalAlpha = .7; g.beginPath(); g.arc(x, y, 3 + (i % 3), 0, 7); g.fill(); }
          g.globalAlpha = 1;
        }
        self.raf = requestAnimationFrame(frame);
      }
      self.raf = requestAnimationFrame(frame);
    };
    img.src = drawing.url;
  }
};
