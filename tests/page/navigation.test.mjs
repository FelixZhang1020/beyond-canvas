import test from 'node:test';
import assert from 'node:assert/strict';
import { loadStudio } from './load.mjs';

function runningClass(forgetSession) {
  const revoked = [];
  const S = loadStudio({ globals: { URL: { revokeObjectURL: url => revoked.push(url) } } });
  Object.assign(S.state, {
    session: 'class-1', transport: { forgetSession }, mode: 'book', modeHistory: ['feedback', 'move'],
    drawings: [{ id: 'drawing-1', url: 'blob:drawing-1' }], current: 'drawing-1', chosen: ['drawing-1'],
    said: { 'drawing-1': 'The bird is looking for its house.' }, asked: { 'drawing-1': 2 },
    feedback: { 'drawing-1': { text: 'A little bird.', question: 'Where is it going?' } },
    drafts: { 'drawing-1': 'An unfinished answer' }, results: { 'art-feedback': { text: 'A little bird.' } }
  });
  return { S, revoked };
}

test('switching classes retains work until the old class is successfully ended', async () => {
  let resolveEnd;
  const calls = [];
  const { S, revoked } = runningClass(id => {
    calls.push(id);
    return new Promise(resolve => { resolveEnd = resolve; });
  });
  const ending = S.session.end();
  assert.equal(S.state.session, 'class-1');
  assert.equal(S.state.drawings.length, 1);
  assert.equal(S.state.drafts['drawing-1'], 'An unfinished answer');
  assert.deepEqual(revoked, []);
  resolveEnd();
  await ending;
  assert.deepEqual(calls, ['class-1']);
  assert.equal(S.state.session, null);
  assert.equal(S.state.mode, 'feedback');
  for (const key of ['drawings', 'modeHistory', 'chosen']) assert.equal(S.state[key].length, 0, key);
  for (const key of ['said', 'asked', 'feedback', 'drafts', 'results']) assert.equal(Object.keys(S.state[key]).length, 0, key);
  assert.deepEqual(revoked, ['blob:drawing-1']);
});

test('a failed class switch preserves the session, drawing, answer and navigation history', async () => {
  const { S, revoked } = runningClass(() => Promise.reject(new Error('offline')));
  await assert.rejects(S.session.end(), /offline/);
  assert.equal(S.state.session, 'class-1');
  assert.equal(S.state.current, 'drawing-1');
  assert.equal(S.state.drawings.length, 1);
  assert.equal(S.state.said['drawing-1'], 'The bird is looking for its house.');
  assert.equal(S.state.feedback['drawing-1'].question, 'Where is it going?');
  assert.equal(S.state.drafts['drawing-1'], 'An unfinished answer');
  assert.equal(S.state.mode, 'book');
  assert.equal(S.state.modeHistory.length, 2);
  assert.deepEqual(revoked, []);
});

function deferred() {
  let resolve, reject;
  const promise = new Promise((yes, no) => { resolve = yes; reject = no; });
  return { promise, resolve, reject };
}

test('a late end response releases only old artwork and leaves the newer class untouched', async () => {
  const request = deferred();
  const { S, revoked } = runningClass(() => request.promise);
  const ending = S.session.end();
  const newer = [{ id: 'drawing-2', url: 'blob:drawing-2' }];
  Object.assign(S.state, { session: 'class-2', drawings: newer, current: 'drawing-2', drafts: { 'drawing-2': 'Keep this draft' } });
  const events = [];
  S.bus.on('current', value => events.push(value));
  request.resolve();
  assert.equal(await ending, false);
  assert.equal(S.state.session, 'class-2');
  assert.equal(S.state.drawings, newer);
  assert.equal(S.state.current, 'drawing-2');
  assert.equal(S.state.drafts['drawing-2'], 'Keep this draft');
  assert.deepEqual(events, []);
  assert.deepEqual(revoked, ['blob:drawing-1']);
});

test('repeated end calls share a pending request; a failed request can be retried', async () => {
  const request = deferred();
  let calls = 0;
  const { S } = runningClass(() => { calls++; return request.promise; });
  const first = S.session.end(), second = S.session.end();
  assert.equal(first, second);
  request.reject(new Error('offline'));
  await assert.rejects(first, /offline/);
  assert.equal(calls, 1);
  S.state.transport.forgetSession = () => { calls++; return Promise.resolve(); };
  assert.equal(await S.session.end(), true);
  assert.equal(calls, 2);
  assert.equal(S.state.session, null);
});

test('a pending no-session end cannot clear a class opened immediately afterwards', async () => {
  const { S, revoked } = runningClass(() => Promise.resolve());
  S.state.session = null;
  const ending = S.session.end();
  S.state.session = 'class-2';
  assert.equal(await ending, false);
  assert.equal(S.state.session, 'class-2');
  assert.equal(S.state.drawings.length, 1);
  assert.deepEqual(revoked, []);
});

