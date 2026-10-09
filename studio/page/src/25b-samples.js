window.Studio = window.Studio || {};
// A file that stops coming is asked for once more, past the browser's own copy. Over the slow link a full-size
// sample got its headers and then nothing for minutes while the thumbnails loaded beside it, every card disabled
// under the loading note; the same file asked for afresh came whole in about a second. A slow link still sends
// something every few seconds, so only `idle` milliseconds of nothing count as a stall, and it is asked for again only
// while `again()` says it is still wanted. Before its headers a file is given four times as long: it can wait in the
// browser's queue behind others (a phone's browser may keep fetching a thumbnail whose src was taken away), and
// waiting there is no stall. `hold` is handed each attempt's controller, so a file nobody wants any more gives its
// connection back. A picked sample and a 3D model come this way (27g-cloud-relight.js); the temple replay does the
// same for its files (steadyFetch in studio/showpiece/page/rebuild-runs.mjs).
Studio.steady = async function (url, again, hold, idle, type) {
  for (const cache of ['default', 'no-store']) {
    const stop = new AbortController(), parts = [];
    let timer;
    const wait = function (ms) { clearTimeout(timer); timer = setTimeout(function () { stop.abort(); }, ms); };
    hold(stop);
    try {
      wait(idle * 4);
      const response = await fetch(url, { cache: cache, signal: stop.signal });
      if (!response.ok) throw new Error('file unavailable');
      const reader = response.body.getReader();
      for (;;) {
        wait(idle);
        const step = await reader.read();
        if (step.done) return new Blob(parts, { type: response.headers.get('Content-Type') || type || '' });
        parts.push(step.value);
      }
    } catch (error) {
      if (cache === 'no-store' || error.name !== 'AbortError' || !again()) throw error;
    } finally {
      clearTimeout(timer);
    }
  }
};
Studio.samples = {
  version: 0, finish: null,
  close: function (blob) {
    this.version++;
    this.loading?.abort(); this.loading = null;
    document.getElementById('samples-overlay').hidden = true;
    document.getElementById('samples-grid').replaceChildren();
    const done = this.finish; this.finish = null; if (done) done(blob || null);
  },
  // A picked drawing comes by Studio.steady, asked for again while the pick still stands. Closing the sheet calls the
  // download off (`loading`), so a pick nobody wants gives its connection back.
  idle: 8000, loading: null,
  download: function (url, again) {
    const self = this;
    return Studio.steady(url, again, function (stop) { self.loading = stop; }, this.idle, 'image/jpeg');
  },
  choose: function () {
    this.close();
    const self = this, sid = Studio.state.session, version = this.version;
    const note = document.getElementById('samples-note'), grid = document.getElementById('samples-grid');
    document.getElementById('samples-overlay').hidden = false;
    note.textContent = Studio.i18n.t('samples.loading');
    document.getElementById('samples-close').onclick = function () { self.close(); };
    const result = new Promise(function (resolve) { self.finish = resolve; });
    if (Studio.state.transport.name !== 'http') {
      note.textContent = Studio.i18n.t('samples.unavailable'); return result;
    }
    fetch('/api/session/' + encodeURIComponent(sid) + '/samples').then(function (response) {
      if (!response.ok) throw new Error('samples unavailable'); return response.json();
    }).then(function (catalog) {
      if (version !== self.version || !Studio.session.isCurrent(sid)) return;
      note.textContent = Studio.i18n.t(catalog.items.length ? 'samples.choose' : 'samples.empty');
      catalog.items.forEach(function (item, index) {
        const button = document.createElement('button'), image = document.createElement('img'), label = document.createElement('span');
        button.type = 'button'; button.className = 'sample-card';
        image.src = item.thumbnail_url; image.alt = ''; image.loading = 'lazy';
        label.textContent = Studio.i18n.t('samples.item', { n: index + 1 });
        button.append(image, label);
        button.onclick = function () {
          const current = function () { return version === self.version && Studio.session.isCurrent(sid); };
          if (!current()) return;
          const buttons = grid.querySelectorAll('button'), stopped = [];
          buttons.forEach(function (b) { b.disabled = true; });
          // Thumbnails still coming hold the browser's few connections to the studio, and a stalled one keeps its
          // own for minutes: they make way for the picked drawing, and come back if it cannot be read. A transparent
          // picture takes their place, because an img with no src drew a broken-picture icon and lost its square.
          grid.querySelectorAll('img').forEach(function (img) {
            if (img.complete) return;
            stopped.push([img, img.src]);
            img.src = 'data:image/gif;base64,R0lGODlhAQABAIAAAAAAAP///yH5BAEAAAAALAAAAAABAAEAAAIBRAA7';
          });
          note.textContent = Studio.i18n.t('samples.loading');
          self.download(item.url, function () {
            if (current()) note.textContent = Studio.i18n.t('samples.retrying');
            return current();
          }).then(function (blob) {
            if (current()) self.close(blob);
          }).catch(function () {
            if (version !== self.version) return;
            note.textContent = Studio.i18n.t('samples.unavailable');
            buttons.forEach(function (b) { b.disabled = false; });
            stopped.forEach(function (pair) { pair[0].src = pair[1]; });
          });
        };
        grid.appendChild(button);
      });
    }).catch(function () { if (version === self.version) note.textContent = Studio.i18n.t('samples.unavailable'); });
    return result;
  }
};
