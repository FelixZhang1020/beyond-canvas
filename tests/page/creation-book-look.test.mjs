import test from 'node:test';
import assert from 'node:assert/strict';
import { loadStudio } from './load.mjs';

// Step 3 of the storybook (operator): the child's originals, each page its drawing or its clip, or
// every page redrawn by FLUX in one picture-book style, chosen after seeing page 1 in all seven.

function planner({skills = ['scene-description', 'story-outline', 'book-pictures'], entrance = 'colour', saved = {}} = {}) {
  const videos = [];
  const handlers = {}, root = {hidden: true, innerHTML: '', addEventListener: (n, fn) => handlers[n] = fn, querySelector: () => ({disabled: false}),
    // The clips step 3 plays, as the screen would hold them after it is drawn.
    querySelectorAll: () => [...root.innerHTML.matchAll(/data-clip="([^"]+)"/g)].map(m => {
      const video = {dataset: {clip: m[1]}, src: '', getAttribute: () => video.src || null, play: () => Promise.resolve()};
      videos.push(video); return video; })};
  const S = loadStudio({files: ['src/29a-creation.js', 'src/29h-lanes.js', 'src/29l-book-look.js'],
    globals: {queueMicrotask: () => {}, document: {getElementById: id => id === 'creation-planner' ? root : {style: {}, dataset: {}}}}});
  Object.assign(S.state, {session: 'one', mode: 'book', current: 'a', settings: {entrance}, said: {}, savedMade: saved,
    drawings: [{id: 'a', url: '/a'}, {id: 'b', url: '/b'}, {id: 'c', url: '/c'}], chosen: []});
  const calls = [];
  S.creation.init({active: () => true, stop: () => {}, open: () => {},
    run: (skill, ids, opts) => { calls.push({skill, ids: [...ids], opts}); S.state.making = skill; S.creation.render(); }});
  S.creation.configure(skills);
  S.portfolio = {api: path => Promise.resolve({outputs: {video_url: 'data:video/mp4;base64,' + path.split('/').pop()}})};
  const click = dataset => handlers.click({target: {closest: () => ({dataset, disabled: false})}});
  const finish = out => { const c = calls.at(-1); S.creation.completed(c.skill, out, null); S.state.making = null; S.creation.render(); };
  // Straight to step 3: a story of a, b and c is written and confirmed.
  S.creation.render(); S.state.chosen = ['a', 'b', 'c'];
  click({create: 'plot'});
  S.creation.completed('story-outline', {outline: ['a', 'b', 'c'].map(id => ({drawing_id: id, text: 'Page ' + id})), scenes: []}, null);
  S.state.busy = false; S.state.making = null; calls.length = 0;
  click({create: 'book'});
  return {S, root, calls, click, finish, videos};
}
const picture = (id, style, changed = false) => ({drawing_id: id, style, url: `/${style}-${id}.jpg`, changed});

test('confirming the story opens the choice of pictures, with the originals chosen and each clip ready to play', () => {
  const h = planner({saved: {b: {video: {skill: 'painting-to-animation', activityId: 'clip-b', kind: 'video'}}}});
  assert.match(h.root.innerHTML, /第 3 步 \/ 共 4 步/);
  assert.match(h.root.innerHTML, /data-look="original" aria-pressed="true"/);
  assert.match(h.root.innerHTML, /data-motion="b" data-on="1" aria-pressed="true"/, 'a page with a clip plays it unless she says');
  assert.doesNotMatch(h.root.innerHTML, /data-motion="a"/, 'a page with no clip has nothing to choose');
  h.click({motion: 'b', on: '0'});
  assert.match(h.root.innerHTML, /data-motion="b" data-on="0" aria-pressed="true"/);
  h.click({create: 'look-bind'});
  assert.deepEqual(h.calls.map(c => [c.skill, c.ids, c.opts.look, c.opts.motion]),
    [['drawings-to-storybook', ['a', 'b', 'c'], 'original', ['a', 'c']]]);
  assert.deepEqual(h.calls[0].opts.pages.map(p => p.text), ['Page a', 'Page b', 'Page c'], 'the confirmed words');
});

