// Content planning and teacher confirmation are distinct from media generation.
(function () {
  const S = Studio, st = S.state, t = (key, vars) => S.i18n.t('creation.' + key, vars);
  const esc = text => String(text || '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const planning = skill => skill === 'scene-description' || skill === 'story-outline';
  let hooks, sid, motionSteps = {}, motionEditors = {}, bookStep = 'select', bookInitialized = false, job = null, message = '', result = null, mediaResults = {}, bookResult = null, context = '', supported = true;
  let messages = {}, rejectedMotion = {}, rejectedBook = false, rejectedTexts = null;
  // What the review flagged on a rejected draft, per drawing and for the book: the
  // teacher editing the draft is the one reader who can act on it. Cleared with the
  // rejection it belongs to.
  let reviewIssues = {}, bookIssues = [], rejectedMotionTexts = {};
  // The words of a scene or a story while the studio writes them (29g-text-stream.js).
  let streamed = '';
  // What each drawing has had made, one of each kind (operator: a clip and a figure for the
  // same picture, where the newer used to hide the older). mediaResults keeps the latest.
  let made = {};
  const kindOf = r => r && (r.kind === 'figure' || (r.out && r.out.figure)) ? 'figure' : 'video';
  const keep = (id, r) => { (made[id] ||= {})[kindOf(r)] = r; };
  // A 3D figure inspired by the painting is a third output beside the clip and the pose (painting-to-figure);
  // it needs no description, and the studio checks it before it comes back. Offered only when the studio's own
  // skill list says so: a control follows the service's answer, never a default.
  let figureOffered = false;
  function enabled() { return !!st.session && (!hooks?.active || hooks.active()) && (st.mode === 'book' || (st.mode === 'move' && st.settings.entrance !== 'sketch')); }
  function button(key, action, primary = false, disabled = false) {
    return '<button type="button" class="btn ' + (primary ? 'primary' : '') + '" data-create="' + action + '"' + (disabled ? ' disabled' : '') + '>' + esc(t(key)) + '</button>';
  }
  function sameOrder(a, b) { return !!a && a.length === b.length && a.every((id, i) => id === b[i]); }
  // Once the teacher has rewritten EVERY passage of a rejected outline, the text is
  // theirs, not the model's, and the reviewer of model text has nothing to review;
  // the binding keeps supplied words verbatim behind a safety screen. One rewritten
  // passage beside a rejected one is still the model's book. Rewritten means the
  // words differ from what was rejected: a keystroke typed and undone, or the
  // rejected text pasted back, used to count as a rewrite and unlock the binding.
  function teacherOwnsOutline() {
    return rejectedBook && Array.isArray(rejectedTexts) && !!st.storyDraft && st.storyDraft.pages.length > 0
      && st.storyDraft.pages.length === rejectedTexts.length
      && st.storyDraft.pages.every((p, i) => p.text.trim() && p.text.trim() !== rejectedTexts[i].trim());
  }
  // The same door for a scene: a description the teacher has changed from the
  // rejected text is theirs, and confirming animates exactly what they wrote.
  // Without it a wrong reviewer blocked a teacher for the rest of a class,
  // because every regeneration handed it fresh model text.
  function teacherOwnsScene(id) {
    const text = (st.motionDrafts[id] || '').trim();
    return !!rejectedMotion[id] && typeof rejectedMotionTexts[id] === 'string' && !!text && text !== rejectedMotionTexts[id].trim();
  }
  function outlineValid() { return st.storyDraft && sameOrder(st.storyDraft.ids, st.chosen) && st.storyDraft.pages.every(p => p.text.trim()) && (st.storyDraft.scenes || []).every(s => s.text === st.motionDrafts[s.drawing_id]); }
  // Said by a child since the story was written? Then it is written again, not continued.
  function heardSince() { const heard = st.storyDraft?.heard; return !!heard && st.chosen.some(id => ((st.said || {})[id] || '') !== (heard[id] || '')); }
  // The planner has one job at a time; a clip being made no longer stops a conversation
  // elsewhere, so "working" is this job's own lane, not the class's.
  const making = skill => S.lanes.of(skill) === S.lanes.make;   // 29h-lanes.js
  function running() { return !!job && S.lanes.busy(S.lanes.of(job.skill)); }
  // Which page of a book is being written, and that page's picture on the stage (operator: the
  // picture never changed and the teacher could not tell where the book was). Put back when the job ends.
  let progress = '';
  function showProgress(stage) {
    const m = /^(scene-description|story-outline)-(.+)$/.exec(stage || '');
    if (!m || !job || job.skill !== 'story-outline') return;
    const d = m[1] === 'scene-description' ? st.drawings.find(x => x.id === m[2]) : null;
    progress = d ? t('writingPage', {page: job.ids.indexOf(d.id) + 1, n: job.ids.length, i: st.drawings.indexOf(d) + 1})
      : t('joiningPages', {n: job.ids.length});
    const el = document.getElementById('creation-progress'); if (el) el.textContent = progress;
    // Joining the story: page 1's picture, not whichever drawing the teacher last had open.
    const shown = d || st.drawings.find(x => x.id === job.ids[0]);
    if (shown) stage2(shown.url);
  }
  function stage2(url) {
    ['picture', 'haze'].forEach(id => { const el = document.getElementById(id); if (el && el.style && url) el.style.backgroundImage = 'url("' + url + '")'; });
  }
  function endProgress() { progress = ''; const d = S.session.currentDrawing && S.session.currentDrawing(); if (d) stage2(d.url); }
  function clipMakers() { return st.capabilities?.video_makers || []; }
  // Online unless the teacher picks the Spark (operator): about 2 minutes against 18.
  function clipMaker() { const makers = clipMakers(); return makers.includes(st.clipMaker) ? st.clipMaker : makers.includes('online') ? 'online' : 'spark'; }
  function send(skill, ids, options) {
    if (running() || S.lanes.busy(S.lanes.of(skill)) || S.rejoin?.busy || !ids.length || !supported) return;
    job = { skill, ids: ids.slice(), context, kind: options && options.media_kind }; message = ''; messages[context]=''; result = null; streamed = '';
    hooks.run(skill, ids, options);
  }
  function draftMotion() {
    if (!supported || running() || st.busy) return;
    send('scene-description', [st.current], { previous: st.motionDrafts[st.current] || '' });
  }
  function draftStory() {
    if (st.chosen.length < 2) return;
    const scenes = {};
    st.chosen.forEach(id => { if (st.motionDrafts[id] && (!rejectedMotion[id] || teacherOwnsScene(id))) scenes[id] = st.motionDrafts[id]; });
    // Always fresh: handed the last story, Qwen3.6 gave it back word for word.
    send('story-outline', st.chosen, { scenes });
  }
  function image(d, n) { return '<img src="' + esc(d.url) + '" alt="' + esc(S.i18n.t('picture.index', { n })) + '">'; }
  // A finished clip, figure or pose the course already keeps, read from the course as it was opened
  // (21-state.js), so a reload opens on it at once. Each drawing used to be looked up
  // again as it was shown, and 让画动起来 offered to make a clip it already had until that answer
  // came back (operator, found live). A new class has nothing saved and a photo added later cannot
  // have a clip yet, so nothing is left to look up. The file itself is fetched when it is opened.
  function seedSaved() {
    Object.keys(st.savedMedia || {}).forEach(id => {
      const drawing = st.drawings.find(x => x.id === id);
      if (drawing) { motionSteps[id] = 'done'; mediaResults[id] = Object.assign({ out: null, drawing }, st.savedMedia[id]); }
    });
    Object.entries(st.savedMade || {}).forEach(([id, kinds]) => {
      const drawing = st.drawings.find(x => x.id === id);
      if (drawing) Object.values(kinds).forEach(entry => keep(id, id in mediaResults && mediaResults[id].activityId === entry.activityId
        ? mediaResults[id] : Object.assign({ out: null, drawing }, entry)));
    });
  }
  function openResult(r) {
    if (!r) return;
    if (r.activityId && !r.out) { openSaved(r); return; }
    if (r.out && r.out.figure) S.media.open(S.i18n.t('figure.title'), 'figure', r.out.figure, r.drawing); else hooks.open(r);
  }
  // A saved book also carries its id, for its ending, and the ending.
  function loadSaved(saved) {
    return S.portfolio.api('/' + encodeURIComponent(st.courseId) + '/activities/' + encodeURIComponent(saved.activityId)).then(activity =>
      Object.assign({}, activity.outputs, saved.skill === 'drawings-to-storybook' ? { artifact_id: saved.activityId, ending: activity.ending || '' } : {}));
  }
  // A page's clip for step 3 (29l-book-look.js): made in this sitting it is at hand; saved, it is fetched once.
  function clipOf(id) {
    const r = (made[id] || {}).video;
    if (!r) return null;
    if (r.out && r.out.video_url) return Promise.resolve(r.out.video_url);
    return r.activityId ? (r.clip ||= loadSaved(r).then(out => { r.out ||= out; return out.video_url; })) : null;
  }
  // A reopened class opens on its book, ending included, and edits the confirmed words (21-state.js).
  function seedBook() {
    const saved = st.savedBook, draft = st.storyDraft;
    if (!saved || saved.superseded || !draft || !sameOrder(draft.ids, saved.ids)) return;
    const book = bookResult = Object.assign({ out: null, drawing: null }, saved), session = st.session;
    bookStep = 'done';
    loadSaved(book).then(out => {
      if (!S.session.isCurrent(session) || st.storyDraft !== draft || !Array.isArray(out.pages)) return;
      book.out ||= out;
      draft.pages = out.pages.map(p => ({ drawing_id: p.drawing_id, text: p.text }));
      render();
    }).catch(() => {});
  }
  function openSaved(saved) {
    if (saved.loading) return;
    // The file can take half a minute on the node's relay; a class changed meanwhile keeps its own screen.
    const session = st.session, courseId = st.courseId, drawingId = st.current; saved.loading = true;
    loadSaved(saved).then(out => {
      saved.loading = false;
      if (!S.session.isCurrent(session) || courseId !== st.courseId) return;
      saved.out = out;
      // A book belongs to the class, not to the drawing on the stage.
      if ((st.current !== drawingId && saved.skill !== 'drawings-to-storybook') || !enabled()) return;
      if (saved.out.figure) S.media.open(S.i18n.t('figure.title'), 'figure', saved.out.figure, saved.drawing); else hooks.open(saved);
    }).catch(() => { saved.loading = false; if (S.session.isCurrent(session) && st.current === drawingId && enabled()) { message = t('stopped'); render(); } });
  }
  function moveTile(d, kind, saved, make) {
    const video = kind === 'video', title = t(video ? 'videoTitle' : 'figureTitle');
    const working = running() && making(job.skill) && job.ids.includes(d.id) && job.kind === kind;
    // A finished figure shows the studio's picture of it.
    const figure = !video && saved && st.courseId && (saved.activityId || saved.out?.artifact_id);
    const visual = video && saved ? image(d, st.drawings.indexOf(d) + 1) + '<span class="creation-result-play" aria-hidden="true">▶</span>'
      : figure ? '<img class="creation-result-figure" src="/api/courses/' + esc(encodeURIComponent(st.courseId) + '/activities/'
        + encodeURIComponent(figure)) + '?preview=1" alt="' + esc(S.i18n.t('figure.title')) + '">'
      : '<span class="creation-result-symbol" aria-hidden="true">' + (video ? '▷' : '◇') + '</span>';
    return '<article class="creation-result' + (saved ? ' is-ready' : '') + (working ? ' is-making' : '') + '"><div class="creation-result-visual">' + visual + '</div>'
      + '<div class="creation-result-info"><div><h2>' + esc(title) + '</h2><p>' + esc(t(video ? 'videoSummary' : 'figureSummary')) + '</p></div>'
      + '<span class="creation-result-status">' + esc(t(working ? 'resultMaking' : saved ? 'resultReady' : 'resultMissing')) + '</span></div>'
      + (saved ? button(video ? 'openVideo' : 'openFigure', 'open-' + kind) : '') + (make || '') + '</article>';
  }
  function moveView(d) {
    const have = made[d.id] || {}, showFigure = figureOffered || !!have.figure;
    // Each card carries its own make button, so what it makes and where to press are one place.
    const choosing = !running() && supported && motionSteps[d.id] !== 'edit';
    const make = (key, action, primary) => choosing ? button(key, action, primary).replace('class="btn', 'class="creation-make btn') : '';
    const gallery = '<div class="creation-results' + (showFigure ? '' : ' one-result') + '">'
      + moveTile(d, 'video', have.video, make(have.video ? 'redoVideo' : 'startVideo', 'edit-video', !have.video))
      + (showFigure ? moveTile(d, 'figure', have.figure, figureOffered && make(have.figure ? 'redoFigure' : 'startFigure', 'edit-figure', !have.figure && !!have.video)) : '') + '</div>';
    const header = { step: t('resultsEyebrow'), heading: t('resultsHeading') };
    if (running()) {
      const lane = making(job.skill) ? 'make' : 'talk', status = lane === 'make' ? S.makeStatus : S.taskStatus;
      return { ...header, content: gallery + '<div class="creation-move-editor"><h3>' + esc(t(planning(job.skill) ? 'writing' : 'making')) + '</h3>'
        + '<div id="creation-task-status" data-lane="' + lane + '" aria-live="polite">' + (status ? status.html() : '') + '</div>'
        + '<p>' + esc(t(planning(job.skill) ? 'writingNote' : job.kind === 'figure' ? 'figureMaking' : 'makingNote')) + '</p>'
        + (planning(job.skill) ? '<p class="creation-progress" id="creation-progress">' + esc(progress) + '</p><p class="creation-stream" id="creation-stream">' + esc(streamed) + '</p>' : '') + '</div>',
        actions: job.context === context ? button('cancel', 'cancel') : '' };
    }
    if (!supported) return { ...header, content: gallery + '<p role="status">' + esc(t('updateNote')) + '</p>', actions: '' };
    if (motionSteps[d.id] !== 'edit') {
      return { ...header, content: gallery + '<p class="creation-results-note">' + esc(t(figureOffered ? 'resultsNote' : 'videoOnlyNote')) + '</p>',
        actions: '' };
    }
    const figureMode = figureOffered && motionEditors[d.id] === 'figure', drafted = !!(st.motionDrafts[d.id] || '').trim();
    const switcher = showFigure ? '<div class="creation-editor-switch" aria-label="选择要制作的作品">'
      + '<button type="button" data-create="edit-video" aria-pressed="' + !figureMode + '">' + esc(t('videoTitle')) + '</button>'
      + '<button type="button" data-create="edit-figure" aria-pressed="' + figureMode + '"' + (figureOffered ? '' : ' disabled') + '>' + esc(t('figureTitle')) + '</button></div>' : '';
    let editor = figureMode ? '<h3>' + esc(t('figureHeading')) + '</h3><p>' + esc(t('figureNote')) + '</p>'
      : '<h3>' + esc(t('motion')) + '</h3><p>' + esc(t(drafted ? 'motionNote' : 'motionEmpty')) + '</p>'
        + '<label for="creation-motion">' + esc(t('description')) + '</label><textarea id="creation-motion" rows="5" maxlength="600">' + esc(st.motionDrafts[d.id]) + '</textarea>';
    if (!figureMode && clipMakers().includes('online')) {
      const closed = st.capabilities?.video_makers_closed || [], maker = clipMaker();
      const option = (value, label) => '<option value="' + value + '"' + (closed.includes(value) ? ' disabled' : maker === value ? ' selected' : '') + '>'
        + esc(t(label)) + (closed.includes(value) ? esc(t('clipClosed')) : '') + '</option>';
      editor += '<label class="creation-clip" for="creation-clip">' + esc(t('clipMaker')) + '<select id="creation-clip" name="creation-clip">'
        + option('spark', 'clipSpark') + option('online', 'clipOnline') + '</select></label>'
        + (maker === 'online' ? '<p class="creation-clip-note">' + esc(t('clipOnlineNote')) + '</p>' : '');
    }
    return { ...header, content: gallery + '<div class="creation-move-editor">' + switcher + editor + '</div>',
      actions: button('backResults', 'results') + (figureMode ? button('figureMake', 'figure', true)
        : button(drafted ? 'rewriteMotion' : 'draftMotion', 'rewrite')
          + button('confirmMotion', 'confirm', true, !drafted)) };
  }
  function render() {
    if (!hooks) return;
    if (sid !== st.session) {
      sid = st.session; motionSteps = {}; motionEditors = {}; bookStep = 'select'; job = null; message = ''; result = null;
      messages={}; context=''; rejectedMotion={}; rejectedBook=false; rejectedTexts=null;
      mediaResults = {}; made = {}; bookResult = null;
      bookInitialized = false;
      if (st.storyDraft) { st.chosen = st.storyDraft.ids.slice(); bookInitialized = true; }
      seedBook(); seedSaved();
    }
    const root = document.getElementById('creation-planner'), active = enabled();
    root.hidden = !active; document.getElementById('app').dataset.creation = String(active);
    if (!active) return;
    const d = S.session.currentDrawing(), book = st.mode === 'book';
    const nextContext = st.session + ':' + st.mode + ':' + (book ? '' : st.current);
    if (context !== nextContext) { messages[context]=message; context = nextContext; message = messages[context] || ''; }
    result = book ? bookResult : mediaResults[st.current];
    if (book && bookStep !== 'select' && !outlineValid() && !running()) bookStep = 'select';
    if (book && bookStep === 'look' && !running() && !S.lanes.busy(S.lanes.make) && S.bookLook?.due(st.chosen)) { send(...S.bookLook.bind(st.chosen)); if (running()) return; }
    if (book && !bookInitialized && st.drawings.length) { st.chosen = S.chooser.initial(st.drawings,8); bookInitialized = true; hooks.chosen?.(); }
    root.dataset ||= {}; root.dataset.layout = book ? '' : 'results';
    let content = '', actions = '', heading = '', step = '';
    if (!book && d) {
      ({ content, actions, heading, step } = moveView(d));
    } else if (!supported) {
      heading = t('update'); content = '<p role="status">' + esc(t('updateNote')) + '</p>';
    } else if (running()) {
      const lane = making(job.skill) ? 'make' : 'talk', status = lane === 'make' ? S.makeStatus : S.taskStatus, drawing = job.skill === 'book-pictures';
      heading = t(planning(job.skill) ? 'writing' : drawing ? 'lookDrawing' : 'making');
      content = '<div id="creation-task-status" data-lane="' + lane + '" aria-live="polite">' + (status ? status.html() : '') + '</div><p>' + esc(t(planning(job.skill) ? 'writingNote' : drawing ? 'lookDrawingNote' : job.kind === 'figure' ? 'figureMaking' : 'makingNote')) + '</p>'
        + (planning(job.skill) ? '<p class="creation-progress" id="creation-progress">' + esc(progress) + '</p><p class="creation-stream" id="creation-stream">' + esc(streamed) + '</p>' : '');
      // Cancel only where the job began: seen from another picture or tab, it threw that job away.
      actions = job.context === context ? button('cancel', 'cancel') : '';
    } else if (book && bookStep === 'select') {
      step = t('bookOne'); heading = t('select');
      // The pictures stand in the story's order, the chosen ones first (operator: after "move up"
      // the list changed and the pictures did not). Each keeps its own number from today's drawings.
      const inStory = st.chosen.map(id => st.drawings.find(x => x.id === id)).filter(Boolean);
      const ordered = inStory.concat(st.drawings.filter(x => !st.chosen.includes(x.id)));
      content = '<div class="creation-picks">' + ordered.map(drawing => { const i = st.drawings.indexOf(drawing), page = st.chosen.indexOf(drawing.id); return '<button type="button" class="creation-pick" data-pick="' + esc(drawing.id) + '" aria-pressed="' + (page >= 0) + '">' + image(drawing, i + 1) + '<span>' + (page >= 0 ? esc(t('storyPage', {n: page + 1})) + ' · ' : '') + esc(S.i18n.t('picture.index', {n:i+1})) + '</span></button>'; }).join('') + '</div>';
      content += '<h3>' + esc(t('order')) + '</h3><ol class="creation-order">' + st.chosen.map((id, i) => '<li><span>' + esc(S.i18n.t('picture.index', {n:st.drawings.findIndex(x=>x.id===id)+1})) + '</span><button class="btn quiet" type="button" data-up="' + esc(id) + '"' + (!i?' disabled':'') + '>' + esc(t('up')) + '</button></li>').join('') + '</ol><p>' + esc(t('supplement')) + '</p>';
      const going = outlineValid() && !heardSince();
      actions = button(going ? 'continueStory' : 'makePlot', going ? 'continue-story' : 'plot', true, st.chosen.length < 2);
    } else if (book && bookStep === 'edit') {
      step = t('bookTwo'); heading = t('plot');
      // Each page names and shows its drawing, so the teacher can see the story follows her order
      // (operator: two drawings were near twins and the order could not be told from the text alone).
      const pageHead = (p, i) => { const d = st.drawings.find(x => x.id === p.drawing_id), n = st.drawings.indexOf(d) + 1;
        return '<span class="creation-page-head">' + (d ? '<img src="' + esc(d.url) + '" alt="">' : '') + esc(t('page',{n:i+1}))
          + (d ? ' · ' + esc(S.i18n.t('picture.index', {n})) : '') + '</span>'; };
      content = '<p>' + esc(t('plotNote')) + '</p>' + (st.storyDraft?.pages || []).map((p,i)=>'<label class="creation-page">' + pageHead(p, i) + '<textarea rows="3" maxlength="2000" data-page="' + i + '">' + esc(p.text) + '</textarea></label>').join('');
      const supplemented = (st.storyDraft?.scenes || []).filter(s=>s.supplemented).length;
      if (supplemented) content += '<p>' + esc(t('supplemented',{n:supplemented})) + '</p>';
      if (heardSince()) content += '<p class="creation-review-warning" role="status">' + esc(t('heardNew')) + '</p>';
      actions = button('back','back') + button('rewritePlot','plot') + button('confirmBook','book',true,!outlineValid() || (rejectedBook && !teacherOwnsOutline()));
    } else if (book && bookStep === 'look') {
      step = t('bookLookStep'); heading = t('look');
      ({ content, actions } = S.bookLook.view(st.chosen, id => !!(made[id] || {}).video));
    } else if (book && bookStep === 'done') {
      step = t('bookThree'); heading = t('bookDone');
      const changed = S.bookLook ? S.bookLook.changedPages(st.chosen, bookResult && bookResult.out) : [];
      if (changed.length) content = '<p class="creation-review-warning" role="status">' + esc(t('lookChangedPages', {pages: changed.join(t('listJoin'))})) + '</p>';
      actions = button('edit','edit') + button('openBook','open',true);
    } else if (!d) {
      heading = t('noDrawing');
    }
    if(book && teacherOwnsOutline()) content += '<p class="creation-review-warning" role="status">'+esc(t('teacherOwns'))+'</p>';
    else if(!book && d && motionSteps[d.id] === 'edit' && motionEditors[d.id] !== 'figure' && teacherOwnsScene(st.current)) content += '<p class="creation-review-warning" role="status">'+esc(t('teacherOwnsScene'))+'</p>';
    else if(book ? rejectedBook : d && motionSteps[d.id] === 'edit' && motionEditors[d.id] !== 'figure' && rejectedMotion[st.current]) content += '<p class="creation-review-warning" role="'+(book ? 'alert' : 'status')+'">'+esc(t(book ? (bookStep==='select' ? 'reviewFailedRedraft' : 'reviewFailed') : 'reviewFailedScene'))+'</p>';
    const flagged = book ? (rejectedBook && bookStep==='edit' && !teacherOwnsOutline() ? bookIssues : []) : (d && motionSteps[d.id] === 'edit' && motionEditors[d.id] !== 'figure' && rejectedMotion[st.current] && !teacherOwnsScene(st.current) ? reviewIssues[st.current] || [] : []);
    // The review sometimes names a drawing by its id ("c6f25f4343e9页"); the teacher sees its page instead
    // (operator). In a book the page follows the story order; elsewhere, today's drawing number.
    const named = text => String(text || '').replace(/(?:场景)?\b([0-9a-f]{12})\b(?:页)?/g, (whole, id) => {
      const page = st.chosen.indexOf(id), n = st.drawings.findIndex(x => x.id === id);
      return book && page >= 0 ? t('pageN', {n: page + 1}) : n >= 0 ? S.i18n.t('picture.index', {n: n + 1}) : whole;
    });
    if(flagged.length) content += '<div class="creation-review-issues"><p>'+esc(t('reviewIssues'))+'</p><ul>'+flagged.map(i=>'<li><span>'+esc(named(i.evidence))+'</span><span class="creation-review-suggestion">'+esc(named(i.suggestion))+'</span></li>').join('')+'</ul></div>';
    const thumbnails = !book && !st.busy && !running() ? '<div class="thumbs creation-thumbs">' + st.drawings.map((x,i)=>'<button type="button" data-current="' + esc(x.id) + '" aria-pressed="' + (x.id===st.current) + '" aria-label="' + esc(S.i18n.t('picture.index',{n:i+1})) + '">' + image(x,i+1) + '</button>').join('') + '</div>' : '';
    const art = !book && d && !running() ? '<div class="creation-original">' + image(d,st.drawings.indexOf(d)+1) + '<span>' + esc(t('original')) + '</span></div>' : '';
    root.innerHTML = thumbnails + '<p class="creation-step">' + esc(step) + '</p><h1>' + esc(heading) + '</h1><div class="creation-body' + (art?' with-original':'') + '">' + art + '<div>' + content + '</div></div><p class="creation-message" role="status">' + esc(message) + '</p><div class="creation-actions">' + actions + '</div>';
    if (book && bookStep === 'look' && S.bookLook) S.bookLook.attach(root, clipOf);
  }
  S.creation = {
    enabled, render, planning, sameOrder,
    owns(skill) { return !!job && job.skill===skill; },
    preview(text, stage) {
      streamed = text || ''; const el = document.getElementById('creation-stream'); if (el) el.textContent = streamed;
      showProgress(stage);
    },
    configure(skills) { supported = !skills || (skills.includes('scene-description') && skills.includes('story-outline')); figureOffered = !!skills && skills.includes('painting-to-figure'); S.bookLook?.configure(skills); render(); },
    init(callbacks) {
      hooks = callbacks;
      const root = document.getElementById('creation-planner');
      root.addEventListener('change', e => { if(e.target.name==='creation-clip') { st.clipMaker=e.target.value; render(); root.querySelector('#creation-clip')?.focus?.(); } });
      root.addEventListener('input', e => {
        if (e.target.id === 'creation-motion') { st.motionDrafts[st.current] = e.target.value; if (rejectedMotion[st.current]) { const w = root.querySelector('.creation-review-warning'); if (w) w.textContent = t(teacherOwnsScene(st.current) ? 'teacherOwnsScene' : 'reviewFailedScene'); } }
        if (e.target.dataset.page !== undefined) { st.storyDraft.pages[+e.target.dataset.page].text = e.target.value; if (rejectedBook) { const w = root.querySelector('.creation-review-warning'); if (w) w.textContent = t(teacherOwnsOutline() ? 'teacherOwns' : 'reviewFailed'); } }
        const confirm = root.querySelector('[data-create="confirm"]'), book = root.querySelector('[data-create="book"]');
        if (confirm) confirm.disabled = !(st.motionDrafts[st.current] || '').trim();
        if (book) book.disabled = !outlineValid() || (rejectedBook && !teacherOwnsOutline());
      });
      root.addEventListener('click', e => {
        const b = e.target.closest('button'); if (!b || b.disabled || S.rejoin?.busy) return;
        if (b.dataset.create === 'cancel') { if (job) hooks.stop(job.skill); return; }
        if (b.dataset.create === 'open-video' || b.dataset.create === 'open-figure') {
          openResult((made[st.current] || {})[b.dataset.create.slice(5)]); return;
        }
        if (running()) return;
        if (b.dataset.current) { result = null; message = ''; S.session.select(b.dataset.current); return; }
        if (b.dataset.pick) {
          const next = S.chooser.toggle(st.chosen,b.dataset.pick,8);
          if (next) { st.chosen = next; render(); hooks.chosen?.(); } else { message = S.i18n.t('book.full',{n:8}); render(); }
          return;
        }
        if (b.dataset.up) { const i=st.chosen.indexOf(b.dataset.up); if(i>0)[st.chosen[i-1],st.chosen[i]]=[st.chosen[i],st.chosen[i-1]]; render(); hooks.chosen?.(); return; }
        if (st.mode === 'book' && bookStep === 'look' && S.bookLook) {   // 29l-book-look.js
          const asked = S.bookLook.click(b.dataset, st.chosen);
          if (asked === 'render') { message = ''; render(); return; }
          if (asked) { send(...asked); return; }
        }
        const action = b.dataset.create;
        switch(action) {
          case 'rewrite': draftMotion(); return;
          case 'confirm': if ((st.motionDrafts[st.current] || '').trim()) send('painting-to-animation',[st.current],Object.assign({hint:st.motionDrafts[st.current],media_kind:'video'}, clipMakers().includes('online') ? {clip_maker:clipMaker()} : {})); return;
          case 'figure': send('painting-to-animation',[st.current],{media_kind:'figure'}); return;
          case 'plot': draftStory(); return;
          case 'continue-story': bookStep='edit'; break;
          case 'book': if(!outlineValid() || (rejectedBook && !teacherOwnsOutline())) return; bookStep='look'; break;
          case 'back': bookStep='select'; break;
          case 'look-back': bookStep='edit'; break;
          case 'edit': if(st.mode==='book') bookStep='edit'; else { motionEditors[st.current]='video'; motionSteps[st.current]='edit'; } break;
          case 'edit-video': motionEditors[st.current]='video'; motionSteps[st.current]='edit'; break;
          case 'edit-figure': if (!figureOffered) return; motionEditors[st.current]='figure'; motionSteps[st.current]='edit'; break;
          case 'results': motionSteps[st.current]='done'; break;
          case 'open': openResult(result); return;
        }
        message=''; render();
        if (action === 'edit-video' || action === 'edit-figure' || action === 'results') {
          root.querySelector('[data-create="' + (action === 'results' ? 'edit-video' : action) + '"]')?.focus?.();
        }
      });
    },
    completed(skill, out, drawing) {
      if (skill==='scene-description') {st.motionDrafts[job.ids[0]]=out.text;delete rejectedMotion[job.ids[0]];delete reviewIssues[job.ids[0]];delete rejectedMotionTexts[job.ids[0]];}
      else if (skill==='story-outline') {
        rejectedBook=false; rejectedTexts=null; bookIssues=[];
        st.storyDraft={ids:job.ids.slice(),pages:out.outline,scenes:out.scenes || [],heard:S.session.heardNow?.(job.ids)}; bookStep='edit';
        (out.scenes || []).forEach(s=>{if(!st.motionDrafts[s.drawing_id] || rejectedMotion[s.drawing_id])st.motionDrafts[s.drawing_id]=s.text;delete rejectedMotion[s.drawing_id];delete reviewIssues[s.drawing_id];delete rejectedMotionTexts[s.drawing_id];});
      } else if (skill==='book-pictures') {
        S.bookLook.completed(out);
      } else if (job) {
        result={skill,out,drawing};
        if(skill==='drawings-to-storybook') { bookStep='done'; bookResult=result; }
        else { motionSteps[job.ids[0]]='done'; mediaResults[job.ids[0]]=result; keep(job.ids[0], result); }
      }
      if (job) messages[job.context]='';
      job=null; message=''; endProgress();
    },
    stopped(text, candidate, issues, advice) {
      // A clip's description the check still refused after its tries is not an error: the note beside it says so,
      // and the same sentence again under the box read as the red failure teachers took for a dead end.
      let advised = false;
      if(candidate && job && (candidate.skill===job.skill || (job.skill==='story-outline' && candidate.skill==='scene-description' && job.ids.includes(candidate.drawing_id)))) {
        if(candidate.skill==='scene-description' && typeof candidate.text==='string' && candidate.text.trim()) {
          const id=candidate.drawing_id || job.ids[0];
          advised = !!advice;
          st.motionDrafts[id]=candidate.text; rejectedMotion[id]=true; motionSteps[id]='edit'; reviewIssues[id]=Array.isArray(issues)?issues:[]; rejectedMotionTexts[id]=candidate.text;
          if(job.skill==='story-outline') { rejectedBook=true; rejectedTexts=null; }
        } else if(candidate.skill==='story-outline' && Array.isArray(candidate.outline) && candidate.outline.every(p=>typeof p.text==='string')) {
          st.storyDraft={ids:job.ids.slice(),pages:candidate.outline,scenes:candidate.scenes || []};bookStep='edit';rejectedBook=true;rejectedTexts=candidate.outline.map(p=>p.text);bookIssues=Array.isArray(issues)?issues:[];
          // A scene that reached the outline passed its own review, so it replaces a text the
          // reviewer rejected earlier. Same clause as the success path above; without it the
          // stale rejected text fails outlineValid() and the edit step is never shown.
          (candidate.scenes || []).forEach(s=>{if(!st.motionDrafts[s.drawing_id] || rejectedMotion[s.drawing_id]){st.motionDrafts[s.drawing_id]=s.text;delete rejectedMotion[s.drawing_id];delete reviewIssues[s.drawing_id];delete rejectedMotionTexts[s.drawing_id];}});
        }
      }
      if (job?.skill==='book-pictures') S.bookLook.stopped();
      const target=job?.context || context, value=advised ? '' : text || t('stopped');
      messages[target]=value;
      if (target===context) message=value;
      job=null; endProgress();
    }
  };
})();
