// Taking back what was said about the drawing on show. Asked for when a
// conversation stuck on unanswered rounds had no way out: "take back" removes the child's last
// answer and whatever the companion said after it, so the teacher can give it again; "clear"
// erases the whole conversation and waits for the teacher to start again. Both are deleted for good on the
// studio; taking back one answer also waits for the teacher. The studio refuses either while
// the companion is still answering, and the page only says which refusal it was.
window.Studio = window.Studio || {};
Studio.chatEdit = {
  el(id) { return document.getElementById(id); },
  t(key) { return Studio.i18n.t('chatEdit.' + key); },
  init() {
    const show = () => this.sync();
    ['current', 'drawings', 'session', 'ended'].forEach(name => Studio.bus.on(name, show));
    // The column is redrawn after every round, which is when there is newly something to take back.
    new MutationObserver(show).observe(this.el('history-messages'), { childList: true });
    this.el('btn-chat-undo').addEventListener('click', () => this.undo());
    this.el('btn-chat-clear').addEventListener('click', () => this.ask());
    this.el('chat-clear-cancel').addEventListener('click', () => this.close());
    this.el('chat-clear-confirm').addEventListener('click', () => this.confirm());
    show();
  },
  sync() {
    const st = Studio.state, id = st.current;
    const said = !!(id && st.said && st.said[id]), spoken = !!(id && st.feedback && st.feedback[id]);
    this.el('btn-chat-undo').hidden = !said;
    this.el('btn-chat-clear').hidden = !(said || spoken);
    this.el('chat-edit').hidden = !(st.session && id && (said || spoken));
  },
  undo() {
    const st = Studio.state, id = st.current;
    if (!st.session || !id) return;
    if (st.busy) return this.tell(this.t('busy'));
    return Studio.session.forgetChat(id, 'last-round').then(done => {
      if (!done || Studio.state.current !== id) return;
      this.redraw();
      Studio.companion.restoreFeedback(Studio.state.feedback[id], '');
      Studio.companion.openHeard();
      this.tell(this.t('undone'));
    }, error => this.refused(error));
  },
  ask() {
    const st = Studio.state;
    if (!st.session || !st.current) return;
    if (st.busy) return this.tell(this.t('busy'));
    this.pending = st.current;
    this.el('chat-clear-confirm').disabled = false;
    this.el('chat-clear-overlay').hidden = false;
  },
  close() { this.pending = null; this.el('chat-clear-overlay').hidden = true; },
  confirm() {
    const id = this.pending;
    if (!id) return this.close();
    this.el('chat-clear-confirm').disabled = true;
    return Studio.session.forgetChat(id, 'conversation').then(done => {
      this.close();
      if (!done || Studio.state.current !== id) return;
      this.redraw();
      Studio.companion.restoreFeedback(undefined);
      this.tell(this.t('cleared'));
    }, error => { this.close(); this.refused(error); });
  },
  // Words still pending on screen belonged to the round just erased.
  redraw() {
    Studio.courseHistory.said = null;
    Studio.courseHistory.clearDraft();
    Studio.bus.emit('drawings'); Studio.bus.emit('current', Studio.session.currentDrawing());
  },
  refused(error) {
    const known = { drawing_busy: 'busy', nothing_to_undo: 'nothing', course_closed: 'closed' }[error && error.code];
    this.tell(this.t(known || 'failed'));
  },
  tell(text) {
    const toast = this.el('toast');
    toast.textContent = text; toast.hidden = false;
    clearTimeout(this.timer); this.timer = setTimeout(() => { toast.hidden = true; }, 2600);
  }
};
if (typeof document !== 'undefined' && document.addEventListener) {
  document.readyState === 'loading'
    ? document.addEventListener('DOMContentLoaded', () => Studio.chatEdit.init()) : Studio.chatEdit.init();
}
