// Splat's voice: a warm standard voice, never one of the novelty voices, pitched up so it sounds playful.
window.Studio = window.Studio || {};
Studio.voice = {
  preferred: {
    en: ['Samantha', 'Karen', 'Moira', 'Tessa', 'Ava', 'Allison', 'Zoe', 'Daniel', 'Google US English', 'Microsoft Aria', 'Microsoft Zira'],
    zh: ['Tingting', 'Ting-Ting', 'Meijia', 'Mei-Jia', 'Sinji', 'Lili', 'Google \u666e\u901a\u8bdd', 'Microsoft Xiaoxiao', 'Microsoft Yunxi', 'Microsoft Huihui']
  },
  novelty: /albert|bad news|bahh|bells|boing|bubbles|cellos|deranged|good news|hysterical|jester|organ|superstar|trinoids|whisper|wobble|zarvox|eddy|reed|rocko|shelley|flo|grandma|grandpa|sandy|junior|ralph|kathy|fred|trinoids/i,
  voices: function () { return ('speechSynthesis' in window) ? speechSynthesis.getVoices() : []; },
  pick: function (lang) {
    const want = lang === 'zh' ? 'zh' : 'en', all = this.voices().filter(function (v) { return v.lang.replace('_', '-').toLowerCase().indexOf(want) === 0; });
    const clean = all.filter(function (v) { return !Studio.voice.novelty.test(v.name); });
    const names = this.preferred[want];
    for (let i = 0; i < names.length; i++) {
      const hit = clean.find(function (v) { return v.name.indexOf(names[i]) === 0; }); if (hit) return hit;
    }
    return clean.find(function (v) { return /enhanced|premium/i.test(v.name); }) || clean.find(function (v) { return v.localService; }) || clean[0] || null;
  },
  speak: function (text, opts) {
    if (!text || !('speechSynthesis' in window)) return null;
    opts = opts || {};
    const lang = Studio.i18n.lang === 'zh' ? 'zh-CN' : 'en-US', u = new SpeechSynthesisUtterance(text);
    u.lang = lang; u.rate = opts.rate || .95; u.pitch = opts.pitch || 1.35;
    const v = this.pick(Studio.i18n.lang); if (v) u.voice = v;
    if (opts.onend) u.onend = opts.onend;
    if (opts.onerror) u.onerror = opts.onerror;
    speechSynthesis.cancel(); speechSynthesis.speak(u);
    return u;
  }
};
if ('speechSynthesis' in window) speechSynthesis.addEventListener('voiceschanged', function () { Studio.voice.pick(Studio.i18n.lang); });
// Splat: the bubble, the open question, the steps a child can follow, and the voice.
Studio.companion = {
  els: {},
  lastText: '',
  init: function () {
    const q = function (id) { return document.getElementById(id); };
    this.els = { splat: q('splat'), bubble: q('bubble'), ask: q('ask'), steps: q('steps'), process: q('process'),
      say: q('btn-say'), next: q('btn-next'), open: q('btn-open'), openText: q('btn-open-text'), sticker: q('sticker'),
      answer: q('answer'), answered: q('btn-answered'),
      silent: q('btn-silent'), heard: q('heard'), heardText: q('heard-text') };
    const splatFace = this.els.splat;
    Studio.pet?.init(splatFace);
    const faces = [splatFace].concat(Array.from(document.querySelectorAll('.brand>i, #home-mascot .mascot-body')));
    let raf = null, ev = null;
    document.addEventListener('pointermove', function (e) {
      if (e.pointerType === 'touch') return;
      ev = e; if (raf === null) raf = requestAnimationFrame(look);
    });
    function look() {
      raf = null;
      faces.forEach(function (face) {
        const b = face.getBoundingClientRect();
        if (!b.width || !b.height) return;
        const dx = ev.clientX - (b.left + b.width / 2), dy = ev.clientY - (b.top + b.height / 2);
        const d = Math.hypot(dx, dy) || 1;
        const range = face === splatFace ? 3 : Math.min(8, b.width / 22);
        const k = Math.min(1, d / 200) * range;
        const x = (dx / d * k).toFixed(1) + 'px', y = (dy / d * k).toFixed(1) + 'px';
        face.style.setProperty('--look-x', x); face.style.setProperty('--look-y', y);
        face.querySelectorAll('.pupil').forEach(function (p) { p.style.transform = 'translate(' + x + ',' + y + ')'; });
      });
    }
    function resetLook() {
      if (raf !== null) cancelAnimationFrame(raf);
      raf = null;
      faces.forEach(function (face) {
        face.style.setProperty('--look-x', '0px'); face.style.setProperty('--look-y', '0px');
        face.querySelectorAll('.pupil').forEach(function (p) { p.style.transform = 'translate(0px,0px)'; });
      });
    }
    document.documentElement.addEventListener('pointerleave', resetLook);
    window.addEventListener('blur', resetLook);
    const mascot = q('home-mascot');
    if (mascot) {
      // Dragged somewhere of its own, it stays there and rests; a double-click sends it back to stroll.
      Studio.pet?.init(mascot, 'beyond-canvas.home-pet-position-v1');
      const floating = () => mascot.classList.contains('floating');
      let resetTimer = null, idleTimer = null, moodIndex = 0, idleIndex = 0;
      let lastPoke = 0, pokeCount = 0, visible = false, headingRight = true, engaged = false;
      const reducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)');
      function clearReaction() {
        clearTimeout(resetTimer);
        const currentLeft = mascot.offsetLeft;
        mascot.style.transitionDuration = '0s';
        if (!floating()) mascot.style.left = currentLeft + 'px';
        mascot.classList.remove('is-bouncing', 'is-pressed');
        delete mascot.dataset.action;
        delete mascot.dataset.mood;
      }
      function scheduleIdle() {
        clearTimeout(idleTimer);
        if (!visible || document.hidden || reducedMotion.matches || engaged) return;
        idleTimer = setTimeout(function () {
          if (mascot.classList.contains('is-pressed')) { scheduleIdle(); return; }
          const phase = idleIndex++ % 4;
          if ((phase === 0 || phase === 2) && !floating()) react('walk', 'happy', 6000);
          else react(phase === 3 ? 'nap' : 'rest', '', phase === 3 ? 8000 : 3500);
        }, 1200 + Math.random() * 1200);
      }
      function react(action, mood, duration) {
        clearTimeout(idleTimer);
        clearReaction();
        mascot.dataset.mood = mood;
        void mascot.offsetWidth;
        if (action === 'bounce') mascot.classList.add('is-bouncing');
        else mascot.dataset.action = action;
        if (action === 'walk') {
          mascot.style.transitionDuration = duration + 'ms';
          mascot.style.left = headingRight ? 'calc(100% - var(--pet-size))' : '0px';
          headingRight = !headingRight;
        }
        resetTimer = setTimeout(function () { clearReaction(); scheduleIdle(); }, duration);
      }
      const visibilityObserver = new IntersectionObserver(function (entries) {
        visible = entries[0].isIntersecting;
        if (!visible) { clearTimeout(idleTimer); clearReaction(); pokeCount = 0; }
        else scheduleIdle();
      });
      visibilityObserver.observe(mascot);
      document.addEventListener('visibilitychange', function () {
        if (document.hidden) { clearTimeout(idleTimer); clearReaction(); pokeCount = 0; }
        else scheduleIdle();
      });
      reducedMotion.addEventListener('change', function () { clearReaction(); scheduleIdle(); });
      const garden = mascot.parentElement;
      new ResizeObserver(function () {
        clearReaction();
        if (!floating()) mascot.style.left = Math.max(0, Math.min(mascot.offsetLeft, garden.clientWidth - mascot.offsetWidth)) + 'px';
        scheduleIdle();
      }).observe(garden);
      mascot.addEventListener('pointerenter', function () { engaged = true; clearTimeout(idleTimer); clearReaction(); });
      mascot.addEventListener('pointerleave', function () { engaged = mascot === document.activeElement; scheduleIdle(); });
      mascot.addEventListener('focus', function () { engaged = true; clearTimeout(idleTimer); clearReaction(); });
      mascot.addEventListener('blur', function () { engaged = false; scheduleIdle(); });
      const release = function () { mascot.classList.remove('is-pressed'); if (!mascot.dataset.mood) scheduleIdle(); };
      mascot.addEventListener('pointerdown', function (event) {
        if (!event.isPrimary || event.button !== 0) return;
        clearTimeout(idleTimer);
        clearReaction();
        mascot.classList.add('is-pressed');
        mascot.setPointerCapture(event.pointerId);
      });
      ['pointerup', 'pointercancel', 'lostpointercapture', 'blur'].forEach(function (name) {
        mascot.addEventListener(name, release);
      });
      mascot.addEventListener('keydown', function (event) {
        if (event.key === ' ' || event.key === 'Enter') {
          if (event.repeat) { event.preventDefault(); return; }
          mascot.classList.add('is-pressed');
        }
      });
      mascot.addEventListener('keyup', release);
      mascot.addEventListener('click', function () {
        release();
        const now = Date.now();
        pokeCount = now - lastPoke < 1400 ? pokeCount + 1 : 1;
        lastPoke = now;
        if (pokeCount >= 4) react('stomp', 'angry', 2400);
        else {
          const reactions = [['bounce', 'happy'], ['spin', 'surprised'], ['dance', 'wink']];
          const reaction = reactions[moodIndex++ % reactions.length];
          react(reaction[0], reaction[1], 2000);
        }
      });
      window.addEventListener('blur', release);
    }
    this.els.say.addEventListener('click', function () { Studio.courseHistory.playConversation(); });
    // Another drawing: the bridge playing for the last one is over, and holds nothing back.
    if (Studio.bus) Studio.bus.on('current', () => this.endBridge());
    this.say(Studio.i18n.t('greet'));
  },
  say: function (text, opts) {
    opts = opts || {};
    this.els.bubble.textContent = text; this.els.bubble.classList.toggle('typing', !!opts.typing);
    if (Studio.courseHistory && !opts.typing) Studio.courseHistory.clearDraft();
    if (opts.typing) { this.els.say.hidden = true; return; }
    this.lastText = text; this.lastSpoken = text; this.els.say.hidden = !text;
  },
  // The companion is writing, or checking what it wrote against the rules. None of it is shown
  // until it has passed (operator: "like a real chat"): the thread shows it typing,
  // and the bubble, there only while a drawing has no conversation yet, says for how long.
  // Nothing unchecked is ever spoken either; only the checked result is (operator).
  checking: function (draft, since) {
    if (draft.drawing && Studio.state.current !== draft.drawing) return;
    const s = Math.round((Date.now() - since) / 1000);
    this.els.bubble.textContent = Studio.i18n.t(draft.writing ? 'act.writing' : 'act.checking', { s: s });
    this.els.bubble.classList.add('typing');
    this.els.say.hidden = true;
  },
  // A request ended without its words: the thread stops typing.
  dropDraft: function () {
    if (Studio.courseHistory) Studio.courseHistory.clearDraft();
  },
  think: function (on) { this.els.splat.classList.toggle('thinking', !!on); },
  cancelSteps: function () {
    this.els.steps.querySelectorAll('.step.running').forEach(function (row) {
      row.className = 'step stopped';
      row.querySelector('.meta').textContent = Studio.i18n.t('status.stopped');
    });
  },
  clearResult: function () {
    document.getElementById('buddy').scrollTop = 0;
    this.els.process.open = true;
    this.els.ask.hidden = true; this.els.open.hidden = true; this.els.next.hidden = true;
    this.els.heard.hidden = true; this.els.heardText.value = '';
    this.els.steps.hidden = true; this.els.steps.querySelectorAll('.step').forEach(function (s) { s.remove(); });
  },
  showFeedback: function (out) {
    this.els.process.open = !!(out.rubric && out.rubric.failed && out.rubric.failed.length);
    this.say(out.text);
    this.ask();
    this.els.next.hidden = false;
    this.speak(out.text + ' ' + (out.question || ''));
    this.sticker(Studio.i18n.t('sticker.done'));
  },
  // Returning to an activity restores its words without replaying speech or generation.
  restoreFeedback: function (out, draft) {
    this.clearResult();
    if (!out) { this.say(Studio.i18n.t(Studio.state.current ? 'ready' : 'greet')); return; }
    this.say(out.text);
    this.ask();
    this.els.next.hidden = false;
    this.els.heardText.value = draft || '';
  },
  // Beat four. The child spoke, so Splat answers and stops asking: the reply
  // carries a question only when it came back with one.
  showReply: function (out) {
    this.els.process.open = !!(out.rubric && out.rubric.failed && out.rubric.failed.length);
    this.say(out.text);
    this.ask();
    this.els.next.hidden = false;
    this.speak(out.text + ' ' + (out.question || ''));
    this.sticker(Studio.i18n.t('sticker.heard'));
  },
  // Beat three. Nothing new to say, only a smaller door, so the bubble keeps
  // what Splat said before and the question is replaced.
  showRung: function (out) {
    this.els.process.open = !!(out.rubric && out.rubric.failed && out.rubric.failed.length);
    const question = out.question || out.text;
    this.ask();
    this.els.next.hidden = false;
    this.speak(question);
  },
  // After the companion speaks, the row for the child's next words is ready again, with the
  // smaller question on offer while there is one left to ask. The question the child is asked
  // ends the companion's own message in the thread and has no card of its own (operator).
  // The row stays even when a reply asks nothing, because section 5a asks a reply
  // to carry none once the child has said something whole, and the child may say more.
  ask: function () {
    this.els.ask.hidden = false;   // clearResult() hid the row; restoring a turn must bring it back
    this.els.heard.hidden = true;
    this.els.heardText.value = '';
    this.els.answer.hidden = false;
    this.els.silent.hidden = Studio.nextRung(Studio.state.asked[Studio.state.current]) === null;
  },
  // The teacher types what they heard, because listening is a model on the box
  // and is not built yet. The field appears only when it is wanted.
  openHeard: function () {
    this.els.heard.hidden = false; this.els.answer.hidden = true; this.els.heardText.focus();
  },
  offerOpen: function (label, fn) {
    this.els.openText.textContent = label; this.els.open.hidden = false; this.els.next.hidden = false;
    this.els.open.onclick = fn;
  },
  step: function (stage, status, meta) {
    const steps = this.els.steps; steps.hidden = false;
    let row = steps.querySelector('[data-stage="' + stage + '"]');
    if (!row) {
      row = document.createElement('span'); row.className = 'step'; row.dataset.stage = stage;
      row.innerHTML = '<i></i><span class="name"></span><span class="meta"></span>';
      row.querySelector('.name').textContent = Studio.stageLabel(stage); steps.appendChild(row);
    }
    const cls = status === 'gate_pass' || status === 'done' ? 'done' : status === 'stopped' || status === 'gate_fail' ? 'failed' : 'running';
    row.className = 'step ' + cls;
    row.querySelector('.meta').textContent = meta !== undefined ? meta : (cls === 'running' ? '' : Studio.i18n.t('status.' + status));
  },
  // The quick line said while the studio is still looking (studio/conversation/bridge.py; operator).
  // It is spoken at once; the checked answer that follows waits for it to finish, and is dropped
  // if the teacher has moved to another drawing by then. Twenty seconds is the longest it waits.
  bridge: function (text, drawing) {
    const self = this;
    if (drawing && Studio.state.current !== drawing) return;
    if (Studio.courseHistory) Studio.courseHistory.showBridge(text);
    this.bridging = { drawing: drawing, then: null };
    const release = function () {
      const held = self.bridging; if (!held) return;
      self.bridging = null; clearTimeout(self.bridgeTimer);
      if (held.then && (!held.drawing || Studio.state.current === held.drawing)) held.then();
    };
    this.bridgeTimer = setTimeout(release, 20000);
    Studio.voice.speak(text, { onend: release, onerror: release });
  },
  endBridge: function () { this.bridging = null; clearTimeout(this.bridgeTimer); },
  speak: function (text) {
    this.lastSpoken = text;
    if (this.bridging) { this.bridging.then = function () { Studio.voice.speak(text); }; return; }
    Studio.voice.speak(text);
  },
  sticker: function (text) {
    const s = this.els.sticker; s.textContent = text; s.classList.remove('pop'); void s.offsetWidth; s.classList.add('pop');
    setTimeout(function () { s.classList.remove('pop'); }, 2600);
  }
};
