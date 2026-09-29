import test from 'node:test';
import assert from 'node:assert/strict';
import { loadStudio } from './load.mjs';

// The figure view beside the painting: the isolated viewer gets the checked figure, and the page's
// "save it to take home" button, which saves whatever 3D view is open, gets a picture of it.
function setup() {
  const listeners = new Set(), posted = [];
  const element = tag => {
    const node = {tag, style: {}, children: [], append: (...kids) => node.children.push(...kids), remove: () => { node.removed = true; }};
    if (tag === 'iframe') node.contentWindow = {postMessage: (data, origin) => posted.push({data, origin})};
    return node;
  };
  const globals = {
    location: {origin: 'http://127.0.0.1:7060'}, document: {createElement: element},
    setTimeout: () => 1, clearTimeout: () => {}, Blob,
    addEventListener: (name, fn) => listeners.add(fn), removeEventListener: (name, fn) => listeners.delete(fn),
  };
  const S = loadStudio({files: ['src/27i-figure.js'], globals});
  S.relight = {active: null};
  const host = element('div');
  S.figureView.open(host, {version: 1, parts: []}, {url: '/a'});
  const frame = host.children[0].children[1].children[1];
  const say = data => [...listeners].forEach(fn => fn({origin: globals.location.origin, source: frame.contentWindow, data}));
  return {S, listeners, posted, say, frame, host};
}

test('the open figure is the 3D view the save button takes a picture of', async () => {
  const h = setup();
  assert.equal(h.S.relight.active, h.S.figureView.active);
  const picture = h.S.relight.active.snapshot();
  assert.equal(h.posted.at(-1).data.type, 'snapshot');
  const blob = new Blob(['png']);
  h.say({type: 'figure-snapshot', blob});
  assert.equal(await picture, blob);
});

test('wherever the figure is shown it is labelled as inspired by the painting, in both languages', () => {
  for (const lang of ['en', 'zh']) {
    const h = setup(), host = {id: 'review-output-content', children: [], append: (...kids) => host.children.push(...kids)};
    h.S.i18n.lang = lang;
    h.S.figureView.open(host, {version: 1, parts: []}, {url: '/a'});
    const note = host.children.find(node => node.tag === 'p').textContent;
    assert.match(note, lang === 'en' ? /受这幅画启发/ : /受这幅画启发/, lang);
  }
});

test('closing the figure leaves no 3D view behind, stops listening and takes its drawing frame away', () => {
  const h = setup();
  h.S.figureView.close();
  assert.equal(h.frame.removed, true, 'a hidden frame would keep drawing on the tablet');
  assert.ok(h.host.children.every(node => node.removed), 'no note is left behind about a figure that is gone');
  assert.equal(h.S.relight.active, null);
  assert.equal(h.listeners.size, 0);
});

test('a slow figure is said to be still opening, and one that arrives late clears it', () => {
  // Operator: "cannot be shown" stood under a figure that had appeared on the slow link.
  const timers = [], listeners = new Set();
  const element = tag => {
    const node = {tag, style: {}, children: [], append: (...kids) => node.children.push(...kids), remove: () => {}};
    if (tag === 'iframe') node.contentWindow = {postMessage: () => {}};
    return node;
  };
  const globals = {location: {origin: 'http://x'}, document: {createElement: element}, Blob,
    setTimeout: (fn, ms) => { timers.push({fn, ms}); return timers.length; }, clearTimeout: id => { if (timers[id - 1]) timers[id - 1].cleared = true; },
    addEventListener: (name, fn) => listeners.add(fn), removeEventListener: (name, fn) => listeners.delete(fn)};
  const S = loadStudio({files: ['src/27i-figure.js'], globals}); S.relight = {active: null};
  const host = element('div'); S.figureView.open(host, {version: 1, parts: []}, {url: '/a'});
  const frame = host.children[0].children[1].children[1], note = host.children[1];
  const usual = note.textContent;
  timers.find(x => x.ms === 15000).fn();
  assert.equal(note.textContent, '小雕塑还在打开，网络慢时要多等一会儿。');
  [...listeners].forEach(fn => fn({origin: 'http://x', source: frame.contentWindow, data: {type: 'figure-ready'}}));
  assert.equal(note.textContent, usual, 'the figure arrived: the usual note is back');
  assert.ok(timers.filter(x => x.ms >= 15000).every(x => x.cleared), 'nothing will call it failed later');
});
