// The studio keeps one editor per course, so opening a course again anywhere else ends this page's
// editor without telling it. Every call that belongs to the class then comes back session_gone, and
// what the page does next is what these cover: it takes the course back, keeps her words, repeats
// nothing by itself, and leaves her alone if she has already gone elsewhere.
import test from 'node:test';
import assert from 'node:assert/strict';
import { loadStudio } from './load.mjs';

const COURSE = {
  id: 'c1', language: 'en', entrance: 'colour', lesson_intent: '', title: 'Snow bear',
  ended_at: null, drawings: [{ id: 'd1', url: '/api/courses/c1/drawings/d1' }, { id: 'd2', url: '/api/courses/c1/drawings/d2' }],
  activities: [], drafts: { d1: 'the older stored note' },
};

const GONE = { error: 'no such session: s1', code: 'session_gone' };

function refusing(body, status = 404) {
  return () => Promise.resolve({ ok: false, status, json: () => Promise.resolve(body) });
}

// The transport alone, with a page that only records whether it was asked to take the course back.
function transport(fetch) {
  const S = loadStudio({ files: ['src/23-transport-http.js'], globals: { fetch, FormData, EventSource: class {} } });
  const asked = [];
  S.rejoin = { start: () => { asked.push(true); return Promise.resolve(true); } };
  return { S, asked };
}

function studio(editCourse) {
  const modes = { select: () => {} }, said = [], released = [];
  const S = loadStudio({
    files: ['src/29f-rejoin.js'],
    globals: {
      document: { documentElement: {}, querySelectorAll: () => [], getElementById: id => (id === 'mode' ? modes : null) },
      URL: { revokeObjectURL: url => released.push(url) },
    },
  });
  S.companion = { say: text => said.push(text) };
  S.state.transport = { editCourse };
  S.state.session = 'gone-session'; S.state.courseId = 'c1';
  S.state.drawings = [{ id: 'd1', url: 'blob:one' }, { id: 'd2', url: 'blob:two' }];
  S.state.current = 'd2'; S.state.mode = 'move';
  return { S, said, released };
}

test('a request refused because the class was opened elsewhere carries its own reason, not a bare failure', async () => {
  const { S } = transport(refusing(GONE));
  const events = [];
  S.transports.http.request('s1', 'painting-to-animation', ['d1'], { media_kind: 'figure' }, ev => events.push(ev));
  await new Promise(resolve => setTimeout(resolve, 0));
  assert.equal(events.at(-1).reason_code, 'session_gone');
  assert.match(events.at(-1).message, /在别的窗口/);
});

test('a 404 the page cannot act on stays a plain submission failure', async () => {
  const { S, asked } = transport(refusing({ error: "no such drawing: ['d9']", code: 'not_found' }));
  const events = [];
  S.transports.http.request('s1', 'painting-to-animation', ['d9'], {}, ev => events.push(ev));
  await new Promise(resolve => setTimeout(resolve, 0));
  assert.equal(events.at(-1).reason_code, 'submission_failed');
  assert.deepEqual(asked, [], 'a drawing this class never had is nothing the page can rejoin from');
});

test('a body that is not JSON cannot turn a refusal into something the page acts on', async () => {
  const { S, asked } = transport(() => Promise.resolve({ ok: false, status: 502, json: () => Promise.reject(new Error('not json')) }));
  const events = [];
  S.transports.http.request('s1', 'art-feedback', ['d1'], {}, ev => events.push(ev));
  await new Promise(resolve => setTimeout(resolve, 0));
  assert.equal(events.at(-1).reason_code, 'submission_failed');
  assert.deepEqual(asked, []);
});

test('a photograph, a recording, a saved draft and a settings change all take the course back', async () => {
  // Every one of these is the teacher working inside a class, and every one of them used to end in
  // a message she could do nothing with. 让画动起来's own request is covered above.
  const calls = [
    ['addDrawing', s => s.addDrawing('s1', new Blob())],
    ['hear', s => s.hear('s1', new Blob())],
    ['speak', s => s.speak('s1', 'hello', 'splat', {})],
    ['saveDrafts', s => s.saveDrafts('s1', { d1: 'typed' })],
    ['updateSettings', s => s.updateSettings('s1', { language: 'zh', lessonIntent: '' })],
  ];
  for (const [name, call] of calls) {
    const { S, asked } = transport(refusing(GONE));
    await call(S.transports.http).then(() => assert.fail(name + ' should have refused'), () => {});
    assert.deepEqual(asked, [true], name + ' did not ask for the course back');
  }
});

test('nothing that LEAVES a class reopens it', async () => {
  // Reopening a course the teacher is closing is the one thing worse than the refusal itself.
  const { S, asked } = transport(refusing(GONE));
  const http = S.transports.http;
  await http.forgetSession('s1').then(() => {}, () => {});
  await http.completeCourse('c1').then(() => {}, () => {});
  await http.editCourse('c1', false).then(() => {}, () => {});
  assert.deepEqual(asked, []);
});

