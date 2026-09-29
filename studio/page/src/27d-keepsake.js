// What the child takes home.
//
// The class forgets the child: the drawings and the recording are dropped when
// it ends. The finished work is the exception, and it is the whole point of the
// product. This module turns what is on screen into a file a parent can open on
// any machine, later, with no studio and no network.
//
// A keepsake that only renders while online would break the promise this
// product makes loudest, in the one artefact that leaves the building. So the
// book is a single file: every picture embedded, no script, no link.
//
// Every word that reaches a filename comes from the locale tables, because a
// filename is text a person reads.
window.Studio = window.Studio || {};
Studio.keepsake = {
  word: function (key) {
    const table = (Studio.strings && Studio.strings.zh) || {};
    return table[key] || key;
  },

  filename: function (kind, when) {
    const at = when || new Date();
    const pad = function (n) { return (n < 10 ? '0' : '') + n; };
    const stamp = pad(at.getMonth() + 1) + pad(at.getDate())
      + '-' + pad(at.getHours()) + pad(at.getMinutes());
    const ext = { book: 'html', motion: 'webm', still: 'png' }[kind] || 'bin';
    return this.word('file.stem') + '-' + this.word('file.' + kind)
      + '-' + stamp + '.' + ext;
  },

  escape: function (text) {
    return String(text == null ? '' : text)
      .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
  },

  // One file, no script, no link. The pages are turned by scrolling, which needs
  // nothing to be running.
  bookHtml: function (title, pages) {
    const self = this;
    const leaves = pages.map(function (page, i) {
      const words = page.text ? '<p class="say">' + self.escape(page.text) + '</p>' : '';
      // The ending has no drawing: it is what the child said after the story ran
      // out. An empty src would keep a broken frame in the file forever.
      const art = page.art
        ? (page.video ? '<video controls playsinline muted autoplay loop src="' : '<img alt="" src="')
          + self.escape(page.art) + (page.video ? '"></video>' : '">') : '';
      return '<section class="leaf' + (page.art ? '' : ' wordsonly') + '">' + art
        + words + '<span class="n">' + (i + 1) + ' / ' + pages.length + '</span></section>';
    }).join('\n');
    return '<!doctype html>\n<html lang="zh"><head><meta charset="utf-8">'
      + '<meta name="viewport" content="width=device-width,initial-scale=1">'
      + '<title>' + this.escape(title) + '</title><style>'
      + 'body{margin:0;background:#FFFDF8;color:#26224A;'
      + 'font:16px/1.7 "PingFang SC","Hiragino Sans GB",ui-rounded,system-ui,sans-serif}'
      + '.page{max-width:720px;margin:0 auto;padding:40px 20px 80px}'
      + 'h1{font-size:28px;margin:0 0 28px;text-wrap:balance}'
      + '.leaf{margin:0 0 40px;padding:0 0 28px;border-bottom:1px solid #EDE7DA;position:relative}'
      + '.leaf img,.leaf video{width:100%;border-radius:18px;display:block;background:#fff}'
      + '.say{font-size:19px;margin:18px 0 0;text-wrap:pretty}'
      + '.wordsonly{padding-top:40px}.wordsonly .say{font-size:23px;text-align:center}'
      + '.n{position:absolute;right:0;bottom:6px;font-size:12px;color:#5A557A}'
      + '</style></head><body><div class="page"><h1>' + this.escape(title) + '</h1>\n'
      + leaves + '\n</div></body></html>';
  },

  // A blob:, http: or already-embedded picture, as one that needs nothing.
  embed: function (url) {
    if (!url || url.indexOf('data:') === 0) return Promise.resolve(url || '');
    return fetch(url).then(function (r) { return r.blob(); }).then(function (blob) {
      return new Promise(function (resolve) {
        const reader = new FileReader();
        reader.onload = function () { resolve(reader.result); };
        reader.onerror = function () { resolve(''); };
        reader.readAsDataURL(blob);
      });
    }).catch(function () { return ''; });
  },

  // Whatever the viewer has open, kept as a file: a still, the book, a canvas or a clip. Moved out of 30-main.js
  // with the size split; a portable keepsake is separate from the server's saved course portfolio.
  saveOpen: function (toast) {
    const button = document.getElementById('viewer-save'), label = button.querySelector('span');
    const was = label.textContent;
    label.textContent = Studio.i18n.t('save.working'); button.disabled = true;
    const done = function (ok) {
      label.textContent = was; button.disabled = false;
      toast(Studio.i18n.t(ok ? 'save.done' : 'save.failed'));
    };
    let job = null;
    if (Studio.relight.active) {
      job = Studio.relight.active.snapshot().then(function (blob) { Studio.keepsake.save(blob, Studio.keepsake.filename('still')); });
    } else if (!document.getElementById('book').hidden && Studio.book.pages.length) {
      job = Studio.keepsake.book(document.getElementById('viewer-title').textContent, Studio.book.pages);
    } else {
      const canvas = document.getElementById('media').querySelector('canvas'), video = document.getElementById('media').querySelector('video');
      const keyframe = document.getElementById('media').querySelector('img[data-keyframe]');
      if (keyframe && keyframe.complete && keyframe.naturalWidth) {
        job = fetch(keyframe.src).then(function (r) { return r.blob(); }).then(function (blob) {
          Studio.keepsake.save(blob, Studio.keepsake.filename('still'));
        });
      } else if (canvas) job = Studio.keepsake.canvas(canvas);
      else if (video && video.src) {
        job = fetch(video.src).then(function (r) { return r.blob(); }).then(function (blob) {
          Studio.keepsake.save(blob, Studio.keepsake.filename('motion').replace(/\.webm$/, blob.type === 'video/mp4' ? '.mp4' : '.webm'));
          return 'motion';
        });
      }
    }
    if (!job) { done(false); return; }
    job.then(function () { done(true); }).catch(function () { done(false); });
  },
  save: function (blob, name) {
    const url = URL.createObjectURL(blob), a = document.createElement('a');
    a.href = url; a.download = name; a.hidden = true;
    document.body.appendChild(a); a.click(); a.remove();
    setTimeout(function () { URL.revokeObjectURL(url); }, 4000);
  },

  book: function (title, pages) {
    const self = this;
    return Promise.all(pages.map(function (p) { return self.embed(p.video_url || p.url || p.art); }))
      .then(function (arts) {
        const leaves = pages.map(function (p, i) { return { art: arts[i], video: !!p.video_url, text: p.text || '' }; });
        self.save(new Blob([self.bookHtml(title, leaves)], { type: 'text/html' }),
          self.filename('book'));
        return 'book';
      });
  },

  // A canvas is a drawing that moves, and a file has to hold the moving. Where
  // the browser cannot record, a still picture is a smaller promise honestly
  // kept, rather than a button that fails.
  still: function (canvas) {
    const self = this;
    return new Promise(function (resolve) {
      canvas.toBlob(function (blob) {
        if (blob) self.save(blob, self.filename('still'));
        resolve('still');
      }, 'image/png');
    });
  },

  canvas: function (canvas, seconds) {
    const self = this;
    if (canvas.motionReduced || typeof MediaRecorder === 'undefined' || !canvas.captureStream) {
      return this.still(canvas);
    }
    let recorder, stream;
    const release = function () { if (stream) stream.getTracks().forEach(function (track) { track.stop(); }); };
    try {
      stream = canvas.captureStream(30);
      recorder = new MediaRecorder(stream, { mimeType: 'video/webm' });
    } catch (e) {
      release();
      return this.still(canvas);
    }
    return new Promise(function (resolve, reject) {
      const chunks = [];
      let timer, failed = false;
      recorder.onerror = function () { failed = true; clearTimeout(timer); release(); reject(new Error('recording failed')); };
      recorder.ondataavailable = function (e) { if (e.data && e.data.size) chunks.push(e.data); };
      recorder.onstop = function () {
        clearTimeout(timer); release();
        if (failed) return;
        if (!chunks.length) { reject(new Error('empty recording')); return; }
        self.save(new Blob(chunks, { type: 'video/webm' }), self.filename('motion'));
        resolve('motion');
      };
      try { recorder.start(); } catch (e) { release(); reject(e); return; }
      timer = setTimeout(function () {
        if (recorder.state !== 'inactive') recorder.stop();
      }, (seconds || canvas.motionDuration || 6) * 1000);
    });
  }
};
