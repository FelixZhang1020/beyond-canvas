import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { loadStudio } from './load.mjs';

function deferred() {
  let resolve, reject;
  const promise = new Promise((yes, no) => { resolve = yes; reject = no; });
  return { promise, resolve, reject };
}

function setup() {
  class Element {
    children = []; dataset = {}; textContent = ''; value = ''; hidden = false;
    appendChild(child) { this.children.push(child); return child; }
    append(...children) { children.forEach(child => this.appendChild(child)); }
    replaceChildren(...children) { this.children = children; }
    querySelectorAll() { return []; }
    setAttribute(key, value) { this[key] = value; }
    set innerHTML(_) { throw new Error('Untrusted course content must not become HTML'); }
  }
  const elements = new Map();
  const el = id => { if (!elements.has(id)) elements.set(id, new Element()); return elements.get(id); };
  const S = loadStudio({ files: ['src/24c-portfolio.js'], globals: {
    URLSearchParams, Intl, Image: Element, document: { createElement: () => new Element(), getElementById: el }
  } });
  S.i18n.lang = 'zh';
  return { S, P: S.portfolio, el };
}

const course = (id, title = id) => ({ id, title, created_at: '2026-09-07T01:00:00+00:00', entrance: 'colour',
  lesson_intent: '', drawings: [], activities: [] });

test('course cards and header use only the durable completion state', () => {
  const { P, el } = setup();
  const open = { ...course('one'), drawing_count: 1, ended_at: null };
  const status = item => P.card(item).children[1].children[3].textContent;
  assert.equal(status({ ...open, active: false }), '未下课');
  assert.equal(status({ ...open, active: true }), '未下课');
  assert.equal(status({ ...open, active: true, ended_at: 'today' }), '已下课');
  P.showWorkspace(open, 'create'); assert.equal(el('space-state').textContent, '未下课');
  P.showWorkspace({ ...open, ended_at: 'today' }, 'review'); assert.equal(el('space-state').textContent, '已下课');
});

test('an open course keeps review hidden while its editor is pending', async () => {
  const { P, el } = setup(), pending = deferred(), opened = course('one');
  el('course-space').hidden = true; el('course-profile').hidden = true;
  P.api = async () => opened;
  P.init({ editCourse: async () => {
    await pending.promise;
    P.showWorkspace(opened, 'create'); P.close();
  } });
  const opening = P.openCourse('one');
  await Promise.resolve();
  assert.equal(el('course-profile').hidden, true, 'the empty review frame must not paint while editing opens');
  assert.equal(el('course-space').hidden, true, 'the review switch must not paint before creation is ready');
  assert.equal(el('portfolio').hidden, false);
  pending.resolve(); await opening;
  assert.equal(el('app').dataset.courseView, 'create');
  assert.equal(el('portfolio').hidden, true);
});

test('review appears only for a completed course; a failed editor stays out of review', async () => {
  const { P, el } = setup(), opened = course('one');
  el('course-profile').hidden = true;
  let revealed = 0;
  const profile = el('course-profile');
  Object.defineProperty(profile, 'hidden', { get() { return this._hidden; }, set(value) {
    this._hidden = value;
    if (!value) {
      revealed++;
      assert.equal(el('review-originals')['aria-pressed'], 'true', 'review cannot paint without a selected section');
    }
  } });
  P.api = async () => ({ ...opened, ended_at: 'today' });
  await P.openCourse('one');
  assert.equal(revealed, 1);
  el('review-originals')['aria-pressed'] = 'false';
  P.init({ editCourse: async () => { throw new Error('offline'); } });
  P.api = async () => opened;
  await P.openCourse('one');
  assert.equal(revealed, 1, 'an unfinished course must not reveal review after editor failure');
  assert.equal(el('course-profile').hidden, true);
  assert.equal(el('course-space').hidden, true);
  assert.equal(el('portfolio-retry').hidden, false, 'a failed editor offers a retry');
});

