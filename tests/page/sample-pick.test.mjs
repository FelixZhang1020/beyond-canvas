import test from 'node:test';
import assert from 'node:assert/strict';
import { loadStudio } from './load.mjs';

// The sample sheet as the page builds it: an overlay, its note, a grid of cards (a thumbnail and a label in each)
// and a close button. Every line the note shows is kept, so a test can ask what the teacher read along the way.
function sheet() {
  const said = [];
  function element(tag) {
    return {
      tag, hidden: false, disabled: false, children: [], src: '', complete: false,
      append(...kids) { this.children.push(...kids); },
      appendChild(kid) { this.children.push(kid); },
      replaceChildren() { this.children = []; },
      removeAttribute(name) { if (name === 'src') { this.src = ''; this.complete = true; } },
      querySelectorAll(tag) {
        const found = [];
        (function walk(node) { node.children.forEach((kid) => { if (kid.tag === tag) found.push(kid); walk(kid); }); })(this);
        return found;
      },
    };
  }
  const note = element('p');
  Object.defineProperty(note, 'textContent', { get: () => said.at(-1), set: (text) => said.push(text) });
  const parts = { 'samples-overlay': element('div'), 'samples-grid': element('div'), 'samples-note': note, 'samples-close': element('button') };
  return { said, grid: parts['samples-grid'], document: { getElementById: (id) => parts[id], createElement: element } };
}

const CATALOG = { items: [
  { url: '/api/session/class-1/samples/a1', thumbnail_url: '/api/session/class-1/samples/a1?thumbnail=1' },
  { url: '/api/session/class-1/samples/b2', thumbnail_url: '/api/session/class-1/samples/b2?thumbnail=1' },
] };

// A full-size picture whose headers come and whose body then stops, as the live class saw: it sends its first half
// and nothing more until the request is called off.
function stalled(signal) {
  const body = new ReadableStream({
    start(controller) {
      controller.enqueue(new TextEncoder().encode('half'));
      signal?.addEventListener('abort', () => controller.error(Object.assign(new Error('aborted'), { name: 'AbortError' })));
    },
  });
  return new Response(body, { headers: { 'Content-Type': 'image/jpeg' } });
}

// A body that sends its pieces one at a time, `gap` milliseconds apart.
function trickle(pieces, gap) {
  return new Response(new ReadableStream({
    async pull(controller) {
      await new Promise((done) => setTimeout(done, gap));
      if (pieces.length) controller.enqueue(new TextEncoder().encode(pieces.shift())); else controller.close();
    },
  }), { headers: { 'Content-Type': 'image/jpeg' } });
}

// The class page with its sample sheet open on a slow link: `picture` answers each request for a full-size drawing.
async function library(picture) {
  const page = sheet(), asked = [], signals = [];
  const fetch = (url, options = {}) => {
    if (url.endsWith('/samples')) return Promise.resolve(new Response(JSON.stringify(CATALOG)));
    asked.push(options.cache); signals.push(options.signal);
    return Promise.resolve(picture(options, asked.length));
  };
  const S = loadStudio({ files: ['src/25b-samples.js'], globals: {
    document: page.document, fetch, AbortController, Blob, setTimeout, clearTimeout,
  } });
  S.state.session = 'class-1';
  S.state.transport = { name: 'http' };
  S.samples.idle = 40;
  const chosen = S.samples.choose();
  for (let i = 0; i < 100 && !page.grid.children.length; i++) await new Promise((done) => setTimeout(done, 1));
  return { S, page, asked, signals, chosen, cards: page.grid.children };
}

const STILL_WAITING = 'still waiting';
const within = (promise, ms) => Promise.race([promise, new Promise((done) => setTimeout(() => done(STILL_WAITING), ms))]);

test('a picked drawing that stops coming is asked for again past the browser\'s copy, and the class gets it', async () => {
  const { S, page, asked, chosen, cards } = await library(({ cache, signal }) =>
    cache === 'no-store' ? new Response('whole', { headers: { 'Content-Type': 'image/jpeg' } }) : stalled(signal));
  cards[0].onclick();
  const blob = await within(chosen, 1000);
  assert.notEqual(blob, STILL_WAITING, 'the sheet still says it is reading the library, every card disabled');
  assert.equal(await blob.text(), 'whole');
  assert.equal(blob.type, 'image/jpeg');
  assert.deepEqual(asked, ['default', 'no-store']);
  assert.ok(page.said.includes(S.i18n.t('samples.retrying')), `the note never said it was trying again: ${page.said}`);
});

test('a slow link that keeps sending is waited for, not asked again', async () => {
  const { asked, chosen, cards } = await library(() => trickle(['a', 'b', 'c', 'd', 'e', 'f'], 15));
  cards[1].onclick();
  const blob = await within(chosen, 1000);
  assert.notEqual(blob, STILL_WAITING);
  assert.equal(await blob.text(), 'abcdef');
  assert.equal(asked.length, 1, '90 ms in all, never 40 still, so one request is enough');
});

test('a drawing waiting for a free connection is not taken for a stall', async () => {
  const { asked, chosen, cards } = await library(({ signal }) => new Promise((done, fail) => {
    setTimeout(() => done(new Response('whole', { headers: { 'Content-Type': 'image/jpeg' } })), 100);
    signal.addEventListener('abort', () => fail(Object.assign(new Error('aborted'), { name: 'AbortError' })));
  }));
  cards[0].onclick();
  const blob = await within(chosen, 1000);
  assert.notEqual(blob, STILL_WAITING);
  assert.equal(await blob.text(), 'whole');
  assert.equal(asked.length, 1, 'its headers took 100 ms, more than 40 of silence but no stall in the body');
});

test('closing the sheet calls off the drawing still coming, and does not ask for it again', async () => {
  const { S, asked, signals, chosen, cards } = await library(({ signal }) => stalled(signal));
  cards[0].onclick();
  S.samples.close();
  assert.ok(signals[0].aborted, 'a download nobody wants keeps one of the browser\'s few connections');
  assert.equal(await chosen, null);
  await new Promise((done) => setTimeout(done, 120));
  assert.equal(asked.length, 1);
});

test('thumbnails still coming make way for the picked drawing, and come back if it cannot be read', async () => {
  const { S, page, chosen, cards } = await library(({ signal }) => stalled(signal));
  const [arrived, coming] = cards.map((card) => card.children[0]);
  arrived.src = '/api/session/class-1/samples/a1?thumbnail=1'; arrived.complete = true;
  coming.src = '/api/session/class-1/samples/b2?thumbnail=1';
  cards[0].onclick();
  assert.equal(arrived.src, '/api/session/class-1/samples/a1?thumbnail=1', 'a thumbnail already shown stays');
  assert.notEqual(coming.src, '/api/session/class-1/samples/b2?thumbnail=1',
    'a thumbnail still coming keeps one of the browser\'s few connections from the pick');
  assert.match(coming.src, /^data:image\//, 'with no src at all the browser draws a broken picture, and the card loses its square');
  await new Promise((done) => setTimeout(done, 200));
  assert.equal(page.said.at(-1), S.i18n.t('samples.unavailable'));
  assert.ok(cards.every((card) => !card.disabled), 'the cards can be picked again');
  assert.equal(coming.src, '/api/session/class-1/samples/b2?thumbnail=1');
  assert.equal(await within(chosen, 10), STILL_WAITING, 'the sheet stays open for another pick');
});
