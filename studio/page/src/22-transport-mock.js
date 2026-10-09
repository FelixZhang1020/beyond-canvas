// The mock harness: same shape as the HTTP transport, no network. Stages, gates and a ledger are simulated;
// the mock feedback is grounded in the colours found in the photo, and a blank page is refused kindly.
window.Studio = window.Studio || {};
Studio.mockText = Studio.mockText || {};
Studio.mockText.en = {
  openers: ['I notice you used {a} and {b}, ', 'I see a lot of {a} and a patch of {b}, ', 'First I see {a}, then {b}, '],
  middles: ['and the lines go right up to the edge of the paper.', 'and the shapes sit close together, as if they are talking.',
    'with the big shape in the middle and small ones around it.'],
  closers: ['I also see one place where two colours are layered on top of each other.', 'You pressed hard on the sky part.',
    'You left a big open space on one side.'],
  questions: ['Tell me, what is happening in the picture?', 'What is the big shape thinking about?', 'If it could talk, what would it say?',
    'Where did you start drawing?'],
  sketch: {
    openers: ['I see the light landing on the upper left and the shadow turning darker underneath, ',
      'I notice the darkest tone sits just inside the edge, not on it, ', 'First I see where the cast shadow starts, then where the highlight sits, '],
    middles: ['and the form reads as round because the tones step down gradually.', 'and the outline is measured rather than traced.',
      'with the shadow side kept lighter than the cast shadow.'],
    tries: ['You could try measuring the cast shadow against the width of the ball.', 'You could try squinting to find where the shadow really turns.',
      'You could try one more tone between the light and the dark.'],
    questions: ['Which part did you change the most?', 'Where was the hardest part?', 'What did you try first, the outline or the shading?']
  },
  lesson: "That connects to today's lesson: {intent}.",
  reply: ['You said {said}. Tell me more about that part.', 'So {said}. What happens next in there?',
    'You said {said}. I would not have known that from looking.'],
  rung: { 2: ['Is it daytime or night time in there?', 'Did this happen inside or outside?'],
    3: ['If the big shape could talk, what would it say first?', 'Splat wants to know: who else is in there?'] },
  colours: { coral: 'coral red', tangerine: 'orange', sunflower: 'sunflower yellow', leaf: 'leaf green', sky: 'sky blue', violet: 'purple',
    rose: 'pink', ink: 'deep blue', brown: 'brown', grey: 'grey' },
  book: { title: "Today's story", pages: ['Once upon a time there was a picture full of {a}.', 'Then a big patch of {b} came along, looking for a friend.',
    'The {a} and the {b} played together all day.', 'In the end, everyone fell asleep inside the picture.'] }
};
Studio.transports = Studio.transports || {};
(function () {
  let seq = 1; const sessions = {};
  function id(prefix) { return prefix + '-' + (seq++).toString(36) + Math.random().toString(36).slice(2, 6); }
  function wait(ms) { return new Promise(function (r) { setTimeout(r, ms); }); }
  function pick(arr, n) { return arr[n % arr.length]; }
  function analyse(url) {
    return Studio.photos.stats(url).then(function (st) { return st || { paperRatio: 0, variance: 100, mean: 128, muddyRatio: 0, colours: ['sky', 'coral'], counts: {} }; });
  }
  function line(reqId, stage, gate, tokens, wall, extra) {
    const mem = 57.1 + Math.random() * 1.5;
    return Object.assign({ ts: new Date().toISOString(), request_id: reqId, stage: stage, inputs_hash: id('sha'), outputs_path: '',
      gate: gate, tokens: tokens, wall_s: +wall.toFixed(2), mem_before_gb: +mem.toFixed(1), mem_after_gb: +(mem + .2).toFixed(1) }, extra || {});
  }
  // The entrance the teacher chose decides the shape: colour grounds in the paints found and asks into the
  // picture; sketch reads the light and the form, offers one thing to try, and asks about the process.
  function feedbackText(stats, settings, n) {
    const T = Studio.mockText[settings.language] || Studio.mockText.en, gap = settings.language === 'zh' ? '' : ' ';
    const sketch = settings.entrance === 'sketch';
    let text;
    if (sketch) {
      text = pick(T.sketch.openers, n) + pick(T.sketch.middles, n) + gap + pick(T.sketch.tries, n);
    } else {
      const c = stats.dominant && stats.dominant.length ? stats.dominant : stats.colours;
      const a = T.colours[c[0] || 'sky'], b = T.colours[c[1] || 'coral'];
      text = pick(T.openers, n).replace('{a}', a).replace('{b}', b) + pick(T.middles, n) + gap + pick(T.closers, n + 1);
    }
    if (settings.lessonIntent) text += gap + T.lesson.replace('{intent}', settings.lessonIntent);
    const question = pick(sketch ? T.sketch.questions : T.questions, n);
    return { text: text, question: question, language: settings.language,
      rubric: { passed: true, failed: [] }, beat: 'opening' };
  }
  Studio.mockFeedback = feedbackText;
  // The same shape the real skill returns, so the page's player is exercised
  // rather than a second drawing path that only the mock ever runs.
  Studio.mockChoreography = function () {
    return { duration_s: 6, layers: [
      { name: 'the shape near the top', box: [.30, .04, .40, .30], move: 'sway', start_s: 0, end_s: 6, distance: [.05, 0] },
      { name: 'the shape on the right', box: [.55, .30, .35, .45], move: 'rise', start_s: .5, end_s: 5, distance: [0, .10] }
    ] };
  };
  function safety(session, drawing, reqId, emit) {
    emit({ stage: 'studio-safety', status: 'running', ledger: line(reqId, 'studio-safety', null, 0, 0) });
    return wait(500).then(function () { return analyse(drawing.url); }).then(function (stats) {
      if (Studio.isDark(stats) || Studio.isBlank(stats)) return { stop: 'blank_page', msg: 'msg.blank', stats: stats };
      if (Studio.looksLikePhoto(stats)) return { stop: 'photo_not_drawing', msg: 'msg.photo', stats: stats };
      emit({ stage: 'studio-safety', status: 'gate_pass', ledger: line(reqId, 'studio-safety', 'pass', 0, .5) });
      return { stats: stats };
    });
  }
  function stopped(reqId, check, emit) {
    emit({ stage: 'studio-safety', status: 'stopped', message: Studio.i18n.t(check.msg), reason_code: check.stop,
      ledger: line(reqId, 'studio-safety', 'fail', 0, .5, { reason_code: check.stop }) });
  }
  // Beats three and four. The mock says nothing the child did not say: a reply
  // quotes them back, a rung asks smaller. Same shape as the real harness.
  function laterBeat(settings, opts, n) {
    const T = Studio.mockText[settings.language] || Studio.mockText.en;
    const said = (opts.transcript || '').trim();
    if (said) {
      return { text: pick(T.reply, n).replace('{said}', said), question: '', language: settings.language,
        rubric: { passed: true, failed: [] }, beat: 'reply' };
    }
    const rung = opts.rung === 3 ? 3 : 2;
    return { text: '', question: pick(T.rung[rung], n), language: settings.language,
      rubric: { passed: true, failed: [] }, beat: 'rung-' + rung };
  }
  function runFeedback(session, drawing, opts, reqId, emit) {
    return safety(session, drawing, reqId, emit).then(function (check) {
      if (check.stop) return stopped(reqId, check, emit);
      const later = opts && (opts.transcript || opts.rung);
      const out = later ? laterBeat(session.settings, opts, session.count++)
        : feedbackText(check.stats, session.settings, session.count++);
      emit({ stage: 'art-feedback', status: 'running', ledger: line(reqId, 'art-feedback', null, 0, 0) });
      const words = out.text.split(session.settings.language === 'zh' ? '' : ' ');
      let i = 0;
      return (function step() {
        if (i >= words.length) return;
        i += session.settings.language === 'zh' ? 2 : 1;
        // As the studio sends it: the words so far, and the question once it is written.
        emit({ stage: 'art-feedback', status: 'running', partial: { text: words.slice(0, i).join(session.settings.language === 'zh' ? '' : ' '),
          question: i >= words.length ? out.question || '' : '', writing: true } });
        return wait(70).then(step);
      })().then(function () {
        emit({ stage: 'art-feedback', status: 'gate_pass', ledger: line(reqId, 'art-feedback', 'pass', 640 + Math.floor(Math.random() * 200), 2.6) });
        emit({ stage: 'rubric', status: 'running', ledger: line(reqId, 'rubric', null, 0, 0) });
        return wait(500);
      }).then(function () {
        emit({ stage: 'rubric', status: 'gate_pass', ledger: line(reqId, 'rubric', 'pass', 210, .5) });
        emit({ stage: 'art-feedback', status: 'done', outputs: out, ledger: line(reqId, 'art-feedback', null, 0, 0) });
      });
    });
  }
  function runMedia(session, drawing, skill, reqId, emit, options) {
    if (skill === 'sketch-to-3d' || skill === 'painting-to-animation') {
      return Promise.resolve().then(function () {
        const mock = skill === 'sketch-to-3d' ? 'relight.mock' : options && options.media_kind === 'figure' ? 'figure.mock' : 'animation.mock';
        emit({ stage: skill, status: 'stopped', message: Studio.i18n.t(mock), reason_code: 'model_unavailable' });
      });
    }
    return safety(session, drawing, reqId, emit).then(function (check) {
      if (check.stop) return stopped(reqId, check, emit);
      emit({ stage: skill, status: 'running', ledger: line(reqId, skill, null, 0, 0) });
      let p = 0;
      return (function step() {
        if (p >= 100) return;
        p += 9; emit({ stage: skill, status: 'running', partial: { percent: Math.min(100, p) } });
        return wait(380).then(step);
      })().then(function () {
        emit({ stage: skill, status: 'gate_pass', ledger: line(reqId, skill, 'pass', 120, 4.2) });
        const outputs = skill === 'painting-to-scene' ? { preview_url: 'mock:scene', package_url: null }
          : { choreography: Studio.mockChoreography() };
        emit({ stage: skill, status: 'done', outputs: outputs, ledger: line(reqId, skill, null, 0, 0) });
      });
    });
  }
  function runBook(session, drawings, reqId, emit, options) {
    const T = Studio.mockText[session.settings.language] || Studio.mockText.en;
    return drawings.reduce(function (chain, d) {
      return chain.then(function (acc) { if (acc.stop) return acc; return safety(session, d, reqId, emit).then(function (c) { return c.stop ? c : acc; }); });
    }, Promise.resolve({})).then(function (check) {
      if (check.stop) return stopped(reqId, check, emit);
      emit({ stage: 'drawings-to-storybook', status: 'running', ledger: line(reqId, 'drawings-to-storybook', null, 0, 0) });
      return wait(900).then(function () { return Promise.all(drawings.map(function (d) { return analyse(d.url); })); });
    }).then(function (stats) {
      if (!stats) return;
      const pages = drawings.map(function (d, i) {
        const c = stats[i].dominant && stats[i].dominant.length ? stats[i].dominant : stats[i].colours;
        const a = T.colours[c[0] || 'sky'], b = T.colours[c[1] || 'coral'];
        return { drawing_id: d.id, text: options?.pages?.[i]?.text ?? pick(T.book.pages, i).replace('{a}', a).replace('{b}', b), audio_url: null };
      });
      emit({ stage: 'drawings-to-storybook', status: 'gate_pass', ledger: line(reqId, 'drawings-to-storybook', 'pass', 900, 3.1) });
      emit({ stage: 'narration', status: 'running', ledger: line(reqId, 'narration', null, 0, 0) });
      return wait(600).then(function () {
        emit({ stage: 'narration', status: 'gate_pass', ledger: line(reqId, 'narration', 'pass', 0, .6) });
        emit({ stage: 'drawings-to-storybook', status: 'done', outputs: { title: T.book.title, pages: pages, html_url: null },
          ledger: line(reqId, 'drawings-to-storybook', null, 0, 0) });
      });
    });
  }
  Studio.transports.mock = {
    name: 'mock',
    health: function () { return Promise.resolve({ ok: true, profile: 'mock', mode: 'studio' }); },
    createSession: function (settings) {
      const sid = id('s'); sessions[sid] = { settings: settings, drawings: {}, ledger: [], count: 0 };
      return Promise.resolve({ session_id: sid });
    },
    saveDrafts: function () { return Promise.resolve(); },
    forgetSession: function (sid) { delete sessions[sid]; return Promise.resolve(); },
    deleteCourse: function (sid) { delete sessions[sid]; return Promise.resolve(null); },
    addDrawing: function (sid, blob) {
      const did = id('d'), url = URL.createObjectURL(blob); sessions[sid].drawings[did] = { id: did, url: url };
      return Promise.resolve({ drawing_id: did, url: url });
    },
    removeDrawing: function (sid, did) { delete sessions[sid].drawings[did]; return Promise.resolve(null); },
    forgetChat: function () { return Promise.resolve(null); },
    // The mock cannot hear, and says so rather than inventing what a child said.
    hear: function (sid, blob) {
      return wait(700).then(function () { return { text: '', language: 'en', listening: false }; });
    },
    request: function (sid, skill, drawingIds, options, onEvent) {
      const session = sessions[sid], reqId = id('r'), drawings = drawingIds.map(function (x) { return session.drawings[x]; });
      let live = true;
      const emit = function (ev) { if (!live) return; ev.request_id = reqId; if (ev.ledger) session.ledger.push(ev.ledger); onEvent(ev); };
      if (skill === 'teacher-review') {
        wait(500).then(() => emit({stage:skill,status:'done',outputs:{text:Studio.i18n.t('teacher.mock'),beat:'teacher-review'}}));
        return {request_id:reqId,abort:function(){live=false;}};
      }
      if (skill === 'scene-description' || skill === 'story-outline') {
        wait(500).then(function () {
          const text = Studio.i18n.t('mock.creationScene');
          const scenes = drawingIds.map(did => ({drawing_id:did,text:options.scenes?.[did] || text,supplemented:!options.scenes?.[did]}));
          emit({stage:skill,status:'done',outputs:skill==='scene-description'?{text:text}:{outline:scenes.map(s=>({drawing_id:s.drawing_id,text:s.text})),scenes:scenes}});
        });
        return {request_id:reqId,abort:function(){live=false;}};
      }
      const run = skill === 'art-feedback' ? runFeedback(session, drawings[0], options, reqId, emit)
        : skill === 'drawings-to-storybook' ? runBook(session, drawings, reqId, emit, options) : runMedia(session, drawings[0], skill, reqId, emit, options);
      run.catch(function (e) { emit({ stage: skill, status: 'stopped', message: Studio.i18n.t('msg.unavailable'), reason_code: 'model_unavailable',
        ledger: line(reqId, skill, 'fail', 0, 0, { reason_code: 'model_unavailable' }) }); console.error(e); });
      return { request_id: reqId, abort: function () { live = false; } };
    },
    ledger: function (sid) { return Promise.resolve({ lines: (sessions[sid] || { ledger: [] }).ledger.slice() }); }
  };
})();
