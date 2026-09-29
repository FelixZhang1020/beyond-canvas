// A clip the course already has is shown as finished when a drawing is opened, never offered again.
// Found by the operator: after reopening a course, 让画动起来 showed "make it" for
// drawings with finished clips until a lookup came back, sometimes long after, and a teacher who
// pressed it would spend a quarter of an hour of the Spark on a clip the course already kept.
import test from 'node:test';
import assert from 'node:assert/strict';
import { loadStudio } from './load.mjs';

const COURSE = { id: 'c1', language: 'zh', entrance: 'colour', drafts: {},
  drawings: [{ id: 'a', url: '/a' }, { id: 'b', url: '/b' }, { id: 'c', url: '/c' }],
  activities: [
    { id: 'v1', skill: 'painting-to-animation', drawings: ['a'], summary: { kind: 'video', scene_description: 'A bear walks.' } },
    { id: 'v2', skill: 'painting-to-animation', drawings: ['a'], summary: { kind: 'video', scene_description: 'A bear runs.' } },
    { id: 'f1', skill: 'painting-to-figure', drawings: ['b'], summary: { kind: 'figure' } },
    { id: 'h1', skill: 'painting-to-animation', drawings: ['c'], summary: { kind: 'text', status: 'stopped' } },
  ] };

// The planner on a course reopened the way the page reopens one: through restore(), which reads it in full.
function reopened(course = COURSE, api = null) {
  const handlers = {}, asked = [], opened = [];
  const root = { hidden: true, innerHTML: '', addEventListener: (name, fn) => handlers[name] = fn, querySelector: () => ({ disabled: false }) };
  const app = { dataset: {} };
  const S = loadStudio({ files: ['src/29a-creation.js', 'src/29h-lanes.js'], globals: {
    queueMicrotask: () => {}, document: { getElementById: id => id === 'creation-planner' ? root : app } } });
  S.portfolio = { api: path => { asked.push(path); return api ? api(path) : new Promise(() => {}); } };
  S.creation.init({ active: () => true, run: () => {}, stop: () => {}, open: result => opened.push(result) });
  S.session.restore({ session_id: 's1', course });
  S.state.mode = 'move';
  const show = id => { S.state.current = id; S.creation.render(); return root.innerHTML; };
  const click = dataset => handlers.click({ target: { closest: () => ({ dataset, disabled: false }) } });
  return { S, show, click, asked, opened };
}

test('a drawing whose clip the course already has opens on it at once, and nothing is asked again', () => {
  const { show, asked } = reopened();
  const page = show('a');
  assert.match(page, /这幅画的作品/);
  assert.match(page, /data-create="open-(video|figure)"/);
  assert.doesNotMatch(page, /生成描述/, 'a finished clip is never offered to be made again');
  assert.match(show('b'), /data-create="open-figure"/, 'a finished figure too');
  assert.deepEqual(asked, [], 'the course was read when it opened; there is nothing to wait for');
});

test('a drawing with nothing finished offers the first step at once, never a wait', () => {
  const { show, asked } = reopened();
  const page = show('c');
  assert.match(page, /data-create="edit-video"/, 'a clip held back by the check is not a finished clip');
  assert.doesNotMatch(page, /data-create="open-video"/);
  assert.deepEqual(asked, []);
});

test('going back to edit a finished drawing lands on the first step with its buttons', () => {
  const { show, click } = reopened();
  show('a'); click({ create: 'edit' });
  const page = show('a');
  assert.match(page, /data-create="confirm"/);
  assert.match(page, /A bear runs\./, 'the latest scene is what is edited');
});

test('reopening a course remembers the latest finished clip or figure of each drawing', () => {
  const { S } = reopened();
  assert.equal(S.state.savedMedia.a.activityId, 'v2');
  assert.equal(S.state.savedMedia.b.kind, 'figure');
  assert.equal(S.state.savedMedia.c, undefined);
});

test('reopening a drawing with both saved outcomes shows both even if figure creation is unavailable now', () => {
  const course = {...COURSE, activities: [...COURSE.activities,
    {id: 'f2', skill: 'painting-to-figure', drawings: ['a'], summary: {kind: 'figure'}}]};
  const { S, show, asked } = reopened(course);
  const page = show('a');
  assert.equal(S.state.savedMade.a.video.activityId, 'v2');
  assert.equal(S.state.savedMade.a.figure.activityId, 'f2');
  assert.match(page, /data-create="open-video"/);
  assert.match(page, /data-create="open-figure"/);
  assert.doesNotMatch(page, /data-create="edit-figure"/, 'an unavailable generator is not offered');
  assert.deepEqual(asked, [], 'the two result cards do not fetch media until opened');
});

test('a slow saved result does not open over a different drawing', async () => {
  let deliver;
  const pending = new Promise(resolve => { deliver = resolve; });
  const { S, show, click, opened } = reopened(COURSE, () => pending);
  show('a'); click({create: 'open-video'});
  show('b'); deliver({outputs: {video_url: '/saved.mp4'}});
  await pending; await Promise.resolve();
  assert.equal(opened.length, 0);
  show('a'); click({create: 'open-video'});
  assert.equal(opened.length, 1, 'the loaded result is still available on its own drawing');
});

test('a new class carries nothing over from the course open before it', async () => {
  const S = loadStudio({ globals: {} });
  S.state.savedMedia = { a: { skill: 'painting-to-animation', activityId: 'v1', kind: 'video' } };
  S.state.transport = { createSession: () => Promise.resolve({ session_id: 's2', course_id: 'c2' }) };
  await S.session.begin({ entrance: 'colour' });
  assert.deepEqual({ ...S.state.savedMedia }, {});
});

test('a finished figure shows a picture of itself on its card, drawn by the studio from the saved toy', () => {
  // Operator: the clip's card shows its drawing while the figure's showed an empty diamond.
  const { show, asked } = reopened();
  const page = show('b');
  assert.match(page, /<img class="creation-result-figure" src="\/api\/courses\/c1\/activities\/f1\?preview=1"/);
  assert.doesNotMatch(page, /◇/, 'the diamond is for a card with nothing made yet');
  assert.deepEqual(asked, [], 'the picture is an image the browser fetches, not a lookup the planner waits on');
});
