import { test } from 'node:test';
import assert from 'node:assert/strict';
import { loadStudio } from './load.mjs';

class Element {
  constructor(tag) { this.tag = tag; this.children = []; this.attrs = {}; }
  appendChild(node) { this.children.push(node); }
  setAttribute(key, value) { this.attrs[key] = value; }
}
const S = loadStudio({ files: ['src/27-media.js'], globals: {
  document: { createElement: tag => new Element(tag) },
  Image: class extends Element { constructor() { super('img'); } },
  requestAnimationFrame: () => { throw Error('still preview must not start an animation'); }
} });

test('keyframe viewer preserves the original and marks only the generated PNG for export', () => {
  const host = new Element('div'), original = 'blob:original';
  const generated = 'data:image/png;base64,abc';
  S.media.keyframe(host, { kind: 'keyframe', image: generated }, { url: original });
  const [left, right] = host.children[0].children;
  assert.equal(left.children[1].src, original);
  assert.equal(left.children[1].attrs['data-keyframe'], undefined);
  assert.equal(right.children[1].src, generated);
  assert.equal(right.children[1].attrs['data-keyframe'], 'true');
  assert.equal(host.children[1].textContent, S.i18n.t('keyframe.note'));
});

test('malformed and remote keyframe payloads fail visibly without loading an image', () => {
  for (const frame of [null, {}, {kind: 'keyframe', image: 'https://example.com/private.png'}]) {
    const host = new Element('div');
    S.media.keyframe(host, frame, {url: 'blob:original'});
    assert.equal(host.children.length, 0);
    assert.equal(host.textContent, S.i18n.t('keyframe.failed'));
  }
});

test('every keyframe label has Chinese, the only language there is', () => {
  const keys = Object.keys(S.strings.zh).filter(k => k.startsWith('keyframe.'));
  assert.ok(keys.length > 0, 'no keyframe labels found at all');
  for (const key of keys) assert.ok(S.strings.zh[key], key);
});
