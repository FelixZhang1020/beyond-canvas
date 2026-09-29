import test from 'node:test';
import assert from 'node:assert/strict';
import { loadStudio } from './load.mjs';

// The colour planner's second output: a 3D figure inspired by the painting (painting-to-figure).
// It was the third until the still picture was retired.
function setup() {
  const handlers = {}, controls = {};
  const root = {hidden: true, innerHTML: '', addEventListener: (name, fn) => handlers[name] = fn,
    querySelector: selector => controls[selector] ||= {disabled: false}};
  const app = {dataset: {}}, calls = [], opened = [], shown = [];
  const S = loadStudio({files: ['src/29a-creation.js', 'src/29h-lanes.js'], globals: {queueMicrotask: () => {}, document: {getElementById: id => id === 'creation-planner' ? root : app}}});
  Object.assign(S.state, {session: 'one', mode: 'move', current: 'a', settings: {entrance: 'colour'}, drawings: [{id: 'a', url: '/a'}]});
  S.media = {open: (...args) => shown.push(args)};
  S.creation.init({active: () => true, run: (skill, ids, opts) => { calls.push({skill, ids, opts}); if (S.creation.planning(skill)) S.state.busy = true; else S.state.making = skill; S.creation.render(); },
    stop: () => {}, open: r => opened.push(r)});
  const click = dataset => handlers.click({target: {closest: () => ({dataset, disabled: false})}});
  const finish = out => { const c = calls.at(-1); S.creation.completed(c.skill, out, S.state.drawings[0]); S.state.busy = false; S.state.making = null; S.creation.render(); };
  return {S, root, calls, opened, shown, click, finish, handlers};
}

test('the figure outcome appears only when the studio says it offers the figure', () => {
  const h = setup(); h.S.creation.render();
  assert.doesNotMatch(h.root.innerHTML, /data-create="edit-figure"/);
  h.S.creation.configure(['scene-description', 'story-outline', 'painting-to-figure']);
  assert.match(h.root.innerHTML, /data-create="edit-figure"/);
  assert.match(h.root.innerHTML, /立体小雕塑/);
});

test('a figure needs no description and is sent as the planner\'s figure output', () => {
  const h = setup(); h.S.creation.configure(['scene-description', 'story-outline', 'painting-to-figure']);
  h.click({create: 'edit-figure'});
  assert.doesNotMatch(h.root.innerHTML, /creation-motion/);
  assert.doesNotMatch(h.root.innerHTML, /Confirm the scene and movement/, 'a figure has no movement to confirm');
  assert.match(h.root.innerHTML, /用这幅画做一个立体小雕塑/);
  assert.match(h.root.innerHTML, /data-create="figure"/);
  h.click({create: 'figure'});
  assert.deepEqual({skill: h.calls[0].skill, kind: h.calls[0].opts.media_kind}, {skill: 'painting-to-animation', kind: 'figure'});
});

test('a finished figure opens in the figure view, not the video player', () => {
  const h = setup(); h.S.creation.configure(['scene-description', 'story-outline', 'painting-to-figure']);
  h.click({create: 'edit-figure'}); h.click({create: 'figure'});
  const figure = {version: 1, parts: []};
  h.finish({figure});
  h.click({create: 'open-figure'});
  assert.equal(h.opened.length, 0);
  assert.equal(h.shown.length, 1);
  assert.equal(h.shown[0][1], 'figure'); assert.equal(h.shown[0][2], figure);
});

test('the results area gives video and figure separate places, without the retired still picture', () => {
  // An older studio could still report the picture model; the choice ignores it.
  const h = setup(); h.S.state.capabilities = {image_edit: true, image_models: [{id: 'flux', status: 'ready'}]};
  h.S.creation.configure(['scene-description', 'story-outline', 'painting-to-figure']);
  assert.match(h.root.innerHTML, /<h2>视频<\/h2>/);
  assert.match(h.root.innerHTML, /<h2>立体小雕塑<\/h2>/);
  assert.doesNotMatch(h.root.innerHTML, /FLUX|creation-output/);
  h.click({create: 'edit-figure'});
  assert.match(h.root.innerHTML, /data-create="figure"/, 'the figure editor opens below both outcomes');
  assert.match(h.root.innerHTML, /<h2>视频<\/h2>/, 'the video place remains visible');
});