test('a late course response cannot replace a newer selected course', async () => {
  const { P, el } = setup(), old = deferred();
  P.api = path => path === '/old' ? old.promise : Promise.resolve({ ...course('new', '新的课程'), ended_at: 'today' });
  const opening = P.openCourse('old');
  await P.openCourse('new');
  old.resolve({ ...course('old', '旧的课程'), ended_at: 'today' }); await opening;
  assert.equal(P.detail.id, 'new'); assert.equal(el('space-title').textContent, '新的课程');
});

test('failure returns to an actionable course list, and retry can show real data', async () => {
  const { P, el } = setup();
  P.api = () => Promise.reject(new Error('offline'));
  await P.openCourse('one');
  assert.equal(el('portfolio-retry').hidden, false);
  assert.equal(el('portfolio-list').hidden, false);
  assert.equal(P.detail, null);
  P.api = () => Promise.resolve({ ...course('one'), ended_at: 'today' });
  await P.openCourse('one');
  assert.equal(el('portfolio-retry').hidden, true);
  assert.equal(el('course-profile').hidden, false);
});

test('returning to the class discards pending history results without opening a viewer', async () => {
  const { P, S } = setup(), pending = deferred(), opens = [];
  P.detail = course('one'); P.api = () => pending.promise;
  S.media = { open: (...args) => opens.push(args) };
  const loading = P.openResult({ id: 'pose', summary: { kind: 'keyframe' }, drawings: [] }, {});
  P.close(); pending.resolve({ outputs: { keyframe: { image: 'first' } } }); await loading;
  assert.equal(opens.length, 0);
});

test('a slow first result cannot replace the second one the teacher opened', async () => {
  const { P, S } = setup(), pending = deferred(), opens = [];
  P.detail = course('one');
  P.api = path => path.endsWith('/old') ? pending.promise : Promise.resolve({ outputs: { keyframe: 'second' } });
  S.media = { open: (...args) => opens.push(args) };
  const old = P.openResult({ id: 'old', summary: { kind: 'keyframe' }, drawings: [] }, {});
  await P.openResult({ id: 'new', summary: { kind: 'keyframe' }, drawings: [] }, {});
  pending.resolve({ outputs: { keyframe: 'first' } }); await old;
  assert.equal(opens.length, 1); assert.equal(opens[0][2], 'second');
});

test('titles remain literal text and review does not render conversation transcripts', async () => {
  const { P, el } = setup();
  P.api = () => Promise.resolve({ ...course('one', '<img onerror="alert(1)"> 🌻'), ended_at: 'today',
    drawings: [{ id: 'art', url: '/api/courses/one/drawings/art', thumbnail_url: '/thumb' }],
    activities: [{ skill: 'confirmed-words', drawings: ['art'], summary: { kind: 'text', text: '<script>Hi</script>' } }] });
  await P.openCourse('one');
  assert.equal(el('space-title').textContent, '<img onerror="alert(1)"> 🌻');
  assert.equal(el('course-conversation').children.length, 0);
  assert.equal(el('course-drawings').children.length, 1);
});

test('a named course sends its title together with the explicit entrance', async () => {
  const calls = [];
  const S = loadStudio({ files: ['src/23-transport-http.js'], globals: {
    fetch: async (path, opts) => { calls.push(JSON.parse(opts.body)); return { ok: true, json: async () => ({ session_id: 'one' }) }; }
  } });
  await S.transports.http.createSession({ entrance: 'sketch', language: 'zh', title: '光影与结构 🌻' });
  assert.deepEqual(calls[0], { entrance: 'sketch', language: 'zh', lesson_intent: '', title: '光影与结构 🌻' });
});

test('an ended course offers only Reopen, and viewing it never reopens it', async () => {
  const { P, el } = setup(), actions = [], completions = [];
  P.init({ editCourse: async (course, reopen) => {
    actions.push([course.id, reopen]);
    P.showWorkspace({ ...course, ended_at: null }, 'create'); P.close();
  }, completeCourse(id) { completions.push(id); }, home() {}, newClass() {} });
  let ended = '2026-09-07T03:00:00Z';
  P.api = async () => ({ ...course('one'), ended_at: ended });
  await P.openCourse('one');
  assert.equal(el('space-complete').hidden, true); assert.equal(el('space-reopen').hidden, false);
  assert.equal(el('app').dataset.courseView, 'review');
  assert.deepEqual(actions, [], 'viewing the course cannot reopen it');
  await el('space-reopen').onclick(); assert.deepEqual(actions, [['one', true]]);
  ended = null; await P.openCourse('one');
  assert.equal(el('space-complete').hidden, false); assert.equal(el('space-reopen').hidden, true);
  assert.equal(el('app').dataset.courseView, 'create');
  el('space-complete').onclick(); assert.deepEqual(completions, ['one']);
});