test('page 1 comes in every style, and the chosen one is drawn for the rest and binds by itself', () => {
  const h = planner();
  h.click({look: 'styled'});
  assert.match(h.root.innerHTML, /data-create="look-first"/);
  h.click({create: 'look-first'});
  assert.deepEqual([h.calls[0].skill, h.calls[0].ids, [...h.calls[0].opts.styles]], ['book-pictures', ['a'], ['watercolour', 'gouache', 'paper', 'clay', 'pencil', 'storybook', 'ink']]);
  assert.match(h.root.innerHTML, /正在画绘本插图/);
  h.finish({pictures: ['watercolour', 'gouache', 'paper', 'clay', 'pencil', 'storybook', 'ink'].map(s => picture('a', s))});
  assert.equal((h.root.innerHTML.match(/class="creation-pick" data-style="/g) || []).length, 7, 'seven pictures to choose from');
  assert.match(h.root.innerHTML, /data-create="look-use"[^>]*disabled/, 'nothing is drawn until she picks one');
  h.click({style: 'clay'});
  h.click({create: 'look-use'});
  assert.deepEqual([h.calls[1].skill, h.calls[1].ids, [...h.calls[1].opts.styles]], ['book-pictures', ['b', 'c'], ['clay']]);
  h.finish({pictures: [picture('b', 'clay'), picture('c', 'clay', true)]});
  const bind = h.calls[2];
  assert.deepEqual([bind.skill, bind.ids, bind.opts.look, bind.opts.motion], ['drawings-to-storybook', ['a', 'b', 'c'], 'clay', undefined]);
  h.finish({pages: [], look: 'clay'});
  assert.match(h.root.innerHTML, /第 3 页的新画可能和原画不太一样/, 'the page the check flagged is named');
});

test('a sample the check flagged goes back with the rest of the book once she picks it, and only once', () => {
  // A sample is drawn once (operator: faster books); the one she picks gets its second try with the rest (book_pictures.py).
  const h = planner();
  h.click({look: 'styled'}); h.click({create: 'look-first'});
  h.finish({pictures: ['watercolour', 'gouache', 'paper', 'clay', 'pencil', 'storybook', 'ink'].map(s => picture('a', s, s === 'clay'))});
  h.click({style: 'clay'}); h.click({create: 'look-use'});
  assert.deepEqual([h.calls[1].skill, h.calls[1].ids, [...h.calls[1].opts.styles]], ['book-pictures', ['a', 'b', 'c'], ['clay']]);
  h.finish({pictures: ['a', 'b', 'c'].map(id => ({...picture(id, 'clay', id === 'a'), again: true}))});
  assert.equal(h.calls[2].skill, 'drawings-to-storybook', 'still flagged after its second try: the book binds, marked');
  // A flagged sample that has had its second try already (an earlier book of the class) is not drawn a third time.
  const later = planner();
  later.click({look: 'styled'}); later.click({create: 'look-first'});
  later.finish({pictures: ['watercolour', 'gouache', 'paper', 'clay', 'pencil', 'storybook', 'ink'].map(s => ({...picture('a', s, true), again: s === 'ink'}))});
  later.click({style: 'ink'}); later.click({create: 'look-use'});
  assert.deepEqual(later.calls[1].ids, ['b', 'c']);
});

test('a style that did not pass is shown as not drawn and can be drawn again', () => {
  const h = planner();
  h.click({look: 'styled'}); h.click({create: 'look-first'});
  h.finish({pictures: ['watercolour', 'gouache', 'paper', 'pencil', 'storybook', 'ink'].map(s => picture('a', s))});
  assert.match(h.root.innerHTML, /这个风格没有画好/);
  assert.equal((h.root.innerHTML.match(/class="creation-pick" data-style="/g) || []).length, 6);
  assert.match(h.root.innerHTML, /data-style="clay" aria-pressed="false" disabled><strong>黏土<\/strong>/, 'listed, not choosable');
  h.click({create: 'look-first'});
  assert.equal(h.calls.at(-1).skill, 'book-pictures');
});

test('a studio without FLUX, or a sketch class, offers the originals only', () => {
  for (const h of [planner({skills: ['scene-description', 'story-outline']}), planner({entrance: 'sketch'})]) {
    assert.match(h.root.innerHTML, /data-look="original"/);
    assert.doesNotMatch(h.root.innerHTML, /data-look="styled"/);
  }
});

test('stopping the rest of a style never binds the book behind the teacher\'s back', () => {
  const h = planner();
  h.click({look: 'styled'}); h.click({create: 'look-first'});
  h.finish({pictures: ['watercolour', 'gouache', 'paper', 'clay', 'pencil', 'storybook', 'ink'].map(s => picture('a', s))});
  h.click({style: 'gouache'}); h.click({create: 'look-use'});
  h.S.creation.stopped('停下了'); h.S.state.making = null; h.S.creation.render();
  assert.equal(h.calls.length, 2, 'no book after the stop');
  assert.match(h.root.innerHTML, /data-style="gouache" aria-pressed="true"/, 'her choice is still there');
});

test('every style is listed with what it looks like, before page 1 is drawn and after', () => {
  const h = planner();
  h.click({look: 'styled'});
  const listed = [...h.root.innerHTML.matchAll(/<button type="button" data-style="([a-z]+)"[^>]*disabled><strong>([^<]+)<\/strong><span>([^<]+)<\/span>/g)];
  assert.deepEqual(listed.map(m => [m[1], m[2]]), [['watercolour', '水彩'], ['gouache', '水粉'], ['paper', '纸艺拼贴'], ['clay', '黏土'],
    ['pencil', '彩铅'], ['storybook', '故事画'], ['ink', '水墨淡彩']]);
  assert.ok(listed.every(m => m[3].length > 4), 'each says what it looks like');
  h.click({create: 'look-first'});
  h.finish({pictures: ['watercolour', 'gouache', 'paper', 'clay', 'pencil', 'storybook', 'ink'].map(s => picture('a', s, s === 'clay'))});
  assert.match(h.root.innerHTML, /<button type="button" data-style="clay" aria-pressed="false"><strong>黏土<\/strong><span>[^<]+<\/span><small class="is-changed">可能改动了原画<\/small>/);
  h.click({style: 'paper'});
  assert.match(h.root.innerHTML, /<button type="button" data-style="paper" aria-pressed="true"><strong>/, 'chosen in the list as on its picture');
});

test('a page set to its clip plays the clip in step 3, and to its drawing shows the drawing', async () => {
  const h = planner({saved: {b: {video: {skill: 'painting-to-animation', activityId: 'clip-b', kind: 'video'}}}});
  assert.match(h.root.innerHTML, /<video class="book-look-clip" data-clip="b" muted loop playsinline autoplay poster="\/b"><\/video>/);
  await new Promise(resolve => setImmediate(resolve));
  assert.equal(h.videos.at(-1).src, 'data:video/mp4;base64,clip-b', 'the saved clip, fetched once');
  h.click({motion: 'b', on: '0'});
  assert.doesNotMatch(h.root.innerHTML, /data-clip="b"/);
  assert.match(h.root.innerHTML, /<img src="\/b" alt=""><span>第 2 页<\/span>/);
});