test('a drawing keeps both outcomes visible after video then figure', () => {
  // Operator: a teacher who made a clip and then a figure could only reach the figure.
  const h = setup(); h.S.creation.configure(['scene-description', 'story-outline', 'painting-to-figure']);
  h.S.state.motionDrafts = {a: 'The dog wags its tail.'}; h.S.creation.render();
  h.click({create: 'edit-video'});
  h.click({create: 'confirm'}); h.finish({video_url: 'data:video/mp4;base64,AAAA'});
  assert.match(h.root.innerHTML, /data-create="open-video"/);
  assert.match(h.root.innerHTML, /data-create="edit-figure"/, 'the figure is offered next');
  h.click({create: 'edit-figure'});
  assert.match(h.root.innerHTML, /data-create="open-video"/, 'the clip stays visible while editing the figure');
  h.click({create: 'figure'}); h.finish({figure: {version: 1, parts: []}});
  assert.match(h.root.innerHTML, /data-create="open-video"/, 'the clip is still there');
  assert.match(h.root.innerHTML, /data-create="open-figure"/);
  assert.match(h.root.innerHTML, /data-create="edit-video"/, 'the clip can be remade without hiding the figure');
  assert.match(h.root.innerHTML, /data-create="edit-figure"/, 'the figure can be remade without hiding the clip');
  h.click({create: 'open-video'});
  assert.equal(h.opened.length, 1, 'the clip opens in the video player');
  h.click({create: 'open-figure'});
  assert.equal(h.shown.at(-1)[1], 'figure');
});

test('making the video after a figure keeps the figure available throughout', () => {
  const h = setup(); h.S.creation.configure(['scene-description', 'story-outline', 'painting-to-figure']);
  h.click({create: 'edit-figure'}); h.click({create: 'figure'});
  h.finish({figure: {version: 1, parts: []}});
  assert.match(h.root.innerHTML, /data-create="open-figure"/);
  h.S.state.motionDrafts.a = 'The bird flies.';
  h.click({create: 'edit-video'});
  assert.match(h.root.innerHTML, /data-create="open-figure"/, 'the figure remains visible while editing video');
  h.click({create: 'confirm'}); h.finish({video_url: 'data:video/mp4;base64,AAAA'});
  assert.match(h.root.innerHTML, /data-create="open-video"/);
  assert.match(h.root.innerHTML, /data-create="open-figure"/);
});

test('a finished video can be opened while the figure is being made', () => {
  const h = setup(); h.S.creation.configure(['scene-description', 'story-outline', 'painting-to-figure']);
  h.S.state.motionDrafts.a = 'The bird flies.';
  h.click({create: 'edit-video'}); h.click({create: 'confirm'});
  h.finish({video_url: 'data:video/mp4;base64,AAAA'});
  h.click({create: 'edit-figure'}); h.click({create: 'figure'});
  assert.match(h.root.innerHTML, /data-create="open-video"/);
  assert.match(h.root.innerHTML, /<h2>立体小雕塑<\/h2>[\s\S]*?制作中/);
  h.click({create: 'open-video'});
  assert.equal(h.opened.length, 1);
});

test('each drawing keeps its own video or figure editor when switching pictures', () => {
  const h = setup(); h.S.creation.configure(['scene-description', 'story-outline', 'painting-to-figure']);
  h.S.state.drawings.push({id: 'b', url: '/b'});
  h.click({create: 'edit-video'});
  h.S.state.motionDrafts.a = 'Bird A moves.';
  h.S.state.current = 'b'; h.S.creation.render();
  h.click({create: 'edit-figure'});
  assert.doesNotMatch(h.root.innerHTML, /id="creation-motion"/);
  h.S.state.current = 'a'; h.S.creation.render();
  assert.match(h.root.innerHTML, /id="creation-motion"/);
  assert.match(h.root.innerHTML, /Bird A moves\./);
  h.S.state.current = 'b'; h.S.creation.render();
  assert.doesNotMatch(h.root.innerHTML, /id="creation-motion"/);
});

test('a figure just made shows its picture on the card, and one the studio kept no record of keeps the diamond', () => {
  const made = artifact => {
    const h = setup(); h.S.state.courseId = 'one';
    h.S.creation.configure(['scene-description', 'story-outline', 'painting-to-figure']);
    h.click({create: 'edit-figure'}); h.click({create: 'figure'});
    h.finish(Object.assign({figure: {version: 1, parts: []}}, artifact ? {artifact_id: artifact} : {}));
    return h.root.innerHTML;
  };
  assert.match(made('r9'), /<img class="creation-result-figure" src="\/api\/courses\/one\/activities\/r9\?preview=1"/);
  const bare = made(null);
  assert.doesNotMatch(bare, /creation-result-figure/);
  assert.match(bare, /◇/);
});