test('reopening prevents duplicate actions and unlocks the page after failure', async () => {
  const { P, el } = setup(), pending = deferred(); let calls = 0;
  const first = P.withAction(() => { calls++; return pending.promise; });
  await P.withAction(() => { calls++; });
  assert.equal(calls, 1); assert.equal(el('portfolio').inert, true);
  pending.reject(new Error('offline')); await first;
  assert.equal(el('portfolio').inert, false); assert.equal(el('portfolio-retry').hidden, false);
  await P.withAction(async () => { calls++; }); assert.equal(calls, 2);
});

test('restoring a course recovers artwork and confirmed words, with its stable ID', async () => {
  const S = loadStudio({ globals: { clearInterval() {} } }); S.i18n.set = () => {};
  const payload = { session_id: 'new-editor', course: { ...course('original'), language: 'zh',
    drawings: [{ id: 'art', url: '/api/courses/original/drawings/art' }],
    activities: [
      { skill: 'art-feedback', drawings: ['art'], summary: { beat: 'opening', text: 'A dog.', question: 'Where?' } },
      { skill: 'confirmed-words', drawings: ['art'], summary: { text: 'To the stars 🌻.' } },
      { skill: 'art-feedback', drawings: ['art'], summary: { beat: 'rung-3', text: 'Here?' } },
      { skill: 'art-feedback', drawings: ['art'], summary: { beat: 'reply', text: 'To the stars.', question: 'Where?' } }
    ] } };
  assert.throws(() => S.session.restore({ ...payload, course: { ...payload.course, ended_at: 'today' } }));
  assert.equal(S.state.session, null);
  S.session.restore(payload);
  assert.equal(S.state.session, 'new-editor'); assert.equal(S.state.courseId, 'original');
  assert.equal(S.session.currentDrawing().url, '/api/courses/original/drawings/art');
  assert.equal(S.state.said.art, 'To the stars 🌻.'); assert.equal(S.state.feedback.art.question, 'Where?');
  assert.equal(S.state.asked.art, 3, 'restoration must not repeat questions already asked');
  const completed = []; S.state.transport = { completeCourse: async id => completed.push(id) };
  await S.session.end({ complete: true });
  assert.deepEqual(completed, ['original']); assert.equal(S.state.courseId, null);
});

test('an unanswered ending stays read-only until the course is reopened', () => {
  const elements = new Map(), el = id => {
    if (!elements.has(id)) elements.set(id, { pause() {}, load() {}, removeAttribute() {}, style: {}, classList: { toggle() {} }, firstChild: {} });
    return elements.get(id);
  };
  const S = loadStudio({ files: ['src/28-book.js'], globals: { document: { getElementById: el } } });
  S.voice = { speak() {} };
  const output = { artifact_id: 'book', pages: [{ drawing_id: 'art', text: '原话' }] };
  S.book.open('Book', output, [], { courseId: 'one', history: true, readOnly: true });
  S.book.go(1); assert.equal(el('ending').hidden, true);
  assert.equal(S.book.answer('A changed ending'), false);
  assert.equal(S.book.pages[1].text, '');
  S.book.open('Book', output, [], { courseId: 'one', history: true, readOnly: false });
  S.book.go(1); assert.equal(el('ending').hidden, false);
  assert.equal(S.book.answer('A confirmed ending'), true);
  assert.equal(S.book.pages[1].text, 'A confirmed ending');
});

test('course cards enter creation only for open courses; completed courses stay in review', async () => {
  const { P, el } = setup(), edits = [];
  P.init({ editCourse: async c => edits.push(c.id) });
  P.api = async path => ({ ...course(path.slice(1)), ended_at: path === '/ended' ? 'today' : null });
  await P.card(course('open')).onclick();
  assert.deepEqual(edits, ['open']);
  await P.card(course('ended')).onclick();
  assert.deepEqual(edits, ['open'], 'viewing an ended course must never start an editor');
  assert.equal(el('app').dataset.courseView, 'review');
  await P.create(); assert.deepEqual(edits, ['open']);
});

