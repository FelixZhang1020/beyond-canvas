import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { loadStudio } from './load.mjs';

// Exercise the actual page event wiring with a pending/failing archive response.
function page() {
  class Element {
    hidden = true; value = ''; dataset = {}; style = {}; textContent = ''; listeners = {};
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
  let boot; const windowEvents = {}, made = [];
  const S = loadStudio({ files: ['src/29h-lanes.js', 'src/29i-microphones.js', 'src/29j-studio-replies.js', 'src/29k-main-button.js', 'src/30-main.js'], globals: {
    URLSearchParams, location: { search: '', protocol: 'http:' }, setTimeout: () => 1,
    addEventListener(name, fn) { windowEvents[name] = fn; }, document: { readyState: 'loading', getElementById: el,
      addEventListener: (_, fn) => { boot = fn; }, querySelectorAll: () => [],
      createElement: () => { const node = new Element(); made.push(node); return node; } }
  } });
  S.i18n.set = () => {};
  S.glass = S.dialogs = { init() {} };
  S.companion = { els: {}, init() {}, clearResult() {}, restoreFeedback() {}, say() {} };
  S.listen = { release() {} }; S.book = { stop() {} }; S.media = { close() {} }; S.voice = {};
  S.sketchWorkbench = { refresh() {}, close() {} };
  S.portfolio = { selected: {}, init(actions) { this.actions = actions; }, message() {}, close() { el('portfolio').hidden = true; },
    openCourse(id) { (this.openedCourses ||= []).push(id); el('portfolio').hidden = false; },
    open() { this.listOpens = (this.listOpens || 0) + 1; el('portfolio').hidden = false; } };
  S.transports = { http: { health: () => new Promise(() => {}) } };
  boot();
  Object.assign(S.state, { session: 'course-1', transport: {} });
  return { S, el, windowEvents, made };
}

test('choosing another drawing in the chat keeps the row for the child\'s words', () => {
  // Operator's class page: a teacher picked the next drawing in 聊聊你的画 and the record button and the
  // typing box went away, until she left the chat and came back.
  const { S, el, made } = page();
  S.companion.restoreFeedback = () => { el('heard').hidden = true; };   // as the companion's ask() does
  Object.assign(S.state, { courseId: 'course-1', current: 'a', mode: 'feedback',
    feedback: { a: { text: 'A cube.' }, b: { text: 'A pear.' } },
    drawings: [{ id: 'a', url: '/a' }, { id: 'b', url: '/b' }], settings: { entrance: 'sketch', language: 'zh' } });
  const before = made.length;
  S.bus.emit('drawings');
  const [, second] = made.slice(before).filter(b => b.listeners.click);
  second.click();
  assert.equal(S.state.current, 'b');
  assert.equal(el('heard').hidden, false, 'the record button and the typing box are there for the new drawing');
});

test('ending opens the completed course only after saving; repeated clicks share the transition', async () => {
  const { S, el } = page(); let finish, calls = 0;
  S.state.transport.completeCourse = () => { calls++; return new Promise(resolve => { finish = resolve; }); };
  S.portfolio.actions.completeCourse('course-1');
  assert.equal(el('end-class-overlay').hidden, false);
  el('end-class-confirm').click(); el('end-class-confirm').click();
  assert.equal(calls, 1); assert.equal(S.state.session, 'course-1');
  assert.equal(el('portfolio').hidden, true, 'pending saves keep the classroom visible');
  assert.equal(el('end-class-overlay').hidden, false, 'the confirmation stays visible until the save succeeds');
  assert.equal(el('end-class-confirm').disabled, true);
  finish(); await new Promise(setImmediate);
  assert.equal(S.state.session, null);
  assert.equal(el('end-class-overlay').hidden, true);
  assert.equal(el('portfolio').hidden, false, 'the completed course opens after the transition lock is released');
  assert.deepEqual(S.portfolio.openedCourses, ['course-1']);
  assert.equal(S.portfolio.listOpens, undefined, 'completion must not flash the course list first');
});

test('back from an unfinished course returns to the list without showing review', () => {
  const { S, el } = page();
  Object.assign(S.state, { courseId: 'course-1', mode: 'feedback' });
  el('btn-back').click();
  assert.equal(S.portfolio.listOpens, 1);
  assert.equal(S.portfolio.openedCourses, undefined);
});

test('cancelling or failing to save keeps the class available for another attempt', async () => {
  const { S, el } = page(); let calls = 0;
  S.state.transport.completeCourse = () => { calls++; return Promise.reject(new Error('storage unavailable')); };
  S.portfolio.actions.completeCourse('course-1'); el('end-class-cancel').click();
  assert.equal(calls, 0); assert.equal(S.state.session, 'course-1');
  S.portfolio.actions.completeCourse('course-1'); el('end-class-confirm').click(); await new Promise(setImmediate);
  assert.equal(S.state.session, 'course-1'); assert.equal(el('portfolio').hidden, true);
  assert.equal(el('end-class-overlay').hidden, false);
  assert.equal(el('end-class-status').textContent, S.i18n.t('end.failed'));
  assert.equal(el('end-class-confirm').disabled, false, 'a failed save can be retried');
  S.portfolio.actions.completeCourse('course-1'); assert.equal(el('end-class-overlay').hidden, false);
});

test('an unconfirmed completion keeps the confirmation open for retry', async () => {
  const { S, el } = page();
  S.session.end = async () => false;
  S.portfolio.actions.completeCourse('course-1'); el('end-class-confirm').click(); await new Promise(setImmediate);
  assert.equal(el('end-class-overlay').hidden, false);
  assert.equal(el('end-class-status').textContent, S.i18n.t('end.failed'));
  assert.equal(S.portfolio.openedCourses, undefined);
});

test('a review navigation error after saving does not claim the class is still open', async () => {
  const { S, el } = page();
  S.state.transport.completeCourse = async () => {};
  S.portfolio.openCourse = async () => { throw new Error('review unavailable'); };
  S.portfolio.actions.completeCourse('course-1'); el('end-class-confirm').click(); await new Promise(setImmediate);
  assert.equal(S.state.session, null);
  assert.equal(el('end-class-overlay').hidden, true);
  assert.notEqual(el('end-class-status').textContent, S.i18n.t('end.failed'));
});

test('the standalone button completes a new class by durable course ID, not temporary editor ID', async () => {
  const { S, el } = page(), completed = [];
  S.state.session = 'editor-2'; S.state.courseId = 'course-1';
  S.state.transport.completeCourse = async id => completed.push(id);
  S.state.transport.forgetSession = () => { throw new Error('Completion must use the explicit action'); };
  el('btn-end-course').click(); el('end-class-confirm').click(); await new Promise(setImmediate);
  assert.deepEqual(completed, ['course-1']); assert.equal(S.state.session, null);
});

test('pagehide releases the editor without marking the course ended', async () => {
  const { S, windowEvents } = page(), released = [];
  S.state.transport.forgetSession = async id => released.push(id);
  S.state.transport.completeCourse = () => { throw new Error('Leaving is not completion'); };
  windowEvents.pagehide(); await new Promise(setImmediate);
  assert.deepEqual(released, ['course-1']); assert.equal(S.state.session, null);
});

test('a saved course can be marked ended from its profile without an active editor', async () => {
  const { S, el } = page(), completed = [];
  S.state.session = null;
  S.state.transport.completeCourse = async id => completed.push(id);
  S.portfolio.actions.completeCourse('saved-course');
  el('end-class-confirm').click(); await new Promise(setImmediate);
  assert.deepEqual(completed, ['saved-course']);
});

// The class's run log ("画室做了什么") left system management: the operator saw it on an iPad and iPhone and
// said it is wrong, that 系统状态 has replaced it.
test('system management no longer offers the run log, in a class or out of one', () => {
  const markup = readFileSync(new URL('../../studio/page/src/10-app.html', import.meta.url), 'utf8');
  const main = readFileSync(new URL('../../studio/page/src/30-main.js', import.meta.url), 'utf8');
  assert.ok(!markup.includes('id="admin-ledger"'), 'the run log has no entry in system management');
  assert.ok(!main.includes('admin-ledger'), 'nothing shows or wires it');
  assert.ok(markup.includes('id="admin-board"'), 'system status is still there');
  const { el } = page();
  el('portfolio-admin').click();
  assert.equal(el('admin-overlay').hidden, false, 'system management still opens');
});

test('home and course reentry keep the current editor, drawing, activity and unsent answer', async () => {
  const { S, el } = page();
  Object.assign(S.state, { courseId: 'course-1', current: 'a', mode: 'move',
    drawings: [{ id: 'a', url: '/a' }, { id: 'b', url: '/b' }], settings: { entrance: 'colour', language: 'zh' } });
  S.state.transport.editCourse = () => assert.fail('Switching views must not create another editor');
  await S.portfolio.actions.editCourse({ id: 'course-1' }, false);  // back in through the class card
  el('heard').hidden = false; el('heard-text').value = 'Unsubmitted answer';
  S.portfolio.actions.home();
  assert.equal(el('portfolio').hidden, false);
  assert.equal(S.portfolio.selected['course-1'], 'a');
  assert.equal(S.state.drafts.a, 'Unsubmitted answer');
  await S.portfolio.actions.editCourse({ id: 'course-1' }, false, 'b');
  assert.equal(S.state.session, 'course-1'); assert.equal(S.state.current, 'b');
  assert.equal(S.state.mode, 'move'); assert.equal(S.state.drafts.a, 'Unsubmitted answer');
});

test('review keeps course navigation interactive; real dialogs still isolate their controls', () => {
  const header = { id: 'course-space' }, editor = { id: 'creation-workspace' };
  const portfolio = { id: 'portfolio', hidden: false, querySelectorAll: () => [] };
  const overlay = { id: 'end-class-overlay', hidden: true, querySelectorAll: () => [] };
  let sync;
  const root = { children: [header, editor, portfolio, overlay],
    querySelectorAll: selector => selector.includes('#portfolio') ? [portfolio, overlay] : [overlay] };
  const S = loadStudio({ files: ['src/24b-dialogs.js'], globals: {
    MutationObserver: class { constructor(fn) { sync = fn; } observe() {} },
    document: { getElementById: id => id === 'portfolio' ? portfolio : null, addEventListener() {} }
  } });
  S.dialogs.init(root);
  assert.equal(header.inert, false, 'course navigation is part of the page, not modal background');
  assert.equal(editor.inert, true);
  overlay.hidden = false; sync();
  assert.equal(header.inert, true); assert.equal(portfolio.inert, true); assert.equal(overlay.inert, false);
  overlay.hidden = true; sync(); assert.equal(header.inert, false);
});
