// Deleting the drawing on show, from the strip of today's drawings. Asked for to remove a
// wrong photograph or a duplicate. It cannot be undone, so it asks once, and the studio decides
// whether it may: never while something is still being made from the drawing, never for a drawing
// a book shares. The page only says which of those it was.
window.Studio = window.Studio || {};
Studio.removeDrawing = {
  el(id) { return document.getElementById(id); },
  t(key) { return Studio.i18n.t('remove.' + key); },
  init() {
    const show = () => this.sync();
    ['current', 'drawings', 'session', 'ended'].forEach(name => Studio.bus.on(name, show));
    this.el('btn-remove-drawing').addEventListener('click', () => this.ask());
    this.el('remove-drawing-cancel').addEventListener('click', () => this.close());
    this.el('remove-drawing-confirm').addEventListener('click', () => this.confirm());
    show();
  },
  sync() {
    const st = Studio.state;
    this.el('btn-remove-drawing').hidden = !(st.session && st.current);
  },
  ask() {
    const st = Studio.state;
    if (!st.session || !st.current) return;
    if (st.busy) { this.tell(this.t('busy')); return; }
    this.pending = st.current;
    this.el('remove-drawing-confirm').disabled = false;
    this.el('remove-drawing-overlay').hidden = false;
  },
  close() { this.pending = null; this.el('remove-drawing-overlay').hidden = true; },
  confirm() {
    const id = this.pending;
    if (!id) return this.close();
    this.el('remove-drawing-confirm').disabled = true;
    return Studio.session.removeDrawing(id).then(removed => {
      this.close();
      if (removed) this.tell(this.t('done'));
    }, error => {
      this.close();
      const known = { in_book: 'inBook', drawing_busy: 'busy', course_closed: 'closed' }[error && error.code];
      this.tell(this.t(known || 'failed'));
    });
  },
  tell(text) {
    const toast = this.el('toast');
    toast.textContent = text; toast.hidden = false;
    clearTimeout(this.timer); this.timer = setTimeout(() => { toast.hidden = true; }, 2600);
  }
};
if (typeof document !== 'undefined' && document.addEventListener) {
  document.readyState === 'loading'
    ? document.addEventListener('DOMContentLoaded', () => Studio.removeDrawing.init()) : Studio.removeDrawing.init();
}