test('review preserves selection when a completed course is reopened for creation', async () => {
  const { P, el } = setup(), edits = [];
  P.init({ editCourse: async (c, reopen, drawing) => edits.push([c.id, drawing]) });
  P.api = async path => path.includes('/activities/') ? { outputs: { keyframe: { image: 'data:image/png;base64,YQ==' } } } : ({ ...course('one'), ended_at: 'today', drawings: [{ id: 'a', url: '/a' }, { id: 'b', url: '/b' }],
    activities: [{ id: 'pose', drawings: ['b'], created_at: '2026-09-07', summary: { kind: 'keyframe' } }] });
  await P.openCourse('one');
  await P.reviewSection('stage2');
  assert.equal(el('review-output').children.length, 1);
  await P.openCourse('one'); assert.equal(el('course-original').src, '/b');
  await P.create(true); assert.deepEqual(edits, [['one', 'b']]);
  P.showWorkspace(P.detail, 'create');
  await P.create(); assert.equal(edits.length, 1, 'clicking the active view must not reset the drawing');
});

test('expression and transformation layers include both entrances; books and originals stay separate', async () => {
  const { P, S, el } = setup(), opened = []; let closed = 0;
  S.relight = { active: null, close() {}, open() { this.active = {}; } };
  S.book = { open: (...args) => opened.push(args), closeInline() { closed++; } };
  P.api = async path => path.includes('/activities/mesh') ? { outputs: { scene: {} } }
    : path.includes('/activities/book') ? { outputs: { title: '我们的故事', pages: [] } }
    : path.includes('/activities/') ? { outputs: { keyframe: { image: 'data:image/png;base64,YQ==' } } }
    : { ...course('one'), ended_at: 'today', drawings: [{ id: 'a', url: '/a' }, { id: 'b', url: '/b' }, { id: 'c', url: '/c' }], activities: [
      { id: 'pose', drawings: ['a'], summary: { kind: 'keyframe' } },
      { id: 'mesh', drawings: ['b'], summary: { kind: 'relight' } },
      { id: 'book', drawings: ['a','b'], created_at: '2026-09-07', summary: { kind: 'book' } },
      { id: 'chat', skill: 'art-feedback', drawings: ['a'], summary: { kind: 'text', text: 'An observation', question: 'Who lives there?' } },
      { id: 'words', skill: 'confirmed-words', drawings: ['a'], summary: { kind: 'text', text: 'My story' } },
      { id: 'response', skill: 'art-feedback', drawings: ['a'], summary: { kind: 'text', text: 'A response to your story' } },
      { id: 'more-words', skill: 'confirmed-words', drawings: ['a'], summary: { kind: 'text', text: 'More of my story 🐘.\nAnother line.' } },
      { id: 'other-words', skill: 'confirmed-words', drawings: ['b'], summary: { kind: 'text', text: 'Other picture', status: 'draft' } },
      { id: 'note', skill: 'art-feedback', drawings: ['a'], summary: { kind: 'text', text: 'Later output provenance' } }
    ] };
  await P.openCourse('one'); await P.reviewSection('stage1');
  assert.equal(el('review-output').children.length, 1); assert.equal(el('review-output').children[0].value, 'note');
  assert.equal(el('course-original').src, '/a'); assert.equal(el('review-output-content').children.length, 1);
  // The whole conversation, both voices in order (operator: the child's words alone read as a list).
  const thread = el('review-output-content').children[0].children[0];
  // Each turn names its speaker for a screen reader, and the companion's question has its own line.
  assert.deepEqual(thread.children.map(turn => [turn.className, ...turn.children.map(part => part.textContent)]), [
    ['review-turn companion', '画画伙伴', 'An observation', 'Who lives there?'], ['review-turn child', '孩子', 'My story'],
    ['review-turn companion', '画画伙伴', 'A response to your story'],
    ['review-turn child', '孩子', 'More of my story 🐘.\nAnother line.'],
    ['review-turn companion', '画画伙伴', 'Later output provenance']]);
  assert.equal(thread.children[0].children[2].className, 'review-question');
  const spoken = []; let stopped = 0;
  S.voice = { selected() { return 'gentle-female'; }, place() {}, unlock() {}, playAll: (...args) => spoken.push(args),
    stop() { stopped++; }, restore() {} };
  el('review-output-content').children[0].children[1].onclick();
  assert.equal(spoken[0][0][0], 'My story');
  assert.deepEqual(Array.from(spoken[0][0]), ['My story', 'More of my story 🐘.\nAnother line.']);
  assert.equal(spoken[0][1].voice, 'soft-child');

  await P.reviewSection('stage2');
  assert.equal(stopped, 1, 'leaving the chat stops its reading');
  assert.equal(el('review-output').children.length, 2);
  assert.deepEqual(el('review-output').children.map(o => o.value), ['a', 'b'], 'one button per drawing');
  assert.equal(el('review-output').children[0].children[0].src, '/a');
  assert.equal(el('review-output').children[0]['aria-pressed'], 'true');
  await el('review-output').children[1].onclick();
  assert.equal(el('review-output').children[0]['aria-pressed'], 'false');
  assert.equal(el('review-output').children[1]['aria-pressed'], 'true');
  assert.deepEqual(el('review-results').children.map(slot => slot.value), ['mesh']);
  assert.equal(el('course-original').src, '/b');
  await P.reviewSection('books'); assert.equal(el('review-comparison').hidden, true);
  assert.equal(el('review-book-panel').hidden, false);
  assert.equal(opened.length, 1); assert.equal(opened[0][0], '我们的故事');
  assert.equal(opened[0][3].inlineHost, el('review-book-reader'));
  assert.equal(el('review-book-title').textContent, '我们的故事');
  P.reviewSection('originals'); assert.equal(el('review-book-panel').hidden, true);
  assert.ok(closed > 0, 'leaving the book stops the inline reader');
  assert.equal(el('course-drawings').children.length, 3, 'unprocessed originals must also appear');
});

