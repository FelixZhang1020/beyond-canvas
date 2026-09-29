// A clip is made beside a conversation (operator). One "busy" used to hold the whole
// class: every tab's big button turned into Stop, and a teacher who pressed it on 老师评价 threw away a
// twelve-minute clip. Driven through the page's own wiring, with its surroundings stood in.
import test from 'node:test';
import assert from 'node:assert/strict';
import { loadStudio } from './load.mjs';

function page() {
  class Element {
    hidden = true; value = ''; dataset = {}; style = {}; textContent = ''; listeners = {}; disabled = false;
    parentElement = {}; firstChild = { dataset: {} };
    classList = { add() {}, remove() {}, toggle() {} };
    querySelector() { return this.child ||= new Element(); }
    querySelectorAll() { return []; }
    addEventListener(name, callback) { this.listeners[name] = callback; }
    setAttribute() {} prepend() {} refresh() {} select() {} appendChild() {}
    click() { return this.listeners.click(); }
  }
  const elements = new Map(), el = id => {
    if (!elements.has(id)) elements.set(id, new Element()); return elements.get(id);
  };
  let boot;
  const S = loadStudio({ files: ['src/29b-task-status.js', 'src/29c-task-navigation.js', 'src/29h-lanes.js', 'src/29i-microphones.js', 'src/29j-studio-replies.js', 'src/29k-main-button.js', 'src/30-main.js'], globals: {
    URLSearchParams, location: { search: '', protocol: 'http:' }, setTimeout: () => 1, setInterval: () => 1, clearInterval() {},
    addEventListener() {}, document: { readyState: 'loading', getElementById: el,
      addEventListener: (_, fn) => { boot = fn; }, querySelectorAll: () => [], createElement: () => new Element() }
  } });
  const quiet = () => {}, said = [], progress = [];
  S.glass = S.dialogs = { init: quiet };
  S.companion = { els: { next: {} }, init: quiet, clearResult: quiet, restoreFeedback: quiet, say: text => said.push(text), think: quiet, step: quiet,
    cancelSteps: quiet, dropDraft: quiet, checking: quiet, showFeedback: quiet, sticker: quiet, offerOpen: quiet, bridge: quiet };
  S.listen = { release: quiet }; S.book = { stop: quiet }; S.voice = {};
  S.textStream = { drop: quiet, partial: quiet, settle: quiet };   // 29g-text-stream.js
  S.media = { close: quiet, clearQueue: quiet, queue: quiet, open: quiet };
  S.sketchWorkbench = { refresh: quiet, close: quiet, beginGeneration: quiet, generationTick: line => progress.push(line), generationFailed: quiet };
  S.portfolio = { selected: {}, init(actions) { this.actions = actions; }, message: quiet, close: quiet, open: quiet };
  S.transports = { http: { health: () => new Promise(() => {}) } };
  boot();
  const calls = [];
  Object.assign(S.state, { session: 's', courseId: 'c', mode: 'move', current: 'a', settings: { entrance: 'sketch' },
    drawings: [{ id: 'a', url: '/a' }, { id: 'b', url: '/b' }], transport: { request(sid, skill, ids, opts, reply) {
      const call = { skill, opts, reply, aborted: false }; calls.push(call); return { abort() { call.aborted = true; } };
    } } });
  S.portfolio.actions.editCourse({ id: 'c' });   // into the class, off the home screen
  const show = (mode, current) => { S.state.mode = mode; if (current) S.state.current = current; S.bus.emit('capabilities'); };
  const button = () => ({ text: el('primary-text').textContent, disabled: el('btn-primary').disabled });
  return { S, el, calls, show, button, said, progress, t: key => S.i18n.t(key) };
}

test('the 3D viewer receives submitted and later task phases while it runs', () => {
  const { el, calls, progress, t } = page();
  el('btn-primary').click();
  assert.ok(progress.at(-1).includes(t('task.submitting')));
  calls[0].reply({stage:'sketch-to-3d',status:'loading'});
  assert.ok(progress.at(-1).includes(t('task.loading')));
});

test('a teacher review starts while a 3D model is made, and Stop on its tab stops only the review', () => {
  const { S, el, calls, show, button, t } = page();
  el('btn-primary').click();
  assert.equal(calls[0].skill, 'sketch-to-3d');
  assert.equal(calls[0].opts.model_choice, 'auto');
  assert.equal(calls[0].opts.regenerate, false);
  assert.equal(S.state.making, 'sketch-to-3d');
  assert.deepEqual(button(), { text: t('act.stop'), disabled: false }, 'Stop where the model was asked for');
  show('teacher');
  assert.deepEqual(button(), { text: t('teacher.generate'), disabled: false }, 'the teacher tab is free to use');
  el('btn-primary').click();
  assert.equal(calls[1].skill, 'teacher-review', 'the press started a review; it used to stop the model');
  assert.equal(calls[0].aborted, false);
  assert.equal(S.state.busy, true);
  el('btn-primary').click();
  assert.equal(calls[1].aborted, true, 'Stop on the review tab stops the review');
  assert.equal(calls[0].aborted, false, 'and never the model being made');
  assert.equal(S.state.making, 'sketch-to-3d');
});