test('an upload that finishes after switching classes cannot insert or select its old drawing', async () => {
  const upload = deferred();
  const { S, revoked } = runningClass(() => Promise.resolve());
  S.state.transport.addDrawing = id => { assert.equal(id, 'class-1'); return upload.promise; };
  const adding = S.session.addDrawing(new Blob(['sample']), 'blob:pending');
  const newer = [{ id: 'new-art', url: 'blob:new-art' }];
  Object.assign(S.state, { session: 'class-2', drawings: newer, current: 'new-art' });
  const events = [];
  S.bus.on('drawings', () => events.push('drawings'));
  S.bus.on('current', () => events.push('current'));
  upload.resolve({ drawing_id: 'old-art' });
  assert.equal(await adding, null);
  assert.equal(S.state.drawings, newer);
  assert.equal(S.state.current, 'new-art');
  assert.deepEqual(events, []);
  assert.deepEqual(revoked, ['blob:pending']);
});

test('ending a class rejects pending and new uploads even before deletion completes', async () => {
  const upload = deferred(), deletion = deferred();
  const { S, revoked } = runningClass(() => deletion.promise);
  let uploads = 0;
  S.state.transport.addDrawing = () => { uploads++; return upload.promise; };
  const adding = S.session.addDrawing(new Blob(['sample']), 'blob:pending');
  const ending = S.session.end();
  const tooLate = S.session.addDrawing(new Blob(['sample']), 'blob:too-late');
  assert.equal(uploads, 1);
  assert.equal(await tooLate, null);
  upload.resolve({ drawing_id: 'old-art' });
  assert.equal(await adding, null);
  assert.equal(S.state.drawings.length, 1);
  deletion.resolve(); await ending;
  assert.deepEqual(revoked.sort(), ['blob:drawing-1', 'blob:pending', 'blob:too-late'].sort());
});

test('a current upload still adds the drawing and emits its selection', async () => {
  const { S, revoked } = runningClass(() => Promise.resolve());
  S.state.transport.addDrawing = () => Promise.resolve({ drawing_id: 'drawing-2' });
  const selected = [];
  S.bus.on('current', drawing => selected.push(drawing.id));
  const drawing = await S.session.addDrawing(new Blob(['sample']), 'blob:drawing-2');
  assert.equal(drawing.id, 'drawing-2');
  assert.equal(S.state.current, 'drawing-2');
  assert.equal(S.state.drawings.length, 2);
  assert.deepEqual(selected, ['drawing-2']);
  assert.deepEqual(revoked, []);
});

test('upload errors remain visible for the active class but are ignored after switching', async () => {
  const { S, revoked } = runningClass(() => Promise.resolve());
  S.state.transport.addDrawing = () => Promise.reject(new Error('offline'));
  await assert.rejects(S.session.addDrawing(new Blob(['sample']), 'blob:failed'), /offline/);
  const request = deferred();
  S.state.transport.addDrawing = () => request.promise;
  const adding = S.session.addDrawing(new Blob(['sample']), 'blob:old-failed');
  S.state.session = 'class-2';
  request.reject(new Error('old failure'));
  assert.equal(await adding, null);
  assert.deepEqual(revoked, ['blob:failed', 'blob:old-failed']);
});


test('save-and-switch persists answer drafts before releasing the editor', async () => {
  const calls = [];
  const { S } = runningClass(id => { calls.push(['release', id]); return Promise.resolve(); });
  S.state.transport.saveDrafts = async (id, drafts) => { calls.push(['save', id, drafts['drawing-1']]); };
  await S.session.end({ saveDrafts: true });
  assert.deepEqual(calls, [['save', 'class-1', 'An unfinished answer'], ['release', 'class-1']]);
});

test('discard switches without saving drafts, while a save failure retains the editor', async () => {
  let releases = 0, saves = 0;
  const { S } = runningClass(() => { releases++; return Promise.resolve(); });
  S.state.transport.saveDrafts = async () => { saves++; throw new Error('storage unavailable'); };
  await assert.rejects(S.session.end({ saveDrafts: true }), /storage unavailable/);
  assert.equal(releases, 0);
  assert.equal(S.state.drafts['drawing-1'], 'An unfinished answer');
  assert.equal(S.state.session, 'class-1');
  await S.session.end({ saveDrafts: false });
  assert.equal(releases, 1);
  assert.equal(saves, 1);
  assert.equal(S.state.session, null);
});

test('editing a saved course restores its drafts without confirming the words', () => {
  const S = loadStudio();
  S.session.restore({ session_id: 'editor', course: { id: 'course', entrance: 'colour', language: 'zh',
    drawings: [{ id: 'art', url: '/art' }], activities: [], drafts: { art: '还没确认 🌻' } } });
  assert.equal(S.state.drafts.art, '还没确认 🌻');
  assert.deepEqual(Object.keys(S.state.said), []);
});