test('late comparison responses cannot repopulate another section and failures allow retry', async () => {
  const { P, el } = setup(), pending = deferred();
  P.detail = { ...course('one'), drawings: [{ id:'a', url:'/a' }], activities: [{ id:'pose', drawings:['a'], summary:{kind:'keyframe'} }] };
  P.api = () => pending.promise;
  const old = P.reviewSection('stage2'); P.reviewSection('originals');
  pending.resolve({outputs:{keyframe:{image:'data:image/png;base64,YQ=='}}}); await old;
  assert.equal(el('review-output-content').children.length, 0);
  P.api = async () => { throw Error('offline'); };
  await P.reviewSection('stage2'); assert.equal(el('review-output-retry').hidden, false);
  P.api = async () => ({outputs:{keyframe:{image:'data:image/png;base64,YQ=='}}});
  await P.loadComparison('pose'); assert.equal(el('review-output-retry').hidden, true);
  assert.equal(el('review-output-content').children.length, 1);
});

test('leaving a comparison stops its video and releases its 3D viewer', () => {
  const { P, S } = setup(), calls = [];
  P.reviewVideo = { pause() { calls.push('pause'); }, removeAttribute(name) { calls.push(name); }, load() { calls.push('load'); } };
  P.reviewScene = {};
  S.relight = { active: P.reviewScene, close() { calls.push('dispose'); this.active = null; } };
  P.disposeComparison();
  assert.deepEqual(calls, ['pause', 'src', 'load', 'dispose']);
  assert.equal(P.reviewVideo, null); assert.equal(P.reviewScene, null);
  P.disposeComparison(); assert.equal(calls.length, 4, 'cleanup must not dispose resources twice');
});

test('review books are read-only even while the course is open', async () => {
  const { P, S } = setup(); let context;
  P.detail = course('open'); P.api = async () => ({ outputs: { pages: [] } });
  S.book = { open: (...args) => { context = args[3]; } };
  await P.openResult({ id: 'book', drawings: [], summary: { kind: 'book' } }, {});
  assert.equal(context.readOnly, true);
});

