import test from 'node:test';
import assert from 'node:assert/strict';
import { loadStudio } from './load.mjs';

// The teacher's choice of clip maker, with how long each takes (operator): the Spark's own
// 5 s clip, or Wan 3.0's 5 s clip online, which sends the drawing to Alibaba and says so.
function setup(makers) {
  const handlers = {}, controls = {};
  const root = {hidden: true, innerHTML: '', addEventListener: (name, fn) => handlers[name] = fn,
    querySelector: selector => controls[selector] ||= {disabled: false}};
  const app = {dataset: {}}, calls = [];
  const S = loadStudio({files: ['src/29a-creation.js', 'src/29h-lanes.js'], globals: {queueMicrotask: () => {}, document: {getElementById: id => id === 'creation-planner' ? root : app}}});
  Object.assign(S.state, {session: 'one', mode: 'move', current: 'a', settings: {entrance: 'colour'}, drawings: [{id: 'a', url: '/a'}],
    motionDrafts: {a: 'The river flows.'}, capabilities: makers ? {video_makers: makers} : {}});
  S.creation.init({active: () => true, run: (skill, ids, opts) => calls.push({skill, ids, opts}), stop: () => {}, open: () => {}});
  const click = dataset => handlers.click({target: {closest: () => ({dataset, disabled: false})}});
  S.creation.render();
  return {S, root, calls, click, handlers};
}

test('both clip makers are offered with their times, online first, and it says where the drawing goes', () => {
  const h = setup(['spark', 'online']);
  assert.doesNotMatch(h.root.innerHTML, /creation-clip/, 'the outcomes are shown before the editor');
  h.click({create: 'edit-video'});
  assert.match(h.root.innerHTML, /<select id="creation-clip" name="creation-clip">/, 'one drop-down, not cards');
  assert.match(h.root.innerHTML, /<option value="spark">工作室自己的机器（Wan 2\.2）· 5 秒 · 大约 18 分钟<\/option>/);
  assert.match(h.root.innerHTML, /<option value="online" selected>在线生成（Wan 3\.0）· 5 秒 · 大约 2 分钟<\/option>/);
  assert.match(h.root.innerHTML, /这幅画会发送给阿里云/, 'the note stands with the online choice');
  h.handlers.change({target: {name: 'creation-clip', value: 'spark'}});
  assert.match(h.root.innerHTML, /<option value="spark" selected>/);
  assert.doesNotMatch(h.root.innerHTML, /阿里云/);
});

test('online is chosen until the teacher picks the Spark, and the choice goes with the request', () => {
  // Operator: online by default, about 2 minutes against 18.
  const h = setup(['spark', 'online']);
  h.click({create: 'edit-video'});
  h.click({create: 'confirm'});
  assert.equal(h.calls.at(-1).opts.clip_maker, 'online');
  h.handlers.change({target: {name: 'creation-clip', value: 'spark'}});
  h.click({create: 'confirm'});
  assert.equal(h.calls.at(-1).opts.clip_maker, 'spark');
  assert.equal(h.calls.at(-1).opts.media_kind, 'video');
});

test('a studio with one clip maker shows no choice and asks for none', () => {
  for (const makers of [null, ['spark']]) {
    const h = setup(makers);
    h.click({create: 'edit-video'});
    assert.doesNotMatch(h.root.innerHTML, /creation-clip/);
    h.click({create: 'confirm'});
    assert.equal('clip_maker' in h.calls.at(-1).opts, false);
  }
});

test('a clip maker the studio has closed shows greyed and cannot be chosen', () => {
  // Operator: the Spark's clip holds about 72 GB for eighteen minutes.
  const h = setup(['online']);
  h.S.state.capabilities.video_makers_closed = ['spark']; h.click({create: 'edit-video'});
  assert.match(h.root.innerHTML, /<option value="spark" disabled>工作室自己的机器（Wan 2\.2）· 5 秒 · 大约 18 分钟（暂不开放：占用内存太多）<\/option>/);
  assert.match(h.root.innerHTML, /<option value="online" selected>/);
  h.S.state.clipMaker = 'spark'; h.click({create: 'confirm'});
  assert.equal(h.calls.at(-1).opts.clip_maker, 'online', 'a closed maker is never sent');
});
