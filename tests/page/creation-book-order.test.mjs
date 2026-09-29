import test from 'node:test';
import assert from 'node:assert/strict';
import { loadStudio } from './load.mjs';

// Operator: after "move up" the story's list changed and the pictures stayed where they were.
test('the book\'s pictures stand in the story\'s order, each with its page and its own number', () => {
  const root = {hidden: true, innerHTML: '', addEventListener: () => {}, querySelector: () => ({disabled: false})};
  const S = loadStudio({files: ['src/29a-creation.js', 'src/29h-lanes.js'],
    globals: {queueMicrotask: () => {}, document: {getElementById: id => id === 'creation-planner' ? root : {dataset: {}}}}});
  Object.assign(S.state, {session: 'one', mode: 'book', current: 'a', settings: {entrance: 'colour'},
    drawings: [{id: 'a', url: '/a'}, {id: 'b', url: '/b'}, {id: 'c', url: '/c'}], chosen: []});
  S.creation.init({active: () => true, run: () => {}, stop: () => {}, open: () => {}});
  S.creation.render();   // the first look at the book picks every drawing, as a teacher sees it
  S.state.chosen = ['b', 'a']; S.creation.render();
  const picks = [...root.innerHTML.matchAll(/data-pick="([^"]+)"[^>]*>.*?<span>([^<]*)<\/span>/g)].map(m => [m[1], m[2]]);
  assert.deepEqual(picks, [
    ['b', '故事第 1 页 · 今天的第 2 幅画'],
    ['a', '故事第 2 页 · 今天的第 1 幅画'],
    ['c', '今天的第 3 幅画'],
  ]);
});

test('while a book is written the teacher sees which page, and that page\'s picture', () => {
  // Operator: the picture never changed and the teacher could not tell where the book was.
  const els = {}, el = id => els[id] ||= {style: {}, dataset: {}, textContent: ''}, handlers = {};
  const root = {hidden: true, innerHTML: '', addEventListener: (name, fn) => handlers[name] = fn, querySelector: () => ({disabled: false})};
  const S = loadStudio({files: ['src/29a-creation.js', 'src/29h-lanes.js'],
    globals: {queueMicrotask: () => {}, document: {getElementById: id => id === 'creation-planner' ? root : el(id)}}});
  Object.assign(S.state, {session: 'one', mode: 'book', current: 'a', settings: {entrance: 'colour'},
    drawings: [{id: 'a', url: '/a'}, {id: 'b', url: '/b'}, {id: 'c', url: '/c'}], chosen: []});
  S.session = {currentDrawing: () => S.state.drawings[0], isCurrent: () => true};
  const sent = [];
  S.creation.init({active: () => true, run: (skill, ids) => sent.push({skill, ids}), stop: () => {}, open: () => {}});
  S.creation.render(); S.state.chosen = ['c', 'a']; S.creation.render();
  handlers.click({target: {closest: () => ({dataset: {create: 'plot'}, disabled: false})}});
  assert.equal(sent.at(-1).skill, 'story-outline');
  S.creation.preview('A river under snow.', 'scene-description-c');
  assert.equal(el('creation-progress').textContent, '正在写第 1 页（共 2 页）· 今天的第 3 幅画');
  assert.equal(el('picture').style.backgroundImage, 'url("/c")', 'the page being written is the picture shown');
  S.creation.preview('Once upon a time', 'story-outline-c');
  assert.equal(el('creation-progress').textContent, '正在把 2 页连成故事');
  S.creation.preview('A garden.', 'scene-description-a'); S.creation.preview('Once upon a time', 'story-outline-c');
  assert.equal(el('picture').style.backgroundImage, 'url("/c")', 'joining the story shows page 1, not the last page written');
  S.creation.completed('story-outline', {outline: [{drawing_id: 'c', text: 'x'}, {drawing_id: 'a', text: 'y'}], scenes: []}, S.state.drawings[0]);
  assert.equal(el('picture').style.backgroundImage, 'url("/a")', 'the teacher\'s own picture comes back');
});