test('named animated books remain distinguishable from the original book', async () => {
  const { P, S, el } = setup(); let title;
  const name = '圣诞城堡 · 动画版';
  P.api = async path => path.includes('/activities/') ? { outputs: { title: name, pages: [] } }
    : { ...course('one'), ended_at: 'today', activities: [{ id: 'animated', drawings: [], created_at: '2026-09-07T01:00:00Z', summary: { kind: 'book', title: name } }] };
  S.book = { open: value => { title = value; }, closeInline() {} };
  await P.openCourse('one');
  await P.reviewSection('books');
  assert.equal(title, name);
  assert.equal(el('review-book-title').textContent, name);
});

test('review shows one confirmed book when older course data contains several', async () => {
  const { P, S } = setup(); let selected;
  const book = (id, ending = '') => ({ id, skill: 'drawings-to-storybook', drawings: [],
    created_at: '2026-09-07T01:00:00Z', ending, summary: { kind: 'book' } });
  S.book = { open: (_, output) => { selected = output.artifact_id; }, closeInline() {} };
  P.api = async path => path.includes('/activities/') ? { outputs: { pages: [] } }
    : ({ ...course('one'), ended_at: 'today', activities: [
    book('kept', '孩子的结尾'), book('unrelated'), book('duplicate')
  ] });
  await P.openCourse('one'); await P.reviewSection('books');
  assert.equal(selected, 'kept');
  P.api = async path => path.includes('/activities/') ? { outputs: { pages: [] } }
    : ({ ...course('one'), ended_at: 'today', activities: [book('older'), book('newer')] });
  await P.openCourse('one'); await P.reviewSection('books');
  assert.equal(selected, 'newer');
});

test('inline storybook ignores a late load and can retry a failed load', async () => {
  const { P, S, el } = setup(), pending = deferred(), opened = [];
  const saved = { ...course('one'), ended_at: 'today', activities: [
    { id: 'book', drawings: [], summary: { kind: 'book' } }
  ] };
  S.book = { open: (...args) => opened.push(args), closeInline() {} };
  P.init({ home() {}, newClass() {}, completeCourse() {}, editCourse() {} });
  P.reviewSections = { one: 'originals' };
  P.api = path => path.includes('/activities/') ? pending.promise : Promise.resolve(saved);
  await P.openCourse('one');
  const loading = P.reviewSection('books');
  P.reviewSection('originals');
  pending.resolve({ outputs: { pages: [] } }); await loading;
  assert.equal(opened.length, 0);

  P.api = async path => { if (path.includes('/activities/')) throw Error('offline'); return saved; };
  await P.reviewSection('books');
  assert.equal(el('review-book-retry').hidden, false);
  P.api = async () => ({ outputs: { pages: [] } });
  await el('review-book-retry').onclick();
  assert.equal(opened.length, 1);
  assert.equal(el('review-book-retry').hidden, true);
});

test('motion review says what this result shows, never the child’s words, and clears it on navigation', async () => {
  // Operator: the words under a clip repeated the chat tab word for word; they belong there.
  const { P, el } = setup();
  P.detail = { ...course('one'), drawings: [{ id: 'a', url: '/a' }, { id: 'b', url: '/b' }], activities: [
    { id: 'pose', drawings: ['a'], summary: { kind: 'keyframe', scene_description: '大象抬起鼻子喷水。' } },
    { id: 'empty', drawings: ['b'], summary: { kind: 'keyframe' } },
    { skill: 'confirmed-words', drawings: ['a'], summary: { kind: 'text', text: '大象🐘在喷水。' } }
  ] };
  P.api = async () => ({ outputs: { keyframe: { image: 'data:image/png;base64,YQ==' } } });
  await P.loadComparison('pose');
  assert.equal(el('review-child-description').hidden, false);
  assert.equal(el('review-child-description-text').textContent, '大象抬起鼻子喷水。');
  await P.loadComparison('empty');
  assert.equal(el('review-child-description').hidden, true, 'nothing saved to say, no box');
  P.reviewSection('books');
  assert.equal(el('review-child-description').hidden, true);
  assert.equal(el('review-child-description-text').textContent, '');
});

