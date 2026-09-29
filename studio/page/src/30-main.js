// Wiring: transport choice, the class sheet, photos in, the three scenarios, and the overlays.
(function () {
  const $ = function (id) { return document.getElementById(id); }, S = Studio, st = S.state, t = function (k, v) { return S.i18n.t(k, v); };
  let atHome = true, lessonFromHome = true, changingClass = false, pendingEntrance = null, lessonAtOpen = '';
  let startingFresh = false, pendingCompletion = null;
  const lanes = S.lanes;   // 29h-lanes.js: a clip is made beside a conversation
  // What the pieces split out of this file ask for (29i-microphones.js, 29j-studio-replies.js, 29k-main-button.js):
  // the page's own state stays here, read at the moment it is needed, never copied.
  S.main = { atHome: () => atHome, changing: () => changingClass, taskVisible, showTaskReturn, finish, toast, meshBlocked };
  function taskVisible(lane) { return lanes.visible(lane, atHome); }
  function showTaskReturn() {
    const button=$('task-return'); if (!button) return;
    const lane=lanes.away(atHome); button.hidden=!lane;
    $('task-return-status').textContent=lane?.status ? lane.status.line() : '';
  }
  function returnToTask() {
    const lane=lanes.away(atHome) || lanes.talk;
    if (!lane.nav?.restore()) { resumeClass(); return; }
    resumeClass(); $('mode').select(st.mode,'mode'); renderThumbs(); updatePrimary();
    if (lane.pending) { const p=lane.pending; lane.pending=null; onEvent(p.skill,p.ev,p.drawing); }
    lane.nav.finish();
    showTaskReturn();
  }
  function chooseTransport() {
    const forced = new URLSearchParams(location.search).get('transport');
    if (forced && S.transports[forced]) return Promise.resolve(S.transports[forced]);
    if (location.protocol === 'file:') return Promise.resolve(S.transports.mock);
    return S.transports.http.health().then(function () { return S.transports.http; });
  }
  function setRoom(d) {
    $('app').dataset.hasDrawing = String(!!d);
    $('field').hidden = !!d; $('haze').hidden = !d; $('picture').hidden = !d; $('empty').hidden = !!d;
    if (d) { $('haze').style.backgroundImage = 'url("' + d.url + '")'; $('picture').style.backgroundImage = 'url("' + d.url + '")'; }
    updatePrimary();
  }
  const BOOK_MAX = 8;
  function renderThumbs() {
    const box = $('thumbs'); box.querySelectorAll('button').forEach(function (b) { b.remove(); });
    $('thumbs-empty').hidden = st.drawings.length > 0;
    st.drawings.forEach(function (d, index) {
      const b = document.createElement('button'); b.type = 'button'; b.style.backgroundImage = 'url("' + d.url + '")';
      // In book mode a thumbnail is a choice, not a cursor: the teacher picks
      // which drawings the book is about, and sees her picks.
      const chosen = st.mode === 'book' && st.chosen.indexOf(d.id) >= 0;
      b.className = st.mode === 'book' ? (chosen ? 'on picked' : 'picked') : (d.id === st.current ? 'on' : '');
      b.setAttribute('aria-label', t('picture.index', { n: index + 1 }));
      b.setAttribute('aria-pressed', String(st.mode === 'book' ? chosen : d.id === st.current));
      b.addEventListener('click', function () {
        if (st.mode !== 'book') {
          rememberDraft(); S.session.select(d.id);
          if (st.mode === 'feedback') { S.companion.restoreFeedback(st.feedback[d.id], st.drafts[d.id]); updatePrimary(); }
          return;
        }
        const next = S.chooser.toggle(st.chosen, d.id, BOOK_MAX,
          st.drawings.map(function (x) { return x.id; }));
        if (!next) { toast(t('book.full', { n: BOOK_MAX })); return; }
        st.chosen = next; renderThumbs(); updatePrimary();
      });
      box.appendChild(b);
    });
    const n = st.drawings.length; $('count-text').textContent = n === 1 ? t('count.one') : t('count', { n: n });
  }
  function meshBlocked() { return st.capabilities?.mesh_models?.find(m=>m.id==='trellis2')?.status==='unavailable'; }
  function updatePrimary() { S.mainButton.update(); }   // 29k-main-button.js
  function addPhoto(blob, sessionId) {
    const id = sessionId === undefined ? st.session : sessionId;
    if (changingClass) return Promise.resolve(null);
    return S.photos.importDrawing(blob, id).then(function (d) {
      if (!d || !S.session.isCurrent(id) || st.current !== d.id) return;
      S.companion.clearResult(); S.media.clearQueue(); S.companion.say(t('ready'));
    }).catch(function (error) {
      if (!S.session.isCurrent(id)) return;
      const message = t(error.code === 'dark_image' ? 'msg.dark' : 'msg.unavailable');
      S.companion.say(message); toast(message);
    });
  }
  const ALLOWED = { teacher: ['teacher-review'], feedback: ['art-feedback'], move: ['scene-description', 'painting-to-animation', 'painting-to-scene', 'sketch-to-3d'], book: ['story-outline', 'drawings-to-storybook', 'book-pictures'] };
  function run(skill, ids, opts) {
    const lane = lanes.of(skill), talk = lane === lanes.talk;
    if (lanes.busy(lane) || changingClass || !S.session.isCurrent(st.session) || (ALLOWED[st.mode] || []).indexOf(skill) < 0) return;
    releaseListening(); if (S.voice.stop) S.voice.stop(); if (S.voice.unlock) S.voice.unlock();
    $('app').dataset.guide = 'false';
    // An online clip has its own expected time (29b-task-status.js), the Spark's clip the media kind's.
    const epoch = lanes.begin(lane, skill, opts && opts.clip_maker === 'online' ? 'online' : opts && opts.media_kind);
    if (skill === 'sketch-to-3d') { S.sketchWorkbench.beginGeneration(); S.sketchWorkbench.generationTick(lanes.line(lane)); }
    // The companion's thinking is the conversation's: the chat's Stop and its round-end note follow it (26d).
    S.companion.clearResult(); updatePrimary(); if (talk) S.companion.think(true); else S.media.clearQueue();
    // Until the first words arrive (29g-text-stream.js) the bubble counts upward:
    // a number that moves is the difference between waiting and wondering whether
    // it broke. A media task has no words, and counts to the end.
    if (skill === 'teacher-review') { $('teacher-review-status').hidden = false; $('teacher-review-status').textContent = t('act.busy'); }
    S.companion.say(t('act.busy'), { typing: true });
    lane.ticking = setInterval(function () {
      if (!lanes.busy(lane)) { clearInterval(lane.ticking); return; }
      lane.status?.tick();
      const line = lanes.line(lane);
      if (skill === 'sketch-to-3d' && Math.floor((Date.now()-lane.since)/1000)%10===0)
        S.sketchWorkbench.generationTick(line);
      if (skill === 'teacher-review' && taskVisible(lane)) $('teacher-review-status').textContent = line;
      showTaskReturn();
      if (taskVisible(lane)) talk && st.draft ? S.companion.checking(st.draft, st.runSince) : S.companion.say(line, { typing: true });
    }, 1000);
    const drawing = st.drawings.find(function (d) { return d.id === ids[0]; });
    lane.active = st.transport.request(st.session, skill, ids, opts || {}, function (ev) {
      if (epoch === lane.epoch) onEvent(skill, ev, drawing);
    });
  }
  function finish(lane) {
    if (lanes.end(lane || lanes.talk) === lanes.talk) { S.textStream.drop(); S.companion.think(false); } updatePrimary();
  }
  function onEvent(skill, ev, drawing) { S.studioReplies.take(skill, ev, drawing); }   // 29j-studio-replies.js
  function primaryAction() {
    const lane = lanes.here();
    if (lanes.busy(lane)) { if (taskVisible(lane)) stopRun(lane); return; }
    if (S.creation && S.creation.enabled()) return;
    const d = S.session.currentDrawing();
    if (st.mode === 'teacher' && d) run('teacher-review', [d.id]);
    else if (st.mode === 'feedback' && d) {
      if (st.feedback[d.id]) { S.companion.restoreFeedback(st.feedback[d.id], st.drafts[d.id]); S.companion.openHeard(); }
      else run('art-feedback', [d.id]);
    }
    else if (st.mode === 'move' && d && !(st.settings.entrance==='sketch' && meshBlocked())) {
      if (st.settings.entrance === 'sketch') {
        const regenerate=S.sketchWorkbench.hasModelFor===d.id;
        run('sketch-to-3d',[d.id],{model_choice:regenerate?'trellis2':'auto',regenerate});
      }
      else run('painting-to-animation',[d.id],{hint:$('motion-hint').value.trim()});
    }
    else if (st.mode === 'book' && st.chosen.length >= 2) run('drawings-to-storybook', st.chosen.slice());
  }
  function stopRun(lane) { lanes.stop(lane, atHome, finish); }
  function rememberDraft() {
    if (st.current && !$('heard').hidden) st.drafts[st.current] = $('heard-text').value;
  }
  function releaseListening() { S.microphones.release(); }   // 29i-microphones.js
  function pauseInteraction(stopTask = true) {
    if (stopTask) stopRun(); releaseListening(); S.book.stop(); S.media.close(); if (S.samples) S.samples.close();
  }
  function openHome() {
    if (changingClass) return;
    if (!atHome && st.courseId && S.portfolio.selected) S.portfolio.selected[st.courseId] = st.current;
    rememberDraft(); pauseInteraction(false);
    atHome = true; $('sheet-overlay').hidden = true;
    S.portfolio.open(); updatePrimary();
  }
  function newClass() {
    if (st.busy || st.making) { toast(t('task.keepRunning')); return; }
    if (changingClass || S.portfolio.available === false) return;
    rememberDraft(); pauseInteraction(); startingFresh = true; atHome = true;
    S.portfolio.close(); S.portfolio.hideWorkspace(); $('start-name').value = ''; $('f-intent').value = ''; $('sheet-overlay').hidden = false; updatePrimary();
  }
  function resumeClass() {
    if (!st.session || changingClass) return;
    atHome = false; S.portfolio.close(); $('sheet-overlay').hidden = true; updatePrimary();
    $('mode').refresh();
  }
  async function editCourse(course, reopen, drawingId) {
    if (changingClass) return;
    if (!reopen && st.session && st.courseId === course.id) {
      if (st.busy || st.making) { returnToTask(); return; }
      if (drawingId && st.drawings.some(d => d.id === drawingId)) {
        S.session.select(drawingId);
        if (st.mode === 'feedback') S.companion.restoreFeedback(st.feedback[drawingId], st.drafts[drawingId]);
      }
      resumeClass(); S.portfolio.message(''); return;
    }
    if (st.busy || st.making) { toast(t('task.keepRunning')); return; }
    changingClass = true; rememberDraft(); pauseInteraction(); updatePrimary();
    try {
      if (st.session && !(await S.session.end())) throw new Error('Editor changed');
      const payload = await st.transport.editCourse(course.id, reopen);
      S.session.restore(payload); S.settings.remember(st.settings);
      if (drawingId && st.drawings.some(d => d.id === drawingId)) S.session.select(drawingId);
      $('f-intent').value = st.settings.lessonIntent || '';
      atHome = false; startingFresh = false; S.portfolio.close(); $('sheet-overlay').hidden = true;
      $('mode').select('feedback', 'mode'); $('app').dataset.guide = 'false';
      S.companion.restoreFeedback(st.feedback[st.current], st.drafts[st.current]);
      $('course-history').open = true;
      S.portfolio.message('');
    } finally { changingClass = false; updatePrimary(); }
  }
  function visitMode(mode, returning) {
    if (changingClass || mode === st.mode) return;
    rememberDraft(); pauseInteraction(false);
    if (!returning) st.modeHistory.push(st.mode);
    st.mode = mode; $('mode').select(mode, 'mode');
    $('app').dataset.guide = String(mode !== 'feedback');
    if (mode === 'feedback') S.companion.restoreFeedback(st.feedback[st.current], st.drafts[st.current]);
    else { S.companion.clearResult(); if (mode === 'teacher') { $('teacher-review-status').hidden = !(st.busy && lanes.talk.skill === 'teacher-review'); S.companion.say(''); $('buddy-dialogue').scrollTop = 0; } }
    renderThumbs(); updatePrimary();
  }
  function backToQuestion() {
    rememberDraft(); releaseListening();
    $('heard').hidden = true; $('answer').hidden = false; $('btn-answered').focus();
  }
  function goBack() {
    if (changingClass) return;
    // The persistent composer is not a navigation step.
    if (st.modeHistory.length) { visitMode(st.modeHistory.pop(), true); return; }
    if (st.mode !== 'feedback') { visitMode('feedback', true); return; }
    openHome();
  }
  // Beat four: the child answered and the teacher typed it. Their words go to
  // the skill and are saved with this course after teacher confirmation.
  function sendWhatTheySaid(e) {
    e.preventDefault();
    const d = S.session.currentDrawing(), said = $('heard-text').value.trim();
    if (!d || !said || st.busy || changingClass) return;
    st.said[d.id] = said;
    delete st.drafts[d.id];
    // The recording this answer was heard from, if it was said about this drawing (29i-microphones.js).
    const h = st.heardSample; st.heardSample = null;
    run('art-feedback', [d.id], h && h.drawing === d.id ? { transcript: said, sample: h.id } : { transcript: said });
  }
  // Beat three: the child said nothing, so ask smaller rather than louder.
  function askSmaller() {
    const d = S.session.currentDrawing(), rung = S.nextRung(st.asked[st.current]);
    if (!d || rung === null) return;
    run('art-feedback', [d.id], { rung: rung });
  }
  // Hide every control whose skill the studio does not serve. With no list from
  // the studio, everything stays visible: an older harness is not a broken one.
  function offerOnly(skills) {
    if (S.creation) S.creation.configure(skills);
    if (!skills || !skills.length) return;
    const has = function (name) { return skills.indexOf(name) >= 0; };
    $('extra-scene').dataset.unbuilt = has('painting-to-scene') ? '' : '1';
    $('extra-toy').dataset.unbuilt = has('sketch-to-3d') ? '' : '1';
    const move = $('mode').querySelector('[data-mode="move"]');
    const book = $('mode').querySelector('[data-mode="book"]');
    if (move && !has('painting-to-animation') && !has('sketch-to-3d')) move.hidden = true;
    if (book && !has('drawings-to-storybook')) book.hidden = true;
    updatePrimary();
  }
  // The next child's turn ends the conversation, never the clip still being made for the last one.
  function nextChild() {
    stopRun(lanes.talk); pauseInteraction(false); finish(); st.current = null;
    S.companion.clearResult(); if (!st.making) S.media.clearQueue();
    S.companion.say(t('greet')); S.bus.emit('current', null); S.bus.emit('drawings');
  }
  // The tap on a card is what starts the class: the entrance is the only thing
  // the opening asks, and it is never carried over from the last class.
  function beginClass(entrance, confirmed, saveDrafts) {
    if (st.busy || st.making) { toast(t('task.keepRunning')); return; }
    if (!st.transport || changingClass || S.portfolio.available === false) return;
    if (!startingFresh && st.session && entrance === st.settings.entrance) { resumeClass(); return; }
    if (st.session && st.drawings.length && !confirmed) {
      pendingEntrance = entrance;
      $('switch-class-title').textContent = t('class.switchTo', { kind: t('class.' + entrance) });
      $('sheet-overlay').hidden = true; $('switch-class-overlay').hidden = false;
      return;
    }
    changingClass = true; updatePrimary();
    document.querySelectorAll('.pick').forEach(function (card) { card.disabled = true; });
    const settings = { language: S.i18n.lang, lessonIntent: $('f-intent').value.trim(),
      entrance: entrance, title: $('start-name').value.trim() };
    S.settings.remember(settings);
    const ended = st.session ? S.session.end({ saveDrafts: !!saveDrafts }) : Promise.resolve(true);
    ended.then(function (cleared) { return cleared && !st.session ? S.session.begin(settings) : null; })
      .then(function (id) {
        if (!S.session.isCurrent(id)) return;
        atHome = false; startingFresh = false; S.portfolio.close(); $('sheet-overlay').hidden = true; $('mode').select('feedback', 'mode');
        S.portfolio.message('');
        $('app').dataset.guide = 'false'; S.companion.clearResult(); S.companion.say(t('greet'));
        renderThumbs(); updatePrimary();
      })
      .catch(function () { toast(t('class.failed')); })
      .finally(function () { changingClass = false; updatePrimary(); document.querySelectorAll('.pick').forEach(function (card) { card.disabled = false; }); });
  }
  // One panel at a time: the principles allow a single layer of glass, so the
  // opening steps aside rather than sitting under this one. The segmented pill
  // is re-measured on the way in, because a control laid out while its panel is
  // hidden has no width to measure and the pill lands beside its own label.
  function openLesson() {
    lessonFromHome = atHome; lessonAtOpen = $('f-intent').value;
    $('sheet-overlay').hidden = true;
    $('lesson-overlay').hidden = false; S.courseName.fill();
    document.querySelectorAll('.seg').forEach(function (seg) { if (seg.refresh) seg.refresh(); });
  }
  function syncSettings(language) {
    const settings = { language: language, lessonIntent: $('f-intent').value.trim() };
    const sid = st.session;
    const work = sid && st.transport.updateSettings ? st.transport.updateSettings(sid, settings) : Promise.resolve();
    return work.then(function () {
      if (st.session !== sid) return;
      Object.assign(st.settings, settings); S.settings.remember(settings);
      if (S.voice.stop) S.voice.stop();
    });
  }
  function saveLesson(e) {
    e.preventDefault();
    Promise.all([syncSettings(S.i18n.lang), S.courseName.save()]).then(function () {
      $('lesson-overlay').hidden = true; $('sheet-overlay').hidden = !lessonFromHome; updatePrimary();
    }).catch(function () { toast(t('msg.unavailable')); });
  }
  function closeLesson() {
    $('f-intent').value = lessonAtOpen;   // what it held before this visit, unsaved edits dropped
    $('lesson-overlay').hidden = true;
    $('sheet-overlay').hidden = !lessonFromHome;
  }
  function confirmCourseCompletion(courseId) {
    if (changingClass || !courseId) return;
    pendingCompletion = courseId;
    $('end-class-status').textContent = '';
    $('end-class-overlay').hidden = false;
  }
  function endClass() {
    const courseId = pendingCompletion;
    if (changingClass || !courseId) return;
    changingClass = true;
    $('end-class-status').textContent = t('end.saving');
    $('end-class-confirm').disabled = true; $('end-class-cancel').disabled = true;
    pauseInteraction(); updatePrimary();
    const current = st.session && (st.courseId || st.session) === courseId;
    const work = current ? S.session.end({ complete: true }) : st.transport.completeCourse(courseId).then(function () { return true; });
    let completed = false;
    work.then(async function (cleared) {
      if (!cleared) throw new Error('Course completion was not confirmed');
      completed = true;
      $('end-class-overlay').hidden = true; pendingCompletion = null;
      toast(t('end.done')); atHome = true;
      if (current) { S.companion.clearResult(); setRoom(null); $('mode').select('feedback', 'mode'); }
      changingClass = false;
      await S.portfolio.openCourse(courseId);
    }).catch(function () {
      if (completed) { S.portfolio.message('failed', true); return; }
      $('end-class-status').textContent = t('end.failed');
    }).finally(function () {
      changingClass = false;
      $('end-class-confirm').disabled = false; $('end-class-cancel').disabled = false;
      updatePrimary();
    });
  }
  function toast(text) { const el = $('toast'); el.textContent = text; el.hidden = false; setTimeout(function () { el.hidden = true; }, 2600); }
  function extraButton(id, key, skill) {
    const b = document.createElement('button'); b.type = 'button'; b.className = 'btn magic'; b.id = id; b.hidden = true;
    b.innerHTML = '<span></span>'; b.firstChild.textContent = t(key); b.firstChild.dataset.t = key;
    b.addEventListener('click', function () { const d = S.session.currentDrawing(); if (d) run(skill, [d.id]); });
    $('buddy-actions').prepend(b);
  }
  function boot() {
    $('task-return').onclick=returnToTask;
    if (S.creation) S.creation.init({run: run, stop: function (skill) { if (skill) stopRun(lanes.of(skill)); }, chosen: renderThumbs, active: function () { return !atHome && !changingClass; }, open: function (result) {
      const out = result.out;
      if (result.skill === 'drawings-to-storybook') S.book.open(t('title.book'), out, st.drawings);
      else {
        const kind = out.keyframe ? 'keyframe' : out.choreography ? 'motion' : 'video';
        S.media.open(t(kind === 'keyframe' ? 'keyframe.title' : 'title.video'), kind,
          out.keyframe || out.choreography || out.video_url, result.drawing);
      }
    }});
    S.glass.init($('app'));
    S.dialogs.init($('app'));
    extraButton('extra-toy', 'act.toy', 'sketch-to-3d'); extraButton('extra-scene', 'act.scene', 'painting-to-scene');
    // The labels are written into the markup by the page build, so the studio
    // already reads correctly before this runs. This is for the title, the aria
    // labels and the boxes' examples, which no build step can place.
    S.i18n.apply();
    S.companion.init();
    S.portfolio.init({ newClass: newClass, home: openHome, editCourse: editCourse, completeCourse: confirmCourseCompletion });
    if (S.courseHistory) S.courseHistory.init();
    S.bus.on('edit-pose', function (id) {
      if (st.busy || changingClass) return;
      rememberDraft(); S.session.select(id); visitMode('move', false);
      $('motion-hint').focus();
    });
    if (S.voice.init) S.voice.init();
    // Only the language carries over from the last class (21-state.js): nothing here preselects an
    // entrance or fills in a lesson note.
    document.querySelectorAll('.pick').forEach(function (card) { card.disabled = true; });
    chooseTransport().then(function (tr) {
      st.transport = tr; if (S.deployments) S.deployments.init(); $('chip-mock').hidden = tr.name !== 'mock';
      document.querySelectorAll('.pick').forEach(function (card) { card.disabled = false; });
      // Only offer what this studio can actually do. A button that always comes
      // back "that part is not open yet" is worse than no button.
      return tr.health().then(function (health) {
        offerOnly(health && health.skills); if (S.voice.configure) S.voice.configure(health); $('mode').refresh();
        S.portfolio.available = tr.name !== 'http' || !!(health.portfolio && health.course_lifecycle);
        $('portfolio-new').disabled = !S.portfolio.available;
        if (!S.portfolio.available) { S.portfolio.message('unavailable'); return; }
        return S.portfolio.open();
      });
    }).catch(function () { toast(t('class.failed')); });
    S.bus.on('speaking', releaseListening);
    S.bus.on('current', releaseListening);
    S.bus.on('ended', function () { if (S.voice.clear) S.voice.clear(); S.book.pages = []; });
    S.bus.on('capabilities', updatePrimary);
    S.bus.on('current', setRoom); S.bus.on('current', renderThumbs); S.bus.on('drawings', renderThumbs); S.bus.on('drawings', updatePrimary);
    $('sheet').addEventListener('submit', saveLesson);
    document.querySelectorAll('.pick').forEach(function (card) {
      card.addEventListener('click', function () { beginClass(card.dataset.entrance); });
    });
    $('start-settings').addEventListener('click', openLesson);
    $('start-back').addEventListener('click', openHome);
    $('btn-home').addEventListener('click', openHome);
    $('btn-back').addEventListener('click', goBack);
    $('book-edit-ending').addEventListener('click', function () { S.book.editEnding(); });
    $('motion-hint').addEventListener('input', function () { if (st.current) st.motionDrafts[st.current] = this.value; });
    function closeClassSwitch() {
      pendingEntrance = null; $('switch-class-overlay').hidden = true; $('sheet-overlay').hidden = false;
    }
    $('switch-class-close').addEventListener('click', closeClassSwitch);
    function startPendingClass(saveDrafts) {
      const entrance = pendingEntrance; pendingEntrance = null;
      $('switch-class-overlay').hidden = true; $('sheet-overlay').hidden = false;
      if (entrance) beginClass(entrance, true, saveDrafts);
    }
    $('switch-class-discard').addEventListener('click', function () { startPendingClass(false); });
    $('switch-class-confirm').addEventListener('click', function () { startPendingClass(true); });
    $('btn-lesson').addEventListener('click', openLesson);
    $('lesson-close').addEventListener('click', closeLesson);
    $('mode').querySelectorAll('button').forEach(function (b) {
      b.addEventListener('click', function () {
        visitMode(b.dataset.mode);
      });
    });
    $('btn-primary').addEventListener('click', primaryAction);
    $('teacher-review-generate').addEventListener('click', primaryAction);
    $('btn-next').addEventListener('click', nextChild);
    $('btn-answered').addEventListener('click', function () { S.companion.openHeard(); });
    $('btn-heard-back').addEventListener('click', backToQuestion);
    $('btn-silent').addEventListener('click', askSmaller);
    $('heard').addEventListener('submit', sendWhatTheySaid);
    $('heard-text').addEventListener('keydown', function (e) { if (e.key === 'Enter' && (e.metaKey || e.ctrlKey)) sendWhatTheySaid(e); });
    $('btn-listen').addEventListener('click', function () { S.microphones.toggle(); });
    ['btn-upload', 'empty-upload'].forEach(function (id) { $(id).addEventListener('click', function () { $('file').click(); }); });
    $('file').addEventListener('change', function () { if (this.files[0]) addPhoto(this.files[0]); this.value = ''; });
    ['empty-sample', 'btn-sample'].forEach(function (id) { $(id).addEventListener('click', function () {
      const sessionId = st.session;
      S.photos.sample().then(function (blob) { if (blob) return addPhoto(blob, sessionId); });
    }); });
    ['btn-camera', 'empty-camera'].forEach(function (id) { $(id).addEventListener('click', function () {
      S.photos.camera.open().catch(function () { toast(t('camera.none')); $('file').click(); }); }); });
    $('cam-shoot').addEventListener('click', function () {
      const sessionId = st.session;
      S.photos.camera.shoot().then(function (blob) { S.photos.camera.close(); return addPhoto(blob, sessionId); });
    });
    $('cam-close').addEventListener('click', function () { S.photos.camera.close(); });
    function openAdmin() {
      $('admin-ledger').hidden = !st.session;
      $('admin-overlay').hidden = false;
      if (st.transport?.deployments) S.deployments.refresh();
    }
    $('portfolio-admin').addEventListener('click', openAdmin);
    $('admin-close').addEventListener('click', function () { $('admin-overlay').hidden = true; });
    $('admin-ledger').addEventListener('click', function () { $('admin-overlay').hidden = true; S.ledger.open(); });
    // Load monitoring only while its panel is open.
    $('admin-board').addEventListener('click', function () {
      if (st.transport && st.transport.name === 'mock') { toast(t('board.preview')); return; }
      $('admin-overlay').hidden = true;
      S.deployments.open();
      $('board-overlay').hidden = false;
    });
    $('board-close').addEventListener('click', function () {
      $('board-overlay').hidden = true;

      $('admin-overlay').hidden = false;
    });
    $('viewer-save').addEventListener('click', function () { S.keepsake.saveOpen(toast); });
    $('btn-end-course').addEventListener('click', function () { if (st.session) confirmCourseCompletion(st.courseId || st.session); });
    $('end-class-cancel').addEventListener('click', function () { pendingCompletion = null; $('end-class-overlay').hidden = true; });
    $('end-class-confirm').addEventListener('click', endClass);
    $('cloud3d-model').addEventListener('change', updatePrimary);
    $('ledger-back').addEventListener('click', function () { S.ledger.close(); $('admin-overlay').hidden = false; });
    $('ledger-export').addEventListener('click', function () { S.ledger.exportJson(); });
    $('viewer-close').addEventListener('click', function () { S.book.stop(); S.media.close(); });
    $('book-prev').addEventListener('click', function () { S.book.go(-1); });
    $('book-next').addEventListener('click', function () { S.book.go(1); });
    $('book-read').addEventListener('click', function () { S.book.read(); });
    $('ending').addEventListener('submit', function (e) { S.book.saveEnding(e, toast); });   // typed, or said and written down
    $('ending-listen').addEventListener('click', function () { S.microphones.ending(); });
    $('btn-said-file').addEventListener('click', function () { $('said-file').click(); });
    $('said-file').addEventListener('change', function () {
      const file = this.files && this.files[0];
      this.value = '';
      if (file) S.microphones.fromFile(file);
    });
    addEventListener('pagehide', function () { pauseInteraction(); if (S.voice.clear) S.voice.clear(); if (st.session) S.session.end(); });
    setRoom(null); renderThumbs(); updatePrimary();
  }
  document.readyState === 'loading' ? document.addEventListener('DOMContentLoaded', boot) : boot();
})();