test('regenerating an open sketch bypasses its earlier result', () => {
  const { S, el, calls } = page();
  S.sketchWorkbench.hasModelFor = 'a';
  el('btn-primary').click();
  assert.equal(calls[0].opts.model_choice, 'trellis2');
  assert.equal(calls[0].opts.regenerate, true);
});

test('away from where a job began, the big button says it is running and does nothing', () => {
  const { S, el, calls, show, button, t } = page();
  el('btn-primary').click();                      // the 3D model, from drawing a
  show('move', 'b');
  assert.deepEqual(button(), { text: t('act.elsewhere.make'), disabled: true });
  el('btn-primary').click();
  assert.equal(calls.length, 1); assert.equal(calls[0].aborted, false);
  show('teacher', 'a'); el('btn-primary').click();  // a review from 老师评价
  show('feedback');
  assert.deepEqual(button(), { text: t('act.elsewhere.talk'), disabled: true });
  el('btn-primary').click();
  assert.equal(calls[1].aborted, false);
  show('move', 'a');
  assert.deepEqual(button(), { text: t('act.stop'), disabled: false }, 'back where it began, Stop returns');
});

test('each result goes to its own lane, and the next child leaves the model being made alone', () => {
  const { S, el, calls, show } = page();
  el('btn-primary').click();
  show('teacher'); el('btn-primary').click();
  calls[1].reply({ status: 'done', outputs: { text: 'A report.' } });
  assert.equal(S.state.busy, false); assert.equal(S.state.making, 'sketch-to-3d');
  assert.equal(S.state.teacherReviews.a.text, 'A report.');
  show('feedback'); el('btn-next').click();
  assert.equal(calls[0].aborted, false, 'the next child is a conversation, not the end of the model');
  calls[0].reply({ status: 'done', outputs: { glb_url: '/a.glb' } });
  assert.equal(S.state.making, null);
  assert.equal(el('task-return').hidden, false, 'finished out of sight, the model waits behind 返回当前任务');
});

test('a job refused while the teacher was elsewhere is told once, on return', () => {
  // Found by review: the waiting refusal kept its worded form and was worded again on return,
  // "失败 · 失败 · …". Two lanes make being elsewhere the ordinary case.
  const { S, el, calls, show, said, t } = page();
  el('btn-primary').click();
  show('move', 'b');
  calls[0].reply({ stage: 'sketch-to-3d', status: 'stopped', reason_code: 'sketch_unsupported', message: 'Not a shape yet.' });
  assert.equal(S.state.making, null);
  el('task-return').onclick();
  const told = said.at(-1), failed = S.i18n.t('task.failed');
  assert.match(told, /Not a shape yet\./);
  assert.equal(told.split(failed).length - 1, 1, told);
});

test('a conversation during a clip says why it is slower', () => {
  const S = loadStudio({ files: ['src/29b-task-status.js', 'src/29c-task-navigation.js', 'src/29h-lanes.js'], globals: { clearInterval() {} } });
  const { lanes } = S;
  lanes.begin(lanes.make, 'painting-to-animation');
  lanes.begin(lanes.talk, 'art-feedback');
  assert.equal(S.state.busy, true); assert.equal(S.state.making, 'painting-to-animation');
  assert.match(lanes.line(lanes.talk), new RegExp(S.i18n.t('act.slowerWhileMaking')));
  assert.doesNotMatch(lanes.line(lanes.make), new RegExp(S.i18n.t('act.slowerWhileMaking')));
  lanes.end(lanes.talk);
  assert.equal(S.state.busy, false); assert.equal(S.state.making, 'painting-to-animation', 'ending one lane leaves the other');
});

test('a clip made online takes nothing from the Spark, so the conversation beside it is not called slower', () => {
  const S = loadStudio({ files: ['src/29b-task-status.js', 'src/29c-task-navigation.js', 'src/29h-lanes.js'], globals: { clearInterval() {} } });
  const { lanes } = S;
  lanes.begin(lanes.make, 'painting-to-animation', 'online');
  lanes.begin(lanes.talk, 'teacher-review');
  assert.doesNotMatch(lanes.line(lanes.talk), new RegExp(S.i18n.t('act.slowerWhileMaking')));
});