test('teacher reviews restore per artwork without becoming child dialogue', async () => {
  const { S } = setup();
  S.i18n.set = () => {};
  S.session.restore({ session_id: 'editor', course: {
    id:'course',language:'zh',entrance:'colour',lesson_intent:'',title:'Review',
    drawings:[{id:'a',url:'/a'},{id:'b',url:'/b'}], activities:[
      {skill:'teacher-review',drawings:['a'],summary:{text:'完整评价',beat:'teacher-review'}},
      {skill:'teacher-review',drawings:['a'],summary:{status:'stopped',message:'failed'}},
      {skill:'art-feedback',drawings:['a'],summary:{text:'对话观察',question:'去哪里？',beat:'opening'}}
    ]
  }});
  assert.equal(S.state.teacherReviews.a.text,'完整评价');
  assert.equal(S.state.teacherReviews.b,undefined);
  assert.equal(S.state.feedback.a.text,'对话观察');
  S.state.transport={forgetSession:async()=>{}};
  S.state.drawings.forEach(d => { d.url = ''; });
  await S.session.end();
  assert.equal(Object.keys(S.state.teacherReviews).length,0);
});

test('teacher review has a separate history view with the full saved text', async () => {
  const { S, P, el } = setup();
  S.voice={stop(){},restore(){}};
  P.detail={...course('one'),drawings:[{id:'a',url:'/a'}],activities:[
    {id:'teacher',skill:'teacher-review',drawings:['a'],summary:{kind:'text',text:'完整老师评价'}},
    {id:'chat',skill:'art-feedback',drawings:['a'],summary:{kind:'text',text:'对话观察'}}
  ]};
  await P.reviewSection('teacher');
  assert.equal(el('review-output').children.length,1);
  assert.equal(el('review-output').children[0].value,'teacher');
  const review = el('review-output-content').children[0];
  assert.equal(review.children.length,1,'the card heading already says 老师评价; the text does not say it again');
  assert.equal(review.children[0].textContent,'完整老师评价');
  await P.reviewSection('stage1');
  assert.equal(el('review-output').children[0].value,'chat');
});

