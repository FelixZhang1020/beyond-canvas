// A task owns its original course, activity and pictures independently of the visible view.
(function () {
  const S = Studio;
  // One per lane: a clip being made and a conversation each remember where they began.
  function create() { let origin = null; return {
    start() { const s=S.state; origin={session:s.session,courseId:s.courseId,mode:s.mode,current:s.current,chosen:s.chosen.slice()}; },
    current() { return origin && origin.session === S.state.session ? origin : null; },
    // The task has been seen through: its result was shown where the teacher was
    // looking, or she came back for it. Nothing is left to return to.
    finish() { origin = null; },
    visible(atHome) { const o=this.current(),s=S.state; return !!o && !atHome && o.mode===s.mode && (o.mode==='book' || o.current===s.current); },
    restore() {
      const o=this.current(); if (!o) return false;
      S.state.mode=o.mode; S.state.current=o.current; S.state.chosen=o.chosen.slice(); return true;
    }
  }; }
  S.taskNavigation = create(); S.makeNavigation = create();
})();