test('nothing is listening is still not a lost class', async () => {
  // 503 from the hearing endpoint means no transcription on this box, which the contract calls
  // survivable: typing always works, and the class is perfectly alive.
  const { S, asked } = transport(() => Promise.resolve({ ok: false, status: 503, json: () => Promise.resolve({}) }));
  // Compared field by field: an object built inside the sandbox is not reference-equal to one
  // built out here, whatever it holds.
  const heard = await S.transports.http.hear('s1', new Blob());
  assert.equal(heard.text, '');
  assert.equal(heard.listening, false);
  assert.deepEqual(asked, []);
});

test('the page takes the course back itself, on the picture and in the view the teacher was in', async () => {
  const asked = [];
  const { S, said, released } = studio((courseId, reopen) => {
    asked.push([courseId, reopen]);
    return Promise.resolve({ session_id: 'fresh', course: COURSE, capabilities: { image_edit: true } });
  });
  assert.equal(await S.rejoin.start(), true);
  assert.deepEqual(asked, [['c1', false]]);
  assert.equal(S.state.session, 'fresh');
  assert.equal(S.state.current, 'd2', 'the teacher was on the second picture, not the first');
  assert.equal(S.state.mode, 'move', 'and in the making view, which restore() would have left on feedback');
  assert.match(said.at(-1), /请再做一次/);
  assert.deepEqual(released.sort(), ['blob:one', 'blob:two'], 'the lost class’s pictures are let go of');
});

test('what the teacher had typed survives the course coming back, and is saved to the new editor', async () => {
  const saved = [];
  const { S } = studio(() => Promise.resolve({ session_id: 'fresh', course: COURSE }));
  S.state.transport.saveDrafts = (sid, drafts) => { saved.push([sid, drafts]); return Promise.resolve(null); };
  S.state.drafts = { d1: 'what she just typed' };
  S.state.motionDrafts = { d2: 'the bear walks into the snow' };
  await S.rejoin.start();
  assert.equal(S.state.drafts.d1, 'what she just typed', 'her words, not the older stored note');
  assert.equal(S.state.motionDrafts.d2, 'the bear walks into the snow');
  assert.equal(saved.length, 1);
  assert.equal(saved[0][0], 'fresh');
  assert.equal(saved[0][1].d1, 'what she just typed');
});

test('a draft only the other window has is left alone', async () => {
  const { S } = studio(() => Promise.resolve({ session_id: 'fresh', course: COURSE }));
  S.state.drafts = {};
  await S.rejoin.start();
  assert.equal(S.state.drafts.d1, 'the older stored note', 'nothing of hers to put back, so the stored one stands');
});

test('the course is never repeated or resent by the page itself', async () => {
  const { S } = studio(() => Promise.resolve({ session_id: 'fresh', course: COURSE }));
  let sent = 0, photos = 0;
  S.creation = { stopped: () => {}, render: () => {} };
  S.state.transport.request = () => { sent += 1; };
  S.state.transport.addDrawing = () => { photos += 1; return Promise.resolve({}); };
  await S.rejoin.start();
  assert.equal(sent, 0, 'spending a model is the teacher’s decision');
  assert.equal(photos, 0, 'a photograph the studio never received is not the page’s to send again');
});

test('a press lands nowhere while the course is being taken back', async () => {
  let release;
  const { S } = studio(() => new Promise(resolve => { release = resolve; }));
  const running = S.rejoin.start();
  assert.equal(S.rejoin.busy, true);
  release({ session_id: 'fresh', course: COURSE });
  await running;
  assert.equal(S.rejoin.busy, false);
});

test('a teacher who has already gone elsewhere is not pulled back', async () => {
  // She left for the Portfolio, or opened another course, while the studio was answering. Taking
  // this one back now would move her against her will, so the fresh editor is let go instead.
  let release;
  const forgotten = [];
  const { S, said } = studio(() => new Promise(resolve => { release = resolve; }));
  S.state.transport.forgetSession = id => { forgotten.push(id); return Promise.resolve(null); };
  const running = S.rejoin.start();
  S.state.session = null; S.state.courseId = null;
  release({ session_id: 'fresh', course: COURSE });
  assert.equal(await running, false);
  assert.deepEqual(forgotten, ['fresh'], 'the editor nobody is in is given back');
  assert.equal(S.state.session, null, 'she is left where she went');
  assert.deepEqual(said, [], 'and told nothing about a class she has left');
});

test('when the course cannot be taken back the teacher is told to reload, not to submit again', async () => {
  const { S, said } = studio(() => Promise.reject(new Error('HTTP 409')));
  assert.equal(await S.rejoin.start(), false);
  assert.match(said.at(-1), /请刷新页面/);
  assert.doesNotMatch(said.at(-1), /重新提交/);
});

// A storybook outline as the studio has it saved, so restore() rebuilds one from the course.
const COURSE_WITH_STORY = Object.assign({}, COURSE, {
  activities: [{
    skill: 'story-outline', drawings: ['d1', 'd2'],
    summary: { outline: [{ text: 'the outline the studio had saved' }], scenes: [] },
  }],
});

