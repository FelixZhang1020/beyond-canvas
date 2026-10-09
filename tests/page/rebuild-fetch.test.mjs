import test from 'node:test';
import assert from 'node:assert/strict';
import { steadyFetch } from '../../studio/showpiece/page/rebuild-runs.mjs';

// A request that never answers until it is called off, as the browser's copy of rebuild-hall.json did once a
// transfer the link left hanging held it.
const hanging = (signal) => new Promise((_, fail) => signal.addEventListener('abort', () => fail(Object.assign(new Error('aborted'), { name: 'AbortError' }))));

// A body that sends its pieces one at a time, `gap` milliseconds apart.
function trickle(pieces, gap) {
  return new ReadableStream({
    async pull(controller) {
      await new Promise((done) => setTimeout(done, gap));
      if (pieces.length) controller.enqueue(new TextEncoder().encode(pieces.shift())); else controller.close();
    },
  });
}

test('a file whose request hangs is asked for again past the browser\'s copy, and arrives', async () => {
  const asked = [];
  globalThis.fetch = (name, { cache, signal }) => {
    asked.push(cache);
    return cache === 'no-store' ? Promise.resolve(new Response('{"pieces":[1,2]}')) : hanging(signal);
  };
  const answer = await steadyFetch('rebuild-hall.json', 40);
  assert.deepEqual(await answer.json(), { pieces: [1, 2] });
  assert.deepEqual(asked, ['default', 'no-store']);
});

test('a transfer that stalls part way through is asked for again too', async () => {
  const asked = [];
  globalThis.fetch = (name, { cache, signal }) => {
    asked.push(cache);
    if (cache === 'no-store') return Promise.resolve(new Response('whole'));
    const body = new ReadableStream({
      start(controller) {
        controller.enqueue(new TextEncoder().encode('half'));
        signal.addEventListener('abort', () => controller.error(Object.assign(new Error('aborted'), { name: 'AbortError' })));
      },
    });
    return Promise.resolve(new Response(body));
  };
  assert.equal(await (await steadyFetch('rebuild-hall.glb', 40)).text(), 'whole');
  assert.deepEqual(asked, ['default', 'no-store']);
});

test('a slow link that keeps sending is waited for, not asked again', async () => {
  const asked = [];
  globalThis.fetch = (name, { cache }) => {
    asked.push(cache);
    return Promise.resolve(new Response(trickle(['a', 'b', 'c', 'd', 'e', 'f'], 15)));   // 90 ms in all, never 40 still
  };
  assert.equal(await (await steadyFetch('rebuild-hall.glb', 40)).text(), 'abcdef');
  assert.deepEqual(asked, ['default']);
});

test('a file the studio refuses keeps its answer, and a hang that does not clear says so', async () => {
  globalThis.fetch = () => Promise.resolve(new Response('missing', { status: 404 }));
  assert.equal((await steadyFetch('rebuild-nothing.json', 40)).status, 404);
  globalThis.fetch = (name, { signal }) => hanging(signal);
  await assert.rejects(steadyFetch('rebuild-hall.json', 20), { name: 'AbortError' });
});