test('a sketch class shows no storybook tab, and a colour class opened next shows it again', () => {
  // Operator: remove the storybook from the black-and-white sketch class.
  const { P, el } = setup(), refreshed = [];
  el('mode').refresh = () => refreshed.push(el('app').dataset.entrance);
  P.showWorkspace({ ...course('sketch-class'), entrance: 'sketch', ended_at: null }, 'create');
  assert.equal(el('app').dataset.entrance, 'sketch');
  P.showWorkspace({ ...course('colour-class'), ended_at: null }, 'create');
  assert.equal(el('app').dataset.entrance, 'colour');
  assert.deepEqual(refreshed, ['sketch', 'colour'], 'the tab row is measured again when the tabs change');
  P.hideWorkspace(); assert.equal(el('app').dataset.entrance, '');
  const css = readFileSync(new URL('../../studio/page/src/02-glass.css', import.meta.url), 'utf8');
  assert.match(css, /#app\[data-entrance=sketch\] #mode \[data-mode=book\]\{display:none\}/);
});

// Operator, looking at the showcase classes once ended: the review pages were "not good".
test('a finished class shows its storybook tab only when it has a book, and never in a sketch class', async () => {
  const { P, el } = setup(), drawings = [{ id: 'a', url: '/a' }, { id: 'b', url: '/b' }];
  const book = { id: 'book', drawings: ['a', 'b'], summary: { kind: 'book' } };
  P.api = async () => ({ ...course('one'), ended_at: 'today', drawings, activities: [book] });
  await P.openCourse('one'); assert.equal(el('review-books').hidden, false);
  P.api = async () => ({ ...course('two'), ended_at: 'today', drawings, activities: [] });
  await P.openCourse('two'); assert.equal(el('review-books').hidden, true, 'no book, no empty storybook page');
  P.api = async () => ({ ...course('three'), entrance: 'sketch', ended_at: 'today', drawings, activities: [book] });
  await P.openCourse('three'); assert.equal(el('review-books').hidden, true, 'a sketch class has no storybook');
  P.reviewSections = { three: 'books' };
  P.reviewSection('books');
  assert.equal(el('review-original-panel').hidden, false, 'a remembered storybook tab opens the art collection');
});

test('bring to life in review: one button per drawing, its clip and figure as labelled slots, and what the clip shows',
  async () => {
    const { P, S, el } = setup();
    // The stand-in elements play a clip well enough to be stopped when the teacher moves on.
    Object.assign(Object.getPrototypeOf(el('probe')), { pause() {}, load() {}, removeAttribute() {} });
    S.figureView = { open() {}, close() {} }; S.relight = { active: null, close() {} };
    P.api = async path => ({ outputs: path.includes('fig-') ? { figure: {} } : { video_url: 'data:video/mp4;base64,AA==' } });
    P.detail = { ...course('one'), ended_at: 'today', drawings: [{ id: 'a', url: '/a' }, { id: 'b', url: '/b' }], activities: [
      { id: 'clip-a', drawings: ['a'], summary: { kind: 'video', scene_description: '城堡的彩灯一闪一闪' } },
      { id: 'fig-a', drawings: ['a'], summary: { kind: 'figure' } },
      { id: 'words-a', skill: 'confirmed-words', drawings: ['a'], summary: { kind: 'text', text: '孩子说的话' } },
      { id: 'fig-b', drawings: ['b'], summary: { kind: 'figure' } },
      { id: 'clip-b-old', drawings: ['b'], summary: { kind: 'video', scene_description: '旧的' } },
      { id: 'clip-b', drawings: ['b'], summary: { kind: 'video', scene_description: '小狐狸划船' } }] };
    P.selected.one = 'a';
    await P.reviewSection('stage2');
    assert.deepEqual(el('review-output').children.map(button => button.value), ['a', 'b']);
    const slots = () => el('review-results').children.map(slot => [slot.value, slot.textContent, slot['aria-pressed']]);
    assert.deepEqual(slots(), [['clip-a', '动作视频', 'true'], ['fig-a', '立体小雕塑', 'false']]);
    assert.equal(el('review-child-description-text').textContent, '城堡的彩灯一闪一闪', 'what moves, not the child\'s words');
    assert.equal(el('review-output-content').children[0].src, 'data:video/mp4;base64,AA==', 'the clip is drawn');
    P.api = async () => { throw Error('offline'); };
    await el('review-results').children[0].onclick();
    assert.equal(el('review-output-retry').hidden, false);
    // A saved clip now comes as a file of its own, which plays as it arrives (studio/server/media_links.py).
    const own = '/api/courses/one/activities/clip-a/media/video_url?v=ab12';
    P.api = async path => ({ outputs: path.includes('fig-') ? { figure: {} } : { video_url: own } });
    P.init({});
    await el('review-output-retry').onclick();
    assert.equal(el('review-output-content').children[0].src, own, 'Retry loads the clip again, from its own address');
    await el('review-results').children[1].onclick();
    assert.deepEqual(slots(), [['clip-a', '动作视频', 'false'], ['fig-a', '立体小雕塑', 'true']]);
    assert.equal(el('review-child-description-title').textContent, '受这幅画启发的立体小雕塑');
    await el('review-output').children[1].onclick();
    assert.deepEqual(slots(), [['clip-b', '动作视频', 'true'], ['fig-b', '立体小雕塑', 'false']], 'the latest clip only');
    assert.equal(el('review-child-description-text').textContent, '小狐狸划船');
    await P.reviewSection('teacher');
    assert.equal(el('review-results').hidden, true, 'the slots belong to this tab alone');
  });

test('the art collection shows small pictures and links the full drawing', async () => {
  const { P, el } = setup();
  P.api = async () => ({ ...course('one'), ended_at: 'today', activities: [],
    drawings: [{ id: 'a', url: '/api/courses/one/drawings/a', thumbnail_url: '/api/courses/one/drawings/a?thumbnail=1' }] });
  await P.openCourse('one');
  const card = el('course-drawings').children[0];
  assert.equal(card.children[0].src, '/api/courses/one/drawings/a?thumbnail=1');
  assert.equal(card.children[2].href, '/api/courses/one/drawings/a');
});
