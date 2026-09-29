// Session state, a tiny event bus, and pure helpers the tests cover.
window.Studio = window.Studio || {};
Studio.state = {
  session: null, courseId: null, transport: null,
  // No default entrance, deliberately. The teacher picks by hand every class:
  // colour never corrects and sketch is expected to, so a value nobody chose
  // is the difference between encouragement and criticism.
  settings: { language: 'zh', lessonIntent: '', entrance: null },
  // busy: a conversation or teacher review is running. making: the skill of the clip, 3D model, figure or
  // book being made beside it, or null.
  drawings: [], current: null, mode: 'feedback', busy: false, making: null, ledger: [], results: {},
  modeHistory: [], teacherReviews: {}, feedback: {}, drafts: {},
  // Which drawings the teacher has picked for the book. Empty until she
  // opens that mode; see Studio.chooser.
  chosen: [],
  // How far up the ladder each drawing has climbed. 1 is the opening question,
  // already asked; 3 is the last rung there is.
  asked: {},
  // What the child said about each drawing. It drives the reply, and then what
  // moves when the picture is animated: section 5b wants the child to see that
  // because they said it, the world changed.
  said: {},
  motionDrafts: {},
  storyDraft: null,
  // The handle for the counter that keeps the waiting bubble moving.
  ticking: null
};
// The child said nothing, so make the door smaller. Never repeat a question, and
// never invent a fourth rung: after three, the answer is to move on.
Studio.nextRung = function (asked) {
  const at = asked || 1;
  return at >= 3 ? null : Math.max(2, at + 1);
};
Studio.bus = {
  handlers: {},
  on: function (ev, fn) { (this.handlers[ev] = this.handlers[ev] || []).push(fn); },
  emit: function (ev, data) { (this.handlers[ev] || []).forEach(function (fn) { fn(data); }); }
};
Studio.PAINT = {
  coral: [255, 111, 97], tangerine: [255, 159, 67], sunflower: [255, 201, 60], leaf: [94, 214, 166],
  sky: [79, 179, 255],
  violet: [155, 123, 255], rose: [255, 179, 199], ink: [38, 34, 74], brown: [140, 90, 52], grey: [150, 150, 150]
};
// Name the paint closest to an RGB triple, ignoring near-white paper.
Studio.nearestPaint = function (rgb, withDistance) {
  let best = null, bestD = Infinity;
  Object.keys(Studio.PAINT).forEach(function (name) {
    const p = Studio.PAINT[name];
    const d = (p[0] - rgb[0]) * (p[0] - rgb[0]) + (p[1] - rgb[1]) * (p[1] - rgb[1]) + (p[2] - rgb[2]) * (p[2] - rgb[2]);
    if (d < bestD) { bestD = d; best = name; }
  });
  return withDistance ? { name: best, d2: bestD } : best;
};
// From a flat RGBA array: how much of the page is paper, how varied it is, and which paints dominate.
Studio.imageStats = function (data) {
  const counts = {}, total = data.length / 4;
  let paper = 0, sum = 0, sumSq = 0, muddy = 0;
  for (let i = 0; i < data.length; i += 4) {
    const r = data[i], g = data[i + 1], b = data[i + 2], lum = (r * .299 + g * .587 + b * .114);
    sum += lum; sumSq += lum * lum;
    const sat = Math.max(r, g, b) - Math.min(r, g, b);
    if (lum > 215 && sat < 40) { paper++; continue; }
    const near = Studio.nearestPaint([r, g, b], true);
    if (near.d2 > 55 * 55) muddy++;
    counts[near.name] = (counts[near.name] || 0) + 1;
  }
  const mean = sum / total, variance = sumSq / total - mean * mean;
  const ranked = Object.keys(counts).sort(function (a, b) { return counts[b] - counts[a]; });
  const inked = Math.max(1, total - paper);
  const dominant = ranked.filter(function (name) { return counts[name] / inked >= 1 / 12; });
  return { paperRatio: paper / total, variance: variance, mean: mean, muddyRatio: muddy / inked, colours: ranked,
    dominant: dominant, counts: counts };
};
Studio.isBlank = function (stats) {
  return stats.paperRatio > .97 || stats.variance < 40;
};
// A camera frame with no light in it: the mock and the page both refuse it before anything else runs.
Studio.isDark = function (stats) { return stats.mean < 40 && stats.variance < 60; };
// Crayon on paper is paper plus strong paint hues; a photograph or a screenshot is mostly in-between colours.
Studio.looksLikePhoto = function (stats) { return stats.paperRatio < .15 && stats.muddyRatio > .45; };
Studio.ledgerSummary = function (lines) {
  const requests = {}, out = { requests: 0, gatesPassed: 0, gatesFailed: 0, tokens: 0, cost: 0, wall: 0, peakMem: 0 };
  (lines || []).forEach(function (l) {
    if (l.request_id) requests[l.request_id] = true;
    if (l.gate === 'pass') out.gatesPassed++;
    if (l.gate === 'fail') out.gatesFailed++;
    // Money arrives on every line and used to be summed nowhere, so the
    // view a judge reads counted tokens and said nothing about what they cost.
    out.tokens += l.tokens || 0; out.cost += l.cost || 0; out.wall += l.wall_s || 0;
    out.peakMem = Math.max(out.peakMem, l.mem_before_gb || 0, l.mem_after_gb || 0);
  });
  out.requests = Object.keys(requests).length;
  return out;
};
// Money on a ledger line, for people rather than for accountants. A dash means the
// line was written before costs were kept — not that the stage was free; a real 0
// is free — a stage that ran on the studio's own GPU machine genuinely is.
Studio.money = function (usd) {
  if (usd === undefined || usd === null) return '—';
  if (!usd) return '0';
  return usd < 0.0001 ? '<0.0001' : usd.toFixed(4);
};
// Why a zero is a zero. Studio.money prints '0' for a stage that ran on our own
// hardware and for one a subscription already paid for, and those are different
// facts about the same figure. StepFun First buys its reading,
// speech and hearing on a plan, so its zeros are prepaid rather than free — and
// the moving clip on that deployment is still bought per use, so the total is
// not zero either. Keyed on the deployment because that is what decides who was
// billed, and returned as a string key so the view stays free of wording.
Studio.costFootnote = function (deployment) {
  return deployment === 'stepfun' ? 'ledger.plan' : '';
};
// The harness names a stage by its skill; the page also knows what kind of
// thing is being made, and a still is not a short clip. The specific label wins
// when the language has one, and the skill's own label stands otherwise.
Studio.stageLabel = function (stage, kind) {
  if (kind) { const key = 'stage.' + stage + '.' + kind, s = Studio.i18n.t(key); if (s !== key) return s; }
  return Studio.i18n.t('stage.' + stage);
};
// What carries from one class to the next: the language, and nothing else. The kind of class is
// picked by hand, because a remembered one would be tapped through without thought, and now
// so is the lesson note (operator). A note typed once for a sketch class, "solids and
// shading", was carried unseen into every class after it, colour ones too, and the companion kept
// trying to connect zoo paintings to it. A note a browser saved under the old rule is not read.
Studio.settings = {
  KEY: 'beyond-canvas.class',

  remember: function (settings) {
    try {
      window.localStorage.setItem(this.KEY, JSON.stringify({ language: settings.language }));
    } catch (e) { /* a browser with storage refused is not a broken class */ }
  },


  recall: function () {
    try {
      const raw = window.localStorage.getItem(this.KEY);
      if (!raw) return {};
      const saved = JSON.parse(raw);
      const out = {};
      if (saved.language) out.language = saved.language;
      return out;
    } catch (e) { return {}; }
  }
};

