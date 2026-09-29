window.Studio = window.Studio || {};
Studio.samples = {
  version: 0, finish: null,
  close: function (blob) {
    this.version++;
    document.getElementById('samples-overlay').hidden = true;
    document.getElementById('samples-grid').replaceChildren();
    const done = this.finish; this.finish = null; if (done) done(blob || null);
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
          if (version !== self.version || !Studio.session.isCurrent(sid)) return;
          grid.querySelectorAll('button').forEach(function (b) { b.disabled = true; });
          note.textContent = Studio.i18n.t('samples.loading');
          fetch(item.url).then(function (response) {
            if (!response.ok) throw new Error('sample unavailable'); return response.blob();
          }).then(function (blob) {
            if (version === self.version && Studio.session.isCurrent(sid)) self.close(blob);
          }).catch(function () {
            if (version !== self.version) return;
            note.textContent = Studio.i18n.t('samples.unavailable');
            grid.querySelectorAll('button').forEach(function (b) { b.disabled = false; });
          });
        };
        grid.appendChild(button);
      });
    }).catch(function () { if (version === self.version) note.textContent = Studio.i18n.t('samples.unavailable'); });
    return result;
  }
};