test('the pictures she had chosen survive the course coming back', async () => {
  const { S } = studio(() => Promise.resolve({ session_id: 'fresh', course: COURSE }));
  S.state.chosen = ['d2'];
  await S.rejoin.start();
  assert.deepEqual(S.state.chosen, ['d2'], 'restore() empties the selection; hers goes back on top');
});

test('the storybook outline she had edited survives, and the saved one does not overwrite it', async () => {
  const { S } = studio(() => Promise.resolve({ session_id: 'fresh', course: COURSE_WITH_STORY }));
  S.state.storyDraft = { ids: ['d1', 'd2'], pages: [{ text: 'the page as she has just rewritten it' }], scenes: [] };
  await S.rejoin.start();
  assert.equal(S.state.storyDraft.pages[0].text, 'the page as she has just rewritten it',
    'hers is newer than the course’s saved outline, and she was mid-edit when the class was taken');
});

test('an outline only the other window has is left alone', async () => {
  const { S } = studio(() => Promise.resolve({ session_id: 'fresh', course: COURSE_WITH_STORY }));
  S.state.storyDraft = null;
  await S.rejoin.start();
  assert.equal(S.state.storyDraft.pages[0].text, 'the outline the studio had saved',
    'nothing of hers to put back, so the stored one stands');
});

test('a picture the other window removed is dropped from what she had chosen', async () => {
  const { S } = studio(() => Promise.resolve({ session_id: 'fresh', course: COURSE }));
  S.state.chosen = ['d2', 'd9'];
  await S.rejoin.start();
  assert.deepEqual(S.state.chosen, ['d2'],
    'choosing a picture the course no longer has would fail on her next press, for a reason she cannot see');
});

// After a studio restart every class is forgotten, and the first Send of a child's words said it did not
// go (operator). Chat words, and only those, go once more to the class taken back.
async function settle() { for (let i = 0; i < 8; i += 1) await new Promise(resolve => setTimeout(resolve, 0)); }

function sending(answers) {
  const posts = [];
  const fetch = url => {
    posts.push(url);
    const answer = answers[Math.min(posts.length - 1, answers.length - 1)];
    return answer === 'gone' ? refusing(GONE)()
      : Promise.resolve({ ok: true, status: 200, json: () => Promise.resolve({ request_id: 'r2' }) });
  };
  const S = loadStudio({ files: ['src/23-transport-http.js'],
    globals: { fetch, FormData, EventSource: class { addEventListener() {} close() {} } } });
  const quiet = [], unsent = [], events = [];
  S.rejoin = { start: opts => { quiet.push(!!(opts && opts.quiet)); S.state.session = 's2'; return Promise.resolve(true); } };
  S.bus.on('unsent', payload => unsent.push(payload));
  return { S, posts, quiet, unsent, events };
}

test('a child\'s words sent to a class the studio forgot go once more to the class taken back', async () => {
  const { S, posts, quiet, unsent, events } = sending(['gone', 'ok']);
  S.transports.http.request('s1', 'art-feedback', ['d1'], { transcript: 'the bear goes home' }, ev => events.push(ev));
  await settle();
  assert.deepEqual(posts, ['/api/session/s1/requests', '/api/session/s2/requests']);
  assert.deepEqual(quiet, [true], 'taken back quietly: the page is sending them again itself');
  assert.equal(events.at(-1).status, 'submitted');
  assert.deepEqual(unsent, [], 'nothing tells the teacher they did not go');
});

test('the words are sent again once, not chased round a studio that keeps forgetting', async () => {
  const { S, posts, unsent, events } = sending(['gone']);
  S.transports.http.request('s1', 'art-feedback', ['d1'], { transcript: 'the bear goes home' }, ev => events.push(ev));
  await settle();
  assert.equal(posts.length, 2);
  assert.equal(events.at(-1).reason_code, 'session_gone');
  assert.equal(unsent.length, 1);
});

test('a creation task is still not sent again by the page', async () => {
  const { S, posts, events } = sending(['gone', 'ok']);
  S.transports.http.request('s1', 'painting-to-animation', ['d1'], { media_kind: 'video' }, ev => events.push(ev));
  await settle();
  assert.equal(posts.length, 1, 'spending a model on a clip is the teacher’s decision');
  assert.equal(events.at(-1).reason_code, 'session_gone');
});

test('a class taken back quietly says nothing to the teacher, and one that cannot be still says to reload', async () => {
  const back = studio(() => Promise.resolve({ session_id: 'fresh', course: COURSE }));
  back.S.creation = { stopped: () => { throw Error('nothing stopped'); }, render: () => {} };
  assert.equal(await back.S.rejoin.start({ quiet: true }), true);
  assert.deepEqual(back.said, []);
  const lost = studio(() => Promise.reject(new Error('HTTP 409')));
  assert.equal(await lost.S.rejoin.start({ quiet: true }), false);
  assert.match(lost.said.at(-1), /请刷新页面/);
});
