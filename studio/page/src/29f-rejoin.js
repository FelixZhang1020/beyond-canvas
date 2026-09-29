// A class the studio has forgotten, picked up again.
//
// The studio keeps ONE editor per course: opening the same course anywhere else ends the editor it
// replaces (Classroom.edit_course), and the page that lost its editor is never told. It finds out
// from its next call, which comes back `session_gone` — and that used to be a dead end.
// The message said "return to the course and submit again", and returning did nothing: the page saw
// the course it was already on, resumed from its own memory, and sent the id the studio had
// forgotten. A teacher pressed three times in ninety seconds that afternoon and was refused each
// time. A photograph, a recording or a saved draft in the same window fared no better.
//
// So the page takes the course back itself and asks for the last thing to be done once more. It
// never repeats the call: what a model is spent on is the teacher's to decide
// (operator), and a photograph the studio never received is not the page's to send again.
(function () {
  const S = Studio, st = S.state, t = key => S.i18n.t(key);
  let rejoining = false;
  // Her words win over the stored ones, and only where she has written something: the course may
  // have been reopened in the other window and hold a draft this one never saw, which is not ours
  // to erase.
  function restoreTyping(typed, described) {
    Object.keys(typed).forEach(function (id) { if (String(typed[id] || '').trim()) st.drafts[id] = typed[id]; });
    Object.keys(described).forEach(function (id) { if (String(described[id] || '').trim()) st.motionDrafts[id] = described[id]; });
    // Saving is often how the page found out at all. It goes to the new editor now; a second
    // failure is not worth a second rejoin, because the words are on her screen either way.
    if (st.transport.saveDrafts && st.session) {
      Promise.resolve(st.transport.saveDrafts(st.session, st.drafts)).catch(function () {});
    }
  }
  // The same rule for what she picked and what she wrote in the storybook. restore() empties the
  // selection and replaces the outline with the course's saved one, which is older than her screen.
  // Only the typed words used to come back, so a teacher who had edited an outline and
  // chosen her pictures lost both at the moment the studio asked her to submit again -- the one
  // moment she was certain to be in the middle of something.
  function restoreChoosing(picked, story) {
    // Only pictures the course still has: the other window may have removed one, and choosing a
    // picture that is no longer there would fail on the next press for a reason she cannot see.
    const here = st.drawings.map(function (drawing) { return drawing.id; });
    const kept = picked.filter(function (id) { return here.indexOf(id) >= 0; });
    if (kept.length) st.chosen = kept;
    if (story && story.pages) st.storyDraft = story;
  }
  S.rejoin = {
    // True while the class is being taken back. The creation panel refuses a press meanwhile, for
    // the same reason it refuses one during a task: the press would go to the wrong class.
    get busy() { return rejoining; },
    // `quiet`: the caller sends the teacher's words again itself (23-transport-http.js), so a class
    // taken back says nothing; one that could not be taken back still says to reload.
    async start(opts = {}) {
      const courseId = st.courseId, lost = st.session, drawingId = st.current, mode = st.mode;
      if (rejoining || !courseId || !lost || !st.transport || !st.transport.editCourse) return false;
      rejoining = true;
      // What she has typed and the studio has not stored yet. restore() fills both from the course,
      // which is older than what is on her screen, so hers go back on top afterwards.
      const typed = Object.assign({}, st.drafts), described = Object.assign({}, st.motionDrafts);
      const picked = (st.chosen || []).slice(), story = st.storyDraft;
      const pictures = st.drawings.slice();
      let said = 'task.session_gone', took = false, moved = false;
      try {
        const payload = await st.transport.editCourse(courseId, false);
        // She may have moved on while we were asking — gone home, opened another course. Taking
        // this one back now would pull her out of wherever she went, so let go of the editor we
        // just opened instead, and say nothing at all.
        if (st.session !== lost || st.courseId !== courseId) {
          moved = true;
          if (st.transport.forgetSession) {
            Promise.resolve(st.transport.forgetSession(payload.session_id)).catch(function () {});
          }
        } else {
          st.session = null;
          S.session.restore(payload);
          restoreTyping(typed, described);
          restoreChoosing(picked, story);
          if (drawingId && st.drawings.some(function (d) { return d.id === drawingId; })) S.session.select(drawingId);
          // restore() lands every class on the first picture in the feedback view. The teacher was
          // somewhere else, and being moved is its own small loss.
          st.mode = mode;
          const modes = document.getElementById('mode');
          if (modes && modes.select) modes.select(mode, 'mode');
          said = 'task.rejoined'; took = true;
          // Last, because the class is already back: letting go of the lost editor's pictures is
          // tidying, and tidying that goes wrong must not report the rejoin as a failure.
          pictures.forEach(function (picture) { S.session.releaseUrl(picture.url); });
        }
      } catch (error) {
        // The course was ended, or the studio is unreachable. Reloading is the way out and the
        // message says so, instead of leaving "the server did not accept the task" standing.
      }
      rejoining = false;
      if (moved) return false;
      S.bus.emit('capabilities');
      if (opts.quiet && took) return took;
      if (S.creation) { S.creation.stopped(t(said)); S.creation.render(); }
      if (S.companion) S.companion.say(t(said));
      return took;
    }
  };
})();