function bookPlanner(extra = {}) {
  const handlers = {}, root = {hidden: true, innerHTML: '', addEventListener: (n, fn) => handlers[n] = fn, querySelector: () => ({disabled: false})};
  const S = loadStudio({files: ['src/29a-creation.js', 'src/29h-lanes.js'],
    globals: {queueMicrotask: () => {}, setImmediate, document: {getElementById: id => id === 'creation-planner' ? root : {style: {}, dataset: {}}}}});
  Object.assign(S.state, {session: 'one', courseId: 'course', mode: 'book', current: 'a', settings: {entrance: 'colour'},
    drawings: [{id: 'a', url: '/a'}, {id: 'b', url: '/b'}], chosen: [], said: {}}, extra);
  const sent = [], opened = [];
  S.creation.init({active: () => true, run: (skill, ids, opts) => sent.push({skill, ids, opts}), stop: () => {}, open: r => opened.push(r)});
  const press = create => handlers.click({target: {closest: () => ({dataset: {create}, disabled: false})}});
  return {S, root, sent, opened, press};
}

test('a new story is written fresh from the pictures and the children\'s words, never from the last one', () => {
  // Before the fix: handed the last story to improve, Qwen3.6 gave it back word for word, four presses out of four;
  // and earlier, after a reorder the writer followed the old story's order and the outline was refused.
  const {S, sent, press} = bookPlanner();
  S.creation.render();
  S.state.storyDraft = {ids: ['a', 'b'], pages: [{drawing_id: 'a', text: 'one'}, {drawing_id: 'b', text: 'two'}], scenes: []};
  S.state.chosen = ['a', 'b']; S.creation.render();
  press('plot');
  assert.equal(sent.at(-1).skill, 'story-outline');
  assert.equal(sent.at(-1).opts.previous, undefined, 'same order: written fresh');
  S.state.chosen = ['b', 'a']; S.creation.render(); press('plot');
  assert.equal(sent.at(-1).opts.previous, undefined, 'new order: written fresh');
});

test('a story older than what the child has since said is written again, not continued, and the edit step says so', () => {
  // Before the fix: the child named the princess and said the cannonballs were snowballs; "continue" kept the old story.
  const {S, root, press} = bookPlanner();
  S.creation.render();
  S.state.chosen = ['a', 'b']; S.creation.render(); press('plot');
  S.creation.completed('story-outline', {outline: [{drawing_id: 'a', text: 'one'}, {drawing_id: 'b', text: 'two'}], scenes: []});
  press('back');
  assert.match(root.innerHTML, /data-create="continue-story"/, 'nothing new was said: the story is continued');
  press('continue-story');
  S.state.said.b = 'They are snowballs!'; S.creation.render();
  assert.match(root.innerHTML, /孩子又说了新的话/, 'the teacher editing the old story is told');
  press('back');
  assert.match(root.innerHTML, /data-create="plot"/);
  assert.doesNotMatch(root.innerHTML, /continue-story/, 'the story is written again with the new words');
});

test('a reopened class opens on its finished book, with the words the teacher confirmed and the child\'s ending', async () => {
  // Before the fix: reopening offered the model's first draft again and the book came back without its ending.
  const {S, root, opened, press} = bookPlanner({session: null, courseId: null, mode: 'feedback'});
  const asked = [];
  S.portfolio = {api: path => { asked.push(path); return Promise.resolve({
    outputs: {pages: [{drawing_id: 'a', text: 'The teacher\'s one.'}, {drawing_id: 'b', text: 'The teacher\'s two.'}]}, ending: 'They shared the cheese.'}); }};
  S.bus = S.bus || {emit: () => {}};
  S.session.restore({session_id: 'one', course: {id: 'course', language: 'zh', entrance: 'colour', lesson_intent: '', title: 'Test',
    drawings: [{id: 'a', url: '/a'}, {id: 'b', url: '/b'}], drafts: {}, activities: [
      {id: 'o1', skill: 'story-outline', drawings: ['a', 'b'], summary: {outline: [{drawing_id: 'a', text: 'model one'}, {drawing_id: 'b', text: 'model two'}], scenes: []}},
      {id: 'bk', skill: 'drawings-to-storybook', drawings: ['a', 'b'], summary: {kind: 'book'}, ending: 'They shared the cheese.'}]}});
  S.state.mode = 'book'; S.creation.render();
  assert.match(root.innerHTML, /故事书做好了/, 'the class opens on the book it already has');
  await new Promise(resolve => setImmediate(resolve));
  assert.deepEqual(asked, ['/course/activities/bk']);
  assert.deepEqual(S.state.storyDraft.pages.map(p => p.text), ['The teacher\'s one.', 'The teacher\'s two.'], 'editing starts from the confirmed words');
  press('open');
  assert.equal(opened.at(-1).out.ending, 'They shared the cheese.');
  assert.equal(opened.at(-1).out.artifact_id, 'bk', 'a changed ending is saved on the same book');
});

