// Deleting the whole class, from Lesson settings (operator). Gone for good, chosen over
// a class that could be brought back, so it asks once and names what goes: the class and how many
// drawings. Whatever is still being made is stopped by the studio, not waited for. Once the studio
// has deleted it the page lets the class go and returns to the Portfolio, where it no longer is.
window.Studio = window.Studio || {};
Studio.deleteClass = {
  el(id) { return document.getElementById(id); },
  t(key, vars) { return Studio.i18n.t('deleteClass.' + key, vars); },
  init() {
    const show = () => this.sync();
    ['session', 'ended', 'drawings'].forEach(name => Studio.bus.on(name, show));
    this.el('lesson-delete').addEventListener('click', () => this.ask());
    this.el('delete-class-cancel').addEventListener('click', () => this.close(true));
    this.el('delete-class-confirm').addEventListener('click', () => this.confirm());
    show();
  },
  sync() { this.el('lesson-delete').hidden = !Studio.state.session; },
  ask() {
    const st = Studio.state;
    if (!st.session) return;
    this.pending = st.courseId || st.session;
    const courseId = this.pending, count = st.drawings.length;
    const note = title => { if (this.pending === courseId) this.el('delete-class-note').textContent = this.t('note', { title, count }); };
    note(st.settings?.title || Studio.i18n.t(st.settings?.entrance ? 'class.' + st.settings.entrance : 'menu.title'));
    // A class left unnamed has only its kind on the page; the studio gave it a dated name, and a
    // permanent deletion should say which class it is (code review).
    if (!(st.settings && st.settings.title) && Studio.portfolio && Studio.portfolio.api) {
      Promise.resolve(Studio.portfolio.api('/' + encodeURIComponent(courseId)))
        .then(course => { if (course && course.title) note(course.title); }, () => {});
    }
    this.el('delete-class-confirm').disabled = false;
    this.el('lesson-overlay').hidden = true;
    this.el('delete-class-overlay').hidden = false;
  },
  // Keeping the class goes back to Lesson settings, where the question was asked from.
  close(back) {
    this.pending = null;
    this.el('delete-class-overlay').hidden = true;
    if (back) this.el('lesson-overlay').hidden = false;
  },
  confirm() {
    const courseId = this.pending;
    if (!courseId) return this.close(false);
    this.el('delete-class-confirm').disabled = true;
    // Deleting the course closes its editor on the studio too, so the page lets go of the class
    // without asking again: nothing after the deletion can fail and leave it half-open (reviews).
    return Promise.resolve(Studio.state.transport.deleteCourse(courseId))
      .then(() => Studio.session.end({ local: true }))
      .then(() => {
        this.close(false);
        if (Studio.companion && Studio.companion.clearResult) Studio.companion.clearResult();
        if (Studio.portfolio && Studio.portfolio.actions) Studio.portfolio.actions.home();
        this.tell(this.t('done'));
      }, () => {
        this.close(true);
        this.tell(this.t('failed'));
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
    ? document.addEventListener('DOMContentLoaded', () => Studio.deleteClass.init()) : Studio.deleteClass.init();
}
