// Words a model is still writing. The studio sends the text so far several times a second
// (studio/server/textstream.py): a teacher review shows in its own panel, a scene or story in the
// planner (operator). The companion's words in the chat do not: they arrive whole
// once they have passed the rules, like a message in a chat, and until then the thread shows
// the companion typing (operator). Nothing here is spoken; only the checked result
// is. Kept apart from 30-main.js, which is over the 500-line limit.
(function () {
  const S = Studio, st = S.state, $ = id => document.getElementById(id);
  S.textStream = {
    partial(skill, p, drawing, visible, stage) {
      if (S.creation && S.creation.owns(skill)) { S.creation.preview(p.text, stage); return; }
      if (skill === 'teacher-review') {
        // Written into the panel's own box; the finished review replaces it, a stop puts back the saved one.
        if (visible) { const box = $('teacher-review-text'); box.textContent = p.text; box.classList.add('streaming'); }
        return;
      }
      // Only that it is writing, or checking, and about which drawing: never the words themselves.
      st.draft = skill === 'art-feedback' ? { drawing: drawing && drawing.id, writing: !!p.writing } : null;
      if (visible) st.draft ? S.companion.checking(st.draft, st.runSince) : S.companion.say(p.text, { typing: true });
    },
    // The checked words have arrived: they join the thread whole, where the typing was.
    settle(out) { if (S.courseHistory) S.courseHistory.settleDraft(out.text, out.question); },
    // A request ended. The typing goes; the review panel shows the saved review again.
    drop() {
      S.companion.dropDraft();
      const box = $('teacher-review-text');
      if (box && box.classList.contains('streaming')) { box.classList.remove('streaming'); box.dataset.key = ''; }
      if (S.creation && S.creation.preview) S.creation.preview('');
    }
  };
})();