test('a story written after the book is newer, and a reopened class keeps it', () => {
  const {S, root} = bookPlanner({session: null, courseId: null, mode: 'feedback'});
  S.portfolio = {api: () => { throw new Error('the older book is not fetched'); }};
  S.bus = S.bus || {emit: () => {}};
  S.session.restore({session_id: 'one', course: {id: 'course', language: 'zh', entrance: 'colour', lesson_intent: '', title: 'Test',
    drawings: [{id: 'a', url: '/a'}, {id: 'b', url: '/b'}], drafts: {}, activities: [
      {id: 'bk', skill: 'drawings-to-storybook', drawings: ['a', 'b'], summary: {kind: 'book'}, ending: ''},
      {id: 'o2', skill: 'story-outline', drawings: ['a', 'b'], summary: {outline: [{drawing_id: 'a', text: 'new one'}, {drawing_id: 'b', text: 'new two'}], scenes: []}}]}});
  S.state.mode = 'book'; S.creation.render();
  assert.match(root.innerHTML, /data-create="continue-story"/);
  assert.deepEqual(S.state.storyDraft.pages.map(p => p.text), ['new one', 'new two']);
});

test('the review names a drawing by its page, never by its code', () => {
  // Operator: the teacher was shown "c6f25f4343e9页" and "场景d7fe5251374b".
  const handlers = {}, root = {hidden: true, innerHTML: '', addEventListener: (n, fn) => handlers[n] = fn, querySelector: () => ({disabled: false})};
  const S = loadStudio({files: ['src/29a-creation.js', 'src/29h-lanes.js'],
    globals: {queueMicrotask: () => {}, document: {getElementById: id => id === 'creation-planner' ? root : {style: {}, dataset: {}}}}});
  Object.assign(S.state, {session: 'one', mode: 'book', current: 'aaaaaaaaaaaa', settings: {entrance: 'colour'},
    drawings: [{id: 'aaaaaaaaaaaa', url: '/a'}, {id: 'bbbbbbbbbbbb', url: '/b'}], chosen: []});
  const sent = [];
  S.creation.init({active: () => true, run: (skill, ids, opts) => sent.push({skill, ids}), stop: () => {}, open: () => {}});
  S.creation.render(); S.state.chosen = ['bbbbbbbbbbbb', 'aaaaaaaaaaaa']; S.creation.render();
  handlers.click({target: {closest: () => ({dataset: {create: 'plot'}, disabled: false})}});
  S.creation.stopped('refused', {skill: 'story-outline', outline: [{drawing_id: 'bbbbbbbbbbbb', text: 'x'}, {drawing_id: 'aaaaaaaaaaaa', text: 'y'}], scenes: []},
    [{evidence: 'aaaaaaaaaaaa页 says steam', suggestion: '场景bbbbbbbbbbbb keeps the bird flying'}]);
  S.creation.render();
  assert.match(root.innerHTML, /第 2 页 says steam/);
  assert.match(root.innerHTML, /第 1 页 keeps the bird flying/);
  assert.doesNotMatch(root.innerHTML, /aaaaaaaaaaaa|bbbbbbbbbbbb页/);
});

test('each story page names and shows its drawing', () => {
  // Operator: with two near-identical drawings the order could not be told from the text.
  const handlers = {}, root = {hidden: true, innerHTML: '', addEventListener: (n, fn) => handlers[n] = fn, querySelector: () => ({disabled: false})};
  const S = loadStudio({files: ['src/29a-creation.js', 'src/29h-lanes.js'],
    globals: {queueMicrotask: () => {}, document: {getElementById: id => id === 'creation-planner' ? root : {style: {}, dataset: {}}}}});
  Object.assign(S.state, {session: 'one', mode: 'book', current: 'a', settings: {entrance: 'colour'},
    drawings: [{id: 'a', url: '/a'}, {id: 'b', url: '/b'}], chosen: []});
  S.creation.init({active: () => true, run: () => {}, stop: () => {}, open: () => {}});
  S.creation.render(); S.state.chosen = ['b', 'a'];
  S.state.storyDraft = {ids: ['b', 'a'], pages: [{drawing_id: 'b', text: 'one'}, {drawing_id: 'a', text: 'two'}], scenes: []};
  S.creation.render();
  handlers.click({target: {closest: () => ({dataset: {create: 'continue-story'}, disabled: false})}});
  assert.match(root.innerHTML, /<img src="\/b" alt="">第 1 幕 · 今天的第 2 幅画/);
  assert.match(root.innerHTML, /<img src="\/a" alt="">第 2 幕 · 今天的第 1 幅画/);
});