// Which drawings go into the book. The teacher picks at most eight; the page
// used to send every drawing of the session, which is a machine deciding what
// the book is about.
//
// The newest eight start chosen, visibly and changeably, because a teacher who
// has to tap eight times before she can begin is a teacher who stops using it.
// The last page of the book is blank, and it is the child's.
//
// The machine does not write the ending. The child is asked "and then?", and his
// answer is the ending — the last thing in the book is his own voice. Until he
// answers, the page waits: an empty ending is not an ending.
Studio.ending = {
  add: function (pages) {
    if (pages.length && pages[pages.length - 1].ending) return pages.slice();
    return pages.concat([{ ending: true, text: '', url: '' }]);
  },

  answer: function (pages, text) {
    const said = (text || '').trim();
    return pages.map(function (page, i) {
      if (i !== pages.length - 1 || !page.ending) return page;
      return { ending: true, url: '', text: said };
    });
  },

  waiting: function (page) { return !!(page && page.ending && !page.text); },
  label: function (page) { return this.waiting(page) ? 'book.endingLabel' : page.ending ? 'book.endingDoneLabel' : 'book.pageLabel'; }
};

Studio.chooser = {
  initial: function (drawings, max) {
    return drawings.slice(-max).map(function (d) { return d.id; });
  },

  // A new array, or null when the answer is "no" — the page says why; the rule
  // does not know the words.
  //
  // `order` is every drawing of the class, oldest first. The result is always in
  // that order, so a page put back goes back where it was: the book follows the
  // afternoon, not the order the teacher happened to tap.
  toggle: function (chosen, id, max, order) {
    const has = chosen.indexOf(id) >= 0;
    if (!has && chosen.length >= max) return null;
    const next = has ? chosen.filter(function (x) { return x !== id; }) : chosen.concat([id]);
    if (!order) return next;
    return order.filter(function (x) { return next.indexOf(x) >= 0; });
  }
};

