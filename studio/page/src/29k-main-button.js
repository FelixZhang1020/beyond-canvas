// The one big button and everything that follows the class's state: which words it says, what is enabled, which
// panel shows. Moved out of 30-main.js when that file was 780 lines against the 500 limit and the
// size guard refused any change to it; the page's own state stays there, and this asks for it (S.main).
(function () {
  const $ = function (id) { return document.getElementById(id); }, S = Studio, st = S.state, lanes = S.lanes;
  const t = function (k, v) { return S.i18n.t(k, v); }, main = function () { return S.main; };   // 30-main.js
  S.mainButton = {
    update: function () {
      const changingClass = main().changing(), taskVisible = main().taskVisible;
      if (!main().atHome() && st.session && S.portfolio.showWorkspace) {
        S.portfolio.showWorkspace({ id: st.courseId, title: st.settings.title,
          entrance: st.settings.entrance }, 'create');
      }
      S.sketchWorkbench.refresh();
      const d = S.session.currentDrawing(), btn = $('btn-primary'), label = $('primary-text');
      const picked = st.chosen.length;
      let key = st.mode === 'teacher' ? ((st.teacherReviews || {})[d?.id] ? 'teacher.regenerate' : 'teacher.generate') : st.mode === 'feedback' ? 'act.feedback' : st.mode === 'move' ? (st.settings.entrance === 'sketch' ? (S.sketchWorkbench.hasModelFor === d?.id ? 'cloud3d.regenerate' : 'act.toy') : 'act.animate')
        : (picked >= 2 ? 'act.bookPicked' : 'act.needtwo');
      // The teacher is the gate and can call a halt at any moment, so while a run
      // is going the one big button is how she stops it. It used to go grey and
      // say "working", which left no way out but ending the class. Only where the
      // run began, though: elsewhere it says the work is going on, and does nothing.
      if (st.mode === 'feedback' && d && st.feedback[d.id]) key = 'edit.continue';
      if (st.mode === 'move' && st.settings.entrance !== 'sketch') key = 'edit.generate';
      if (st.mode === 'move' && st.settings.entrance === 'sketch' && S.sketchWorkbench.active) key = 'cloud3d.regenerate';
      const lane = lanes.here(), working = lanes.busy(lane), stopHere = working && taskVisible(lane);
      if (working) key = stopHere ? 'act.stop' : lane === lanes.make ? 'act.elsewhere.make' : 'act.elsewhere.talk';
      label.textContent = st.mode === 'book' && key === 'act.bookPicked'
        ? t(key, { n: picked }) : t(key);
      btn.disabled = changingClass || (working ? !stopHere : (st.mode === 'book' ? picked < 2 : !d));
      btn.className = 'btn primary';
      $('primary-icon').setAttribute('href', stopHere ? '#i-stop' : st.mode === 'feedback' ? '#i-chat' : st.mode === 'book' ? '#i-book' : '#i-spark');
      $('app').dataset.mode = st.mode;
      const chatting = st.mode === 'feedback' && !!d;
      $('ask').hidden = !chatting;
      $('heard').hidden = !chatting;
      $('answer').hidden = true;
      $('btn-next').hidden = true;
      btn.hidden = chatting && !!st.feedback[d.id] && !st.busy;
      $('heard-text').disabled = st.busy || changingClass;
      $('btn-listen').disabled = st.busy || changingClass;
      $('heard').querySelector('[type="submit"]').disabled = st.busy || changingClass;

      const moveTab = $('mode').querySelector('[data-mode="move"]');
      const moveLabel = st.settings.entrance === 'sketch' ? 'mode.move' : 'mode.pose';
      if (moveTab.dataset.t !== moveLabel || moveTab.textContent !== t(moveLabel)) {
        moveTab.dataset.t = moveLabel; moveTab.textContent = t(moveLabel);
        if ($('mode').refresh) $('mode').refresh();
      }
      const topic = st.settings.entrance === 'sketch' && !['book', 'teacher'].includes(st.mode) ? 'sketch' : st.mode;
      const teacherReview = (st.teacherReviews || {})[d?.id];
      $('teacher-review-panel').hidden = st.mode !== 'teacher';
      $('teacher-review-panel').dataset.state = st.busy && lanes.talk.skill === 'teacher-review' ? 'loading' : teacherReview ? 'ready' : 'empty';
      $('teacher-review-generate').querySelector('span').textContent = label.textContent;
      $('teacher-review-generate').disabled = btn.disabled;
      const teacherText = teacherReview?.text || t('teacher.empty');
      const reviewKey = (d?.id || '') + '|' + teacherText, reviewBox = $('teacher-review-text'); if (reviewBox.dataset.key !== reviewKey) { reviewBox.textContent = teacherText; reviewBox.scrollTop = 0; reviewBox.dataset.key = reviewKey; }
      $('empty-title').textContent = t(st.mode === 'teacher' ? 'teacher.emptyTitle' : 'empty.title');
      $('empty-body').textContent = t(st.mode === 'teacher' ? 'teacher.emptyBody' : 'empty.body');
      $('buddy').setAttribute('aria-label', t(st.mode === 'teacher' ? 'mode.teacher' : 'companion.label'));
      $('mode-intro').textContent = st.mode === 'feedback' ? '' : t('mode.intro.' + topic);
      $('piece-title').textContent = t('picture.title.' + topic);
      $('piece-hint').textContent = t('picture.hint.' + topic);
      if (st.mode === 'move' && !$('sketch-workbench').hidden) S.sketchWorkbench.syncHeading();
      $('picture-index').textContent = d ? t('picture.index', { n: st.drawings.indexOf(d) + 1 }) : '';
      $('piece-title').parentElement.hidden = !d;
      const showExtra = st.mode === 'move' && !st.making && !!d;
      $('extra-scene').hidden = !showExtra || st.settings.entrance === 'sketch' || $('extra-scene').dataset.unbuilt === '1';
      $('cloud3d-choice').hidden = true;
      const meshSelect=$('cloud3d-model'), meshModels=st.capabilities?.mesh_models;
      if(meshModels?.length) {
        const previous=meshSelect.value, signature=JSON.stringify([st.session,meshModels,S.i18n.lang]);
        if(meshSelect.dataset.models!==signature) {
          meshSelect.replaceChildren();
          const automatic=document.createElement('option');automatic.value='auto';automatic.textContent=t('cloud3d.auto');meshSelect.append(automatic);
          for(const model of meshModels) {const option=document.createElement('option');option.value=model.id;option.textContent=[...new Set([model.label,model.provider,model.location,t('deployment.check.'+(model.status || 'unknown'))].filter(Boolean))].join(' · ');meshSelect.append(option);}
          if(previous==='auto'||meshModels.some(m=>m.id===previous)) meshSelect.value=previous;
          meshSelect.dataset.models=signature;
        }
        if (st.mode==='move' && st.settings.entrance==='sketch') meshSelect.value='trellis2';
      }
      const selectedMesh=meshModels?.find(m=>m.id===(meshSelect.value==='auto'?'trellis2':meshSelect.value));
      $('cloud3d-model-status').textContent=selectedMesh?.reason ? t('deployment.reason.'+selectedMesh.reason) : '';
      meshSelect.disabled = !!st.making || changingClass;
      if(!st.making && st.mode==='move' && st.settings.entrance==='sketch' && meshModels?.length && (!selectedMesh || main().meshBlocked())) btn.disabled=true;
      $('motion-editor').hidden = st.mode !== 'move' || st.settings.entrance === 'sketch' || !d;
      $('motion-hint').disabled = !!st.making || changingClass;
      if (d && document.activeElement !== $('motion-hint')) $('motion-hint').value = st.motionDrafts[d.id] ?? st.said[d.id] ?? '';
      $('extra-toy').hidden = true; // Sketch reconstruction is the primary action of the sketch move mode.
      $('mode').querySelectorAll('button').forEach(function (button) { button.disabled = changingClass; });
      $('thumbs').querySelectorAll('button').forEach(function (button) { button.disabled = st.busy || changingClass; });
      ['btn-upload', 'btn-camera', 'btn-sample', 'btn-add-drawing', 'empty-upload', 'empty-camera', 'empty-sample'].forEach(function (id) {
        $(id).disabled = st.busy || changingClass || !st.session;
      });
      ['btn-home', 'btn-back'].forEach(function (id) { $(id).disabled = changingClass; });
      $('btn-end-course').hidden = !st.session;
      $('btn-end-course').disabled = changingClass;
      $('btn-lesson').disabled = st.busy || !!st.making || changingClass;
      if (S.creation) S.creation.render();
      main().showTaskReturn();
    }
  };
})();
