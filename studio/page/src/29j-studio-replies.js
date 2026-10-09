// What the studio sends back while a skill runs, and what the page does with each step. Moved out of 30-main.js
// when that file was 780 lines against the 500 limit and the size guard refused any change to it; the
// page's own state stays there, and this asks for it (S.main).
(function () {
  const $ = function (id) { return document.getElementById(id); }, S = Studio, st = S.state, lanes = S.lanes;
  const t = function (k, v) { return S.i18n.t(k, v); }, main = function () { return S.main; };   // 30-main.js
  S.studioReplies = {
    take: function (skill, ev, drawing) {
      const media = !['art-feedback', 'teacher-review'].includes(skill), lane = lanes.of(skill);
      const taskVisible = main().taskVisible, finish = main().finish;
      lane.status?.update(ev);
      if (skill === 'sketch-to-3d' && !['done','stopped'].includes(ev.status))
        S.sketchWorkbench.generationTick(lanes.line(lane));
      if (ev.ledger) { ev.ledger.request_id = ev.ledger.request_id || ev.request_id; S.session.appendLedger(ev.ledger); }
      if (ev.status === 'running' && ev.partial) {
        if (ev.partial.text !== undefined) S.textStream.partial(skill, ev.partial, drawing, taskVisible(), ev.name || ev.stage);   // 29g-text-stream.js
        if (ev.partial.percent !== undefined) S.media.queue(ev.stage, 'running', ev.partial);
        if (ev.partial.bridge !== undefined && taskVisible()) S.companion.bridge(ev.partial.bridge, drawing && drawing.id);
        return;
      }
      if (ev.stage) { if (taskVisible(lane)) S.companion.step(ev.stage, ev.status); if (media) S.media.queue(ev.stage, ev.status); }
      if (ev.status === 'stopped') {
        // A clip's description still refused after its tries comes with advice, never an error line to the teacher.
        const advice = ev.review_failed && ev.candidate?.skill === 'scene-description' && ev.message;
        const failure = advice || (lane.status ? lane.status.failure(ev) : ev.message || t('msg.unavailable'));
        if (skill === 'sketch-to-3d' && taskVisible(lane)) S.sketchWorkbench.generationFailed(failure);
        if (skill === 'teacher-review' && taskVisible(lane)) { $('teacher-review-status').hidden = false; $('teacher-review-status').textContent = failure; }
        if (S.creation?.owns(skill)) S.creation.stopped(failure, ev.review_failed ? ev.candidate : null, ev.review_failed ? ev.issues : null, !!advice);
        else if (!taskVisible(lane)) lane.pending={skill,ev:{status:'stopped',reason_code:ev.reason_code,message:ev.message},drawing};   // worded once, on return
        if (taskVisible(lane)) { S.companion.say(failure); S.companion.els.next.hidden = false; lane.nav?.finish(); }
        finish(lane); return;
      }
      if (ev.status !== 'done') return;
      const out = ev.outputs || {}, d = drawing;
      st.results[skill] = out;
      if (S.creation && S.creation.owns(skill)) {
        S.creation.completed(skill, out, d);
        if (taskVisible(lane)) lane.nav?.finish();
        finish(lane);
        return;
      }
      if (skill === 'teacher-review') { st.teacherReviews = st.teacherReviews || {}; st.teacherReviews[d.id] = out; }
      if (!taskVisible(lane)) { lane.pending={skill,ev:{status:'done',outputs:out},drawing}; finish(lane); return; }
      lane.nav?.finish();
      if (skill === 'teacher-review') {
        S.companion.clearResult(); S.companion.say('');
        $('teacher-review-status').hidden = true;
        $('teacher-review-text').textContent = out.text || '';
        $('teacher-review-panel').scrollTop = $('teacher-review-text').scrollTop = 0;
        $('buddy-dialogue').scrollTop = 0;
      } else if (skill === 'art-feedback') {
        const beat = out.beat || 'opening'; S.textStream.settle(out);
        st.feedback[d.id] = beat.indexOf('rung-') === 0
          ? Object.assign({}, out, { text: (st.feedback[d.id] || {}).text || out.text, question: out.question || out.text }) : out;
        // A response can be shown with a slip on a quality rule; a red line refuses
        // outright. Either way the teacher is told, because the field existed from
        // the start and nothing read it.
        const failed = (out.rubric && out.rubric.failed) || [];
        S.companion.step('rubric', 'gate_pass', failed.length ? t('rubric.slipped', { n: failed.join(', ') }) : undefined);
        if (beat === 'opening') { st.asked[st.current] = 1; S.companion.showFeedback(out); }
        else if (beat === 'reply') S.companion.showReply(out);
        else { st.asked[st.current] = Number(beat.split('-')[1]) || 2; S.companion.showRung(out); }
      }
      else if (skill === 'drawings-to-storybook') {
        S.companion.say(out.title || t('title.book')); S.companion.sticker(t('sticker.book'));
        S.companion.offerOpen(t('open.book'), function () { S.book.open(t('title.book'), out, st.drawings); });
      } else {
        // Image edits are labelled as still previews; legacy choreography still plays.
        const kind = out.keyframe ? 'keyframe' : out.scene ? 'relight' : out.choreography ? 'motion'
          : skill === 'sketch-to-3d' ? 'turntable' : skill === 'painting-to-scene' ? 'scene' : 'video';
        const src = out.keyframe || out.scene || out.choreography || out.video_url || out.turntable_url || out.preview_url || out.glb_url;
        const title = t(kind === 'keyframe' ? 'keyframe.title' : kind === 'relight' || kind === 'turntable' ? 'title.toy' : kind === 'scene' ? 'title.scene' : 'title.video');
        if (kind === 'motion' && S.session.currentDrawing()) st.results.motion = out.choreography;
        S.companion.say(title); S.companion.sticker(t(kind === 'keyframe' ? 'keyframe.ready' : 'sticker.moved'));
        if (kind !== 'relight' || st.settings.entrance !== 'sketch')
          S.companion.offerOpen(t(kind === 'keyframe' ? 'keyframe.open' : kind === 'relight' || kind === 'turntable' ? 'open.toy' : kind === 'scene' ? 'open.scene' : 'open.video'), function () { S.media.open(title, kind, src, d); });
        if (kind === 'relight') {
          // The completion event already carries the saved scene, its model as an address of its own; the workbench
          // fetches that model once and keeps it (27g-cloud-relight.js).
          if (out.artifact_id && st.courseId) S.sketchWorkbench.remember(
            '/'+encodeURIComponent(st.courseId)+'/activities/'+encodeURIComponent(out.artifact_id),{outputs:out});
          S.sketchWorkbench.refreshLatest();
        }
        else S.media.open(title, kind, src, d);
      }
      finish(lane);
      if (S.courseHistory) S.courseHistory.refresh();
    }
  };
})();
