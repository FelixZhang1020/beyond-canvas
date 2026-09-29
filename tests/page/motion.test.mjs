import test from 'node:test';
import assert from 'node:assert/strict';
import { loadStudio } from './load.mjs';
const files = ['src/27c-motion.js'];
const layer = (move = 'sway', box = [.1, .1, .6, .7]) => ({ move, box, start_s: 0, end_s: 6, distance: [.018, -.012] });

test('loops return to the exact source mesh and move visibly between endpoints', () => {
  const m = loadStudio({ files }).motion;
  for (const move of ['sway', 'breathe', 'grow', 'rise', 'drift', 'enter', 'exit']) {
    const layers = [layer(move)], mesh = m.mesh(1280, 900, layers, 48);
    const start = Array.from(m.deform(mesh, layers, 0));
    const peak = Array.from(m.deform(mesh, layers, 2));
    assert.ok(peak.some((x, i) => Math.abs(x - start[i]) > .002), move + ' visibly moves');
    assert.deepEqual(Array.from(m.deform(mesh, layers, 6)), start, move + ' loops without a jump');
    for (let i = 0; i < start.length; i += 4) {
      assert.equal(start[i], start[i + 2]); assert.equal(start[i + 1], start[i + 3]);
    }
  }
});

test('outside the region and at the image edge the source coordinates never change', () => {
  const m = loadStudio({ files }).motion, layers = [layer()], mesh = m.mesh(900, 900, layers, 48);
  const v = m.deform(mesh, layers, 2);
  mesh.points.forEach((p, i) => {
    if (p.u <= .1 || p.u >= .7 || p.v <= .1 || p.v >= .8) {
      assert.equal(v[i * 4], v[i * 4 + 2]); assert.equal(v[i * 4 + 1], v[i * 4 + 3]);
    }
  });
});

test('overlapping extreme plans never fold or invert a mesh triangle', () => {
  const m = loadStudio({ files }).motion;
  const layers = [layer('grow'), layer('sway', [.0, .0, 1, 1]), layer('rise', [.35, .35, .08, .09])];
  layers.forEach(l => { l.distance = [1, -1]; });
  const mesh = m.mesh(1280, 720, layers, 48);
  for (let t = 0; t <= 6; t += .1) {
    const v = m.deform(mesh, layers, t);
    for (let i = 0; i < mesh.indices.length; i += 3) {
      const [a, b, c] = Array.from(mesh.indices.slice(i, i + 3), n => n * 4);
      const area = (v[b] - v[a]) * (v[c + 1] - v[a + 1]) - (v[c] - v[a]) * (v[b + 1] - v[a + 1]);
      assert.ok(area > 0, 'no inverted triangle can tear the picture');
    }
  }
});

test('a 48 megapixel photo fits the rendering budget with its aspect ratio intact', () => {
  const m = loadStudio({ files }).motion;
  assert.deepEqual(Array.from(m.dimensions(8000, 6000, m.MAX_EDGE)), [1280, 960]);
  assert.deepEqual(Array.from(m.dimensions(6000, 8000, 640)), [480, 640]);
  assert.deepEqual(Array.from(m.dimensions(400, 200, 1280)), [400, 200]);
});

test('malformed plans fail locally before allocating a renderer', () => {
  const m = loadStudio({ files }).motion, good = { duration_s: 6, layers: [layer()] };
  assert.equal(m.valid(good), true);
  for (const bad of [null, {}, { ...good, duration_s: Infinity }, { ...good, layers: [null] },
    { ...good, layers: [{ ...layer(), box: [0, 0, NaN, 1] }] },
    { ...good, layers: [{ ...layer(), distance: [NaN, 0] }] },
    { ...good, layers: Array(4).fill(layer()) }]) assert.equal(m.valid(bad), false);
});

test('closing before image load prevents late rendering and a second player releases the first', () => {
  const images = [], canvases = [];
  const S = loadStudio({ files, globals: {
    Image: class { constructor() { images.push(this); } },
    document: { createElement: () => { const c = {}; canvases.push(c); return c; } },
    cancelAnimationFrame() {},
  } });
  const host = { appendChild() {} }, plan = { duration_s: 6, layers: [layer()] };
  S.motion.play(host, plan, { url: 'local-a' });
  const lateLoad = images[0].onload;
  S.motion.play(host, plan, { url: 'local-b' });
  assert.equal(images[0].onload, null);
  assert.equal(canvases[0].width, 1);
  lateLoad(); // Cannot create WebGL, schedule frames, or resurrect the old view.
  S.motion.stop();
  assert.equal(images[1].onload, null);
  assert.equal(S.motion.active, null);
});

test('teacher selection uses image fractions, clips to the paper and rejects accidental taps', () => {
  const m = loadStudio({ files }).motion;
  assert.deepEqual(Array.from(m.selection([.8,.9],[.2,.3])).map(n=>Math.round(n*100)), [20,30,60,60]);
  assert.deepEqual(Array.from(m.selection([-.5,-.2],[1.5,1.2])), [0,0,1,1]);
  assert.equal(m.selection([.4,.4],[.405,.405]), null);
});
