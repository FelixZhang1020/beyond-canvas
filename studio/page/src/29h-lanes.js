// Two lanes (operator): a clip, 3D model, figure or book is made beside one conversation or
// teacher review, so a twelve-minute clip no longer holds the whole class. The studio holds the same two
// lanes (MAKING in studio/classroom/classroom_model.py). Each lane has its own request, status line and way back;
// st.busy is the talk lane's, st.making names the skill being made. Stop is offered only where a lane's
// task began: pressed anywhere else, it threw a clip away.
(function () {
  const S = Studio, st = S.state;
  const MAKING = ['painting-to-animation', 'painting-to-figure', 'painting-to-scene', 'sketch-to-3d', 'drawings-to-storybook', 'book-pictures'];
  const talk = { name: 'talk', status: S.taskStatus, nav: S.taskNavigation, epoch: 0 };
  const make = { name: 'make', status: S.makeStatus, nav: S.makeNavigation, epoch: 0 };
  S.lanes = {
    talk, make,
    of(skill) { return MAKING.includes(skill) ? make : talk; },
    busy(lane) { return lane === make ? !!st.making : st.busy; },
    // The lane the big button speaks for in the tab the teacher is on.
    here() { return ['move', 'book'].includes(st.mode) ? make : talk; },
    visible(lane, atHome) { const nav = (lane || talk).nav; return nav ? nav.visible(atHome) : !atHome; },
    // A lane whose task began somewhere the teacher is not looking; the clip first, being the longer.
    away(atHome) { return [make, talk].find(lane => lane.nav?.current() && !this.visible(lane, atHome)) || null; },
    begin(lane, skill, kind) {
      if (lane === talk) { st.busy = true; st.draft = null; } else st.making = skill;
      lane.pending = null; lane.skill = skill; lane.kind = kind; lane.since = Date.now(); clearInterval(lane.ticking);
      if (lane === talk) st.runSince = lane.since;
      lane.nav?.start(); lane.status?.start(skill + (kind ? '.' + kind : ''));
      return ++lane.epoch;
    },
    end(lane) {
      if (lane === talk) { st.busy = false; st.draft = null; } else st.making = null;
      clearInterval(lane.ticking); lane.active = null;
      return lane;
    },
    // Stop one lane's run; with no lane, both, as leaving the class or starting another does.
    stop(lane, atHome, finish) {
      if (!lane) { this.stop(talk, atHome, finish); this.stop(make, atHome, finish); return; }
      if (!this.busy(lane)) return;
      const seen = lane === talk || this.visible(lane, atHome), stopped = S.i18n.t('act.stopped');
      lane.epoch++; lane.status?.update({ status: 'cancelled' });
      if (lane.active) lane.active.abort();
      if (S.creation?.owns(lane.skill)) S.creation.stopped();
      if (seen) S.companion.cancelSteps();
      finish(lane);
      const box = document.getElementById('teacher-review-status');
      if (lane === talk && st.mode === 'teacher') { box.hidden = false; box.textContent = stopped; }
      if (seen) S.companion.say(stopped);
    },
    // What the lane is doing, counted upward. While the Spark makes a clip its quick writer steps aside
    // for it, and the conversation is written by Step 3.7 Flash, slower; the teacher is told why. A clip
    // made online (Wan 3.0) takes nothing from the Spark, and nothing is slower.
    line(lane) {
      const t = (key, vars) => S.i18n.t(key, vars);
      const sparkClip = st.making === 'painting-to-animation' && make.kind !== 'online';
      return (lane.status ? lane.status.line() : t('act.busyFor', { s: Math.round((Date.now() - lane.since) / 1000) }))
        + (lane === talk && sparkClip ? ' · ' + t('act.slowerWhileMaking') : '');
    }
  };
})();
