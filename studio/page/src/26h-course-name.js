// The class's name, edited in Lesson settings (operator). It used to have its own Course
// information box, opened by its own button, whose one real job was renaming; the box and the
// button went, and the name joined the other settings under the same Save. An ended class is never
// open here, so it cannot be renamed, as before.
window.Studio = window.Studio || {};
Studio.courseName = {
  el(id) { return document.getElementById(id); },
  // Filled each time the sheet opens. A class left unnamed was given a dated name by the studio,
  // which the page has not heard, so it is asked for rather than shown empty.
  fill() {
    const st = Studio.state, field = this.el('f-name');
    this.el('lesson-name-field').hidden = !st.session;
    if (!st.session) return;
    const courseId = st.courseId || st.session;
    field.value = (st.settings && st.settings.title) || '';
    if (field.value || !Studio.portfolio || !Studio.portfolio.api) return;
    return Promise.resolve(Studio.portfolio.api('/' + encodeURIComponent(courseId))).then(course => {
      if (course && course.title && (Studio.state.courseId || Studio.state.session) === courseId && !field.value) {
        field.value = course.title; st.settings.title = course.title;
      }
    }, () => {});
  },
  // Saved with the rest of the sheet. An empty or unchanged name leaves the class as it is.
  save() {
    const st = Studio.state, title = this.el('f-name').value.trim();
    if (!st.session || !title || title === (st.settings && st.settings.title)) return Promise.resolve(false);
    const courseId = st.courseId || st.session;
    return Studio.portfolio.api('/' + encodeURIComponent(courseId), { method: 'PATCH',
      headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ title }) }).then(() => {
      if ((Studio.state.courseId || Studio.state.session) === courseId) Studio.state.settings.title = title;
      return true;
    });
  }
};
