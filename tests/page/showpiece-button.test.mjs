import { test } from 'node:test';
import assert from 'node:assert/strict';
import { loadStudio } from './load.mjs';

function fakeDocument() {
  return { createElement: (tag) => ({ tag, attrs: {}, children: [], setAttribute(k, v) { this.attrs[k] = v; },
    appendChild(c) { this.children.push(c); }, classList: { add() {}, remove() {} } }) };
}

const scene = { version: 1, method: 'geometric-approximation', camera: {}, light: [-3, 6, 5], source_aspect: 1.5,
  objects: [{ kind: 'sphere', position: [0, 1, 0], size: [2, 2, 2], yaw: 0 }] };

test('the request body carries the fitted scene and the words the page speaks', () => {
  const S = loadStudio({ files: ['src/27h-showpiece.js'], globals: { document: fakeDocument() } });
  const b = S.showpiece.body(scene);
  assert.equal(b.scene, scene);
  assert.ok(b.request.length > 10 && !b.request.startsWith('showpiece.'));
});

test('a button lands on the light-study controls for a fitted scene, and on nothing else', () => {
  const S = loadStudio({ files: ['src/27h-showpiece.js'], globals: { document: fakeDocument() } });
  const controls = { children: [], appendChild(c) { this.children.push(c); } };
  const host = { querySelector: (sel) => (sel === '.relight-controls' ? controls : null) };
  const button = S.showpiece.attach(host, scene);
  assert.equal(button.tag, 'button');
  assert.equal(controls.children.length, 1);
  assert.equal(S.showpiece.attach(host, { ...scene, method: 'single-image-mesh' }), null);
  assert.equal(S.showpiece.attach({ querySelector: () => null }, scene), null);
});
