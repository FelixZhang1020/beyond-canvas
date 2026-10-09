import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { fetchAhead, nextStop, tourFrom, tourHref, tourOrder } from '../../studio/showpiece/page/rebuild-tour.mjs';
import { filesOf, whichRun } from '../../studio/showpiece/page/rebuild-runs.mjs';
import { resultOf } from '../../studio/showpiece/page/rebuild-compare.mjs';

const page = (name) => new URL(`../../studio/showpiece/page/${name}`, import.meta.url);
const load = (name) => JSON.parse(readFileSync(page(name), 'utf8'));
const { designs } = load('rebuild-designs.json');
const words = load('rebuild-strings.json');
const html = readFileSync(page('rebuild.html'), 'utf8');
const bar = html.slice(html.indexOf('<nav class="runs"'), html.indexOf('</nav>'));

test('the tour plays the four rebuilds, then every design in its listed order, and round again after the last', () => {
  const order = tourOrder(designs);
  assert.deepEqual(order.slice(0, 4), [1, 2, 3, 4]);
  assert.deepEqual(order.slice(4), designs.map(({ n }) => `design${n}`));
  assert.equal(order.length, 4 + designs.length);
  const visited = [order[0]];
  for (let i = 1; i < order.length; i++) visited.push(nextStop(order, visited.at(-1)));
  assert.deepEqual(visited, order, 'each attempt once, in order');
  assert.equal(nextStop(order, order.at(-1)), 1, 'the last goes back to the first');
});

test('every stop of the tour opens the attempt it names, carrying the tour, its speed and its key-moments choice', () => {
  for (const run of tourOrder(designs)) {
    const href = tourHref(run, { speed: '2', keys: true }), search = href.slice(href.indexOf('?'));
    assert.equal(String(whichRun(search)), String(run), href);
    assert.deepEqual(tourFrom(search), { on: true, speed: '2', keys: true }, href);
  }
});

test('an address without a tour plays one attempt at the plain speed, and an unknown speed is not taken', () => {
  assert.deepEqual(tourFrom('?run=2'), { on: false, speed: '1', keys: false });
  assert.equal(tourFrom('?run=2&tour=1&speed=99').speed, '1');
  assert.equal(tourHref(4).includes('speed'), false);
});

test('the tour button sits in the bar of attempts, after its chips', () => {
  assert.ok(bar.indexOf('id="tour"') > bar.indexOf('id="design-runs"'), 'the button follows the design chips');
});

// Each page the tour opens showed four chips for seconds, until the designs' were added (operator): the bar is
// written whole, so its chips must be the designs listed, in order, each coloured as its record ends.
test('the bar is written with every attempt the tour plays, in its order, each with the result its record gives', () => {
  const chips = [...bar.matchAll(/<a class="run-chip" data-run="([^"]+)" data-result="(\w+)" href="([^"]+)"><b>(\d+)<\/b><em>([^<]+)<\/em>/g)];
  assert.deepEqual(chips.map(([, run]) => run), tourOrder(designs).map(String));
  for (const [, run, result, href, n, said] of chips) {
    if (!run.startsWith('design')) continue;
    assert.equal(result, resultOf(load(filesOf(run).record)), run);
    assert.equal(said, words[`result.${result}`], run);
    assert.equal(href, `rebuild.html?design=${n}`);
    assert.equal(`design${n}`, run);
  }
  assert.equal(/id="design-runs"[^>]*hidden/.test(bar), false, 'the designs show before the list arrives');
});

test('the tour button reads before the page script arrives as the page script would have it read', () => {
  assert.ok(bar.includes(`>${words['tour.start']}</button>`), 'the button as written');
  assert.ok(html.includes(`textContent = "${words['tour.stop']}"`), 'the button while a tour runs');
});

test('while one attempt plays, the next one\'s record and hall are fetched ahead', async () => {
  const asked = [];
  fetchAhead('design3', async (name) => { asked.push(name); return { arrayBuffer: async () => new ArrayBuffer(0) }; });
  fetchAhead(2, async () => { throw new Error('offline'); });                    // a failed fetch says nothing
  await new Promise((done) => setTimeout(done, 0));
  assert.deepEqual(asked, ['rebuild-design3-record.json', 'rebuild-design3-hall.json', 'rebuild-design3-hall.glb']);
});