Studio.session = {
  ending: null,
  isCurrent: function (id) {
    return !!id && Studio.state.session === id && !(this.ending && this.ending.id === id);
  },
  releaseUrl: function (url) {
    if (url && url.indexOf('blob:') === 0) URL.revokeObjectURL(url);
  },
  begin: function (settings) {
    Studio.state.settings = Object.assign({}, Studio.state.settings, settings);
    if (!Studio.state.settings.entrance) {
      return Promise.reject(new Error('no entrance chosen: pick the kind of class by hand'));
    }
    return Studio.state.transport.createSession(Studio.state.settings).then(function (res) {
      Studio.state.session = res.session_id; Studio.state.courseId = res.course_id || res.session_id; Studio.state.savedMedia = {}; Studio.state.savedMade = {}; Studio.state.savedBook = null;
      Studio.state.capabilities = res.capabilities || {};
      Studio.bus.emit('session', res.session_id); return res.session_id;
    });
  },
  restore: function (payload) {
    const st = Studio.state, course = payload.course;
    if (course.ended_at || st.session) throw new Error('Open an editable course after leaving the current editor.');
    st.session = payload.session_id; st.courseId = course.id;
    st.capabilities = payload.capabilities || {};
    st.settings = { language: course.language, entrance: course.entrance, lessonIntent: course.lesson_intent, title: course.title };
    st.drawings = course.drawings.map(function (drawing) { return { id: drawing.id, url: drawing.url }; });
    st.current = st.drawings.length ? st.drawings[0].id : null;
    st.mode = 'feedback'; st.modeHistory = []; st.results = {}; st.ledger = [];
    st.chosen = []; st.teacherReviews = {}; st.feedback = {}; st.said = {}; st.asked = {}; st.motionDrafts = {}; st.drafts = Object.assign({}, course.drafts || {});
    st.savedMedia = {}; st.savedMade = {};   // the latest of any kind, and the latest of each
    st.storyDraft = null; st.savedBook = null;
    course.activities.forEach(function (activity) {
      const summary = activity.summary;
      if (activity.skill === 'story-outline' && summary.outline && !summary.status) {
        // What the children had said by then (29a-creation.js).
        st.storyDraft = { ids: activity.drawings.slice(), pages: summary.outline, scenes: summary.scenes || [],
          heard: Studio.session.heardNow(activity.drawings) };
        (summary.scenes || []).forEach(scene => { st.motionDrafts[scene.drawing_id] = scene.text; });
        if (st.savedBook) st.savedBook.superseded = true;
      }
      // The finished book and its ending, for a reopened class (29a-creation.js).
      if (activity.skill === 'drawings-to-storybook' && !summary.status) {
        st.savedBook = { skill: activity.skill, activityId: activity.id, ids: activity.drawings.slice(), ending: activity.ending || '' };
      }
      activity.drawings.forEach(function (id) {
        if (!summary.status && (summary.scene_description || activity.skill === 'scene-description')) {
          st.motionDrafts[id] = summary.scene_description || summary.text;
        }
        if (activity.skill === 'teacher-review' && !summary.status) st.teacherReviews[id] = summary;
        // The latest finished clip, figure or pose, so 让画动起来 opens on it at once instead of
        // offering to make it again until a lookup comes back (operator).
        if (['video', 'figure', 'keyframe'].includes(summary.kind) && !summary.status) {
          st.savedMedia[id] = { skill: activity.skill, activityId: activity.id, kind: summary.kind };
          (st.savedMade[id] ||= {})[summary.kind === 'figure' ? 'figure' : 'video'] = st.savedMedia[id];
        }
        Studio.session.recallTurn(activity, id);
      });
    });
    Studio.bus.emit('session', st.session); Studio.bus.emit('drawings'); Studio.bus.emit('current', this.currentDrawing());
    return st.session;
  },
  heardNow: function (ids) {
    const said = Studio.state.said || {};
    return Object.fromEntries(ids.map(function (id) { return [id, said[id] || '']; }));
  },
  // One saved turn of a drawing's conversation, read back into what the page holds for it: the
  // child's latest words, what the companion last said, and how far down the rungs it has asked.
  recallTurn: function (activity, id) {
    const st = Studio.state, summary = activity.summary;
    if (activity.skill === 'confirmed-words') st.said[id] = summary.text;
    else if (activity.skill === 'art-feedback' && !summary.status) {
      const beat = summary.beat || 'opening';
      st.feedback[id] = beat.indexOf('rung-') === 0
        ? Object.assign({}, summary, { text: (st.feedback[id] || {}).text || summary.text, question: summary.question || summary.text }) : summary;
      if (beat.indexOf('rung-') === 0) st.asked[id] = Number(beat.split('-')[1]);
      else if (beat === 'opening' || !st.asked[id]) st.asked[id] = 1;
    }
  },
  // Clear a drawing's conversation for good ('conversation') or take back its last answer
  // ('last-round'), on the studio first; then what the page holds for it is read again from the
  // saved course, so the screen shows exactly what is left.
  forgetChat: function (id, which) {
    const st = Studio.state, sid = st.session, cid = st.courseId;
    return Promise.resolve(st.transport.forgetChat(sid, id, which)).then(function () {
      if (sid !== st.session) return false;
      [st.feedback, st.said, st.asked].forEach(function (held) { delete held[id]; });
      if (which === 'conversation') { delete st.drafts[id]; return true; }
      return Studio.portfolio.api('/' + encodeURIComponent(cid)).then(function (course) {
        if (sid !== st.session) return false;
        course.activities.forEach(function (activity) {
          if (activity.drawings.length === 1 && activity.drawings[0] === id) Studio.session.recallTurn(activity, id);
        });
        return true;
      });
    });
  },
  end: function (options) {
    const self = this, id = Studio.state.session, t = Studio.state.transport;
    if (!id) return Promise.resolve(false);
    if (this.ending && this.ending.id === id) return this.ending.promise;
    // Keep ownership of the old class while its deletion is in flight. A late
    // response must never release the URLs or clear the work of a newer class.
    const drawings = Studio.state.drawings.slice(), pending = { id: id, promise: null };
    this.ending = pending;
    const drafts = Object.assign({}, Studio.state.drafts);
    const courseId = Studio.state.courseId || id;
    // `local`: the studio has already closed the editor (a deleted class), so there is nothing to ask it.
    function release() {
      if (options && options.local) return null;
      return options && options.complete && t.completeCourse ? t.completeCourse(courseId) : t.forgetSession(id);
    }
    pending.promise = new Promise(function (resolve) {
      resolve(options && options.saveDrafts ? Promise.resolve(t.saveDrafts(id, drafts)).then(release) : release());
    }).then(function () {
      drawings.forEach(function (d) { self.releaseUrl(d.url); });
      if (Studio.state.session !== id) return false;
      Studio.state.drawings = []; Studio.state.current = null; Studio.state.ledger = []; Studio.state.results = {};
      Studio.state.session = null; Studio.state.courseId = null; Studio.state.mode = 'feedback'; Studio.state.modeHistory = [];
      Studio.state.chosen = []; Studio.state.asked = {}; Studio.state.said = {};
      Studio.state.teacherReviews = {}; Studio.state.feedback = {}; Studio.state.drafts = {}; Studio.state.motionDrafts = {};
      Studio.state.storyDraft = null; Studio.state.savedBook = null;
      Studio.bus.emit('ended', id); Studio.bus.emit('drawings'); Studio.bus.emit('current', null); Studio.bus.emit('ledger');
      return true;
    }, function (error) {
      if (Studio.state.session !== id) return false;
      throw error;
    }).finally(function () {
      if (self.ending === pending) self.ending = null;
    });
    return pending.promise;
  },
  addDrawing: function (blob, url, sessionId) {
    const self = this, id = sessionId === undefined ? Studio.state.session : sessionId;
    if (!this.isCurrent(id)) { this.releaseUrl(url); return Promise.resolve(null); }
    const t = Studio.state.transport;
    return new Promise(function (resolve) { resolve(t.addDrawing(id, blob)); }).then(function (res) {
      if (!self.isCurrent(id)) {
        self.releaseUrl(url);
        if (res.url !== url) self.releaseUrl(res.url);
        return null;
      }
      const d = { id: res.drawing_id, url: url || res.url, blob: blob };
      Studio.state.drawings.push(d); Studio.state.current = d.id;
      Studio.bus.emit('drawings'); Studio.bus.emit('current', d); return d;
    }, function (error) {
      self.releaseUrl(url);
      if (!self.isCurrent(id)) return null;
      throw error;
    });
  },
  // Deleted for good on the studio first; the page lets go of it only once that has happened, and
  // the picture beside it takes its place. Everything the page held about it goes with it.
  removeDrawing: function (id) {
    const self = this, st = Studio.state, sid = st.session;
    return Promise.resolve(st.transport.removeDrawing(sid, id)).then(function () {
      const at = st.drawings.findIndex(function (d) { return d.id === id; });
      if (sid !== st.session || at < 0) return false;
      self.releaseUrl(st.drawings[at].url);
      st.drawings.splice(at, 1);
      [st.feedback, st.said, st.asked, st.drafts, st.motionDrafts, st.teacherReviews].forEach(function (held) {
        if (held) delete held[id];
      });
      st.chosen = st.chosen.filter(function (x) { return x !== id; });
      if (st.current === id) {
        const next = st.drawings[Math.min(at, st.drawings.length - 1)];
        st.current = next ? next.id : null;
      }
      Studio.bus.emit('drawings'); Studio.bus.emit('current', self.currentDrawing());
      return true;
    });
  },
  select: function (id) {
    const d = Studio.state.drawings.find(function (x) { return x.id === id; });
    if (d) { Studio.state.current = id; Studio.bus.emit('current', d); }
  },
  currentDrawing: function () {
    return Studio.state.drawings.find(function (x) { return x.id === Studio.state.current; }) || null;
  },
  appendLedger: function (line) { Studio.state.ledger.push(line); Studio.bus.emit('ledger'); }
};
