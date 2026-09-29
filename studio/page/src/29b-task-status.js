// Percentages come only from reported progress, never from elapsed time.
(function () {
  const S = Studio, t = (key, vars) => S.i18n.t('task.' + key, vars);
  // How long a task normally takes is measured, never guessed. A whole video
  // run through the harness took 285s and 297s in two runs,
  // and the video model alone answered a probe in 192s. Below
  // its own window a task is costing what it costs; past it, something is
  // genuinely unusual. A task with no measurement keeps the plain two minutes.
  // Those were the 4090's. On the hosted Spark one clip took 691 s
  // (49 frames, 15 steps), so the video window is 700 s. A figure is written up to three times, and one
  // in nine took over five minutes (docs/measured/figure-three-writings.md), so its window is the
  // planner's own six. A request that names
  // no kind is the clip too (the move button sends none), and was left on the 4090's 300 s until the
  // still picture was retired.
  const PATIENCE = 120, TYPICAL = {'painting-to-animation': 1080, 'painting-to-animation.video': 1080, 'painting-to-animation.online': 120,
    'painting-to-animation.figure': 360,
    // A sketch's model came back in about 69 s with TRELLIS.2 kept loaded (docs/measured/trellis-stays-loaded.md),
    // plus the safety look and the reading around it.
    'sketch-to-3d': 120};
  const esc = value => String(value).replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  // One per lane: a clip is made beside a conversation, and each keeps its own line.
  // `lane` names which one the creation planner's box is showing.
  function create(lane) { let state; return {
    start(job) { state = {phase:'submitting', since:Date.now(), ended:null, percent:null, stage:null, typical:TYPICAL[job] || null, kind:(String(job).split('.')[1]) || null}; },
    update(ev) {
      if (!state) return;
      if (['stopped','done','cancelled'].includes(ev.status)) state.ended=Date.now();
      if (ev.stage && ev.stage !== state.stage) { state.stage = ev.stage; state.percent = null; }
      if (ev.status === 'stopped') state.phase = 'failed';
      else if (ev.status === 'done') state.phase = 'done';
      else if (['submitted','queued','loading','repair','cancelled'].includes(ev.status)) state.phase = ev.status;
      else if (ev.status === 'running') state.phase = ev.partial?.writing ? (ev.partial.revised ? 'rewriting' : 'writing')
        : ev.partial?.checking ? 'checkingResult' : ev.stage === 'studio-safety' ? 'checking' : 'running';
      else if (ev.status === 'gate_pass' || ev.status === 'gate_fail') { state.phase = 'checkingResult'; state.percent = null; }
      const p = ev.partial?.percent;
      if (typeof p === 'number' && Number.isFinite(p) && p >= 0 && p <= 100) state.percent = Math.round(p);
      this.tick();
    },
    line() { return state ? t(state.phase) + (state.percent === null ? '' : ' · ' + state.percent + '%') + ' · ' + t('elapsed', {s:Math.max(0, Math.floor(((state.ended ?? Date.now())-state.since)/1000))}) : ''; },
    html() {
      if (!state) return '';
      const seconds = Math.max(0, Math.floor((Date.now()-state.since)/1000));
      return '<div class="task-status"><strong>' + esc(t(state.phase)) + '</strong><span>' + esc(t('elapsed',{s:seconds})) + '</span></div>' +
        '<progress max="100"' + (state.percent === null ? '' : ' value="'+state.percent+'"') + ' aria-label="'+esc(t(state.phase))+'"></progress>' +
        '<p class="task-status-note">' + (state.stage && S.stageLabel ? esc(S.stageLabel(state.stage, state.kind)) + ' · ' : '') + esc(state.percent === null ? t('unknown') : state.percent + '%') + '</p>' +
        (seconds >= (state.typical || PATIENCE)
          ? '<p class="task-status-note">'+esc(t('longWait'))+'</p>'
          : state.typical ? '<p class="task-status-note">'+esc(t('typical', {m: Math.round(state.typical/60)}))+'</p>' : '');
    },
    tick() { const el = document.getElementById('creation-task-status'); if (el && el.dataset.lane === lane) el.innerHTML = this.html(); },
    failure(ev) {
      const code = ev.reason_code || ev.ledger?.reason_code || 'model_unavailable';
      const known = ['connection_lost','server_unreachable','submission_failed','session_gone','model_unavailable','busy','out_of_memory','storage_unavailable'];
      return t('failed') + ' · ' + (known.includes(code) ? t(code) : ev.message || t('failedNote'));
    }
  }; }
  S.taskStatus = create('talk'); S.makeStatus = create('make');
})();
