// The 3D figure inspired by a colour painting, beside the painting itself. The figure is data the studio checked
// (painting-to-figure); the isolated viewer at /viewer/3d/figure.html draws it, and nothing model-written runs here.
// While it is open it is the page's open 3D view (Studio.relight.active), so "save it to take home" saves a picture.
(function () {
  const t = key => Studio.i18n.t('figure.' + key);
  function open(host, figure, drawing) {
    const note = document.createElement('p'); note.className = 'relight-note'; note.textContent = t('note');
    const frame = document.createElement('iframe'); frame.title = t('title');
    frame.src = '/viewer/3d/figure.html'; frame.style.cssText = 'width:100%;height:var(--study-pane,520px);border:0;border-radius:20px;background:#f7f4ee';
    // Fifteen seconds without the figure says it is still opening, not that it failed (operator:
    // on the slow link it said "cannot be shown" while the figure appeared a moment later). Only the viewer's
    // own error, or two minutes of nothing, says it failed; a figure that arrives puts the usual note back.
    const slow = setTimeout(() => { note.textContent = t('slow'); }, 15000);
    const failed = setTimeout(() => { note.textContent = t('failed'); }, 120000);
    let pending = null, timer = null, closed = false;
    const listener = event => {
      if (event.origin !== location.origin || event.source !== frame.contentWindow) return;
      if (event.data?.type === 'figure-viewer-loaded') frame.contentWindow.postMessage({type: 'figure', figure}, location.origin);
      if (event.data?.type === 'figure-ready') { clearTimeout(slow); clearTimeout(failed); note.textContent = t('note'); }
      if (event.data?.type === 'figure-error') { clearTimeout(slow); clearTimeout(failed); note.textContent = t('failed'); }
      if (event.data?.type === 'figure-snapshot' && pending) {
        const job = pending; pending = null; clearTimeout(timer);
        event.data.blob instanceof Blob ? job.resolve(event.data.blob) : job.reject(new Error('Empty snapshot'));
      }
    };
    window.addEventListener('message', listener);
    const views = document.createElement('div'); views.className = 'sketch-pair';
    const original = document.createElement('figure'), caption = document.createElement('figcaption'), img = document.createElement('img');
    caption.textContent = Studio.i18n.t('relight.original'); img.src = drawing.url; img.alt = caption.textContent;
    original.append(caption, img);
    const stage = document.createElement('figure'), label = document.createElement('figcaption'); label.textContent = t('title');
    stage.append(label, frame); views.append(original, stage);
    if (host.id === 'review-output-content') host.append(frame, note); else host.append(views, note);
    const view = {
      snapshot() {
        if (pending) return Promise.reject(new Error('Snapshot already running'));
        return new Promise((resolve, reject) => {
          pending = {resolve, reject};
          frame.contentWindow.postMessage({type: 'snapshot'}, location.origin);
          timer = setTimeout(() => { pending = null; reject(new Error('Snapshot timed out')); }, 5000);
        });
      },
      dispose() {
        if (closed) return;
        closed = true; clearTimeout(slow); clearTimeout(failed); clearTimeout(timer); pending?.reject(new Error('Viewer closed')); pending = null;
        window.removeEventListener('message', listener);
        frame.remove(); views.remove(); note.remove();   // a hidden frame would keep drawing; a note would outlive it
      },
    };
    Studio.figureView.active = view;
    if (Studio.relight) Studio.relight.active = view;
  }
  Studio.figureView = { open, active: null, close() {
    if (Studio.relight?.active && Studio.relight.active === this.active) Studio.relight.active = null;
    this.active?.dispose(); this.active = null;
  } };
})();
