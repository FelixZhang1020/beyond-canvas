import {boundedAsset} from './asset-guard.mjs';
import assert from 'node:assert/strict';
import {readFile} from 'node:fs/promises';

const root = new URL('./', import.meta.url);
const manifest = JSON.parse(await readFile(new URL('manifest.json', root)));
let requests = 0, payload;
globalThis.fetch = async () => {requests++; return new Response(payload);};
for (const sample of manifest.samples) for (const item of sample.cases) {
  if (item.status !== 'ready') continue;
  payload = await readFile(new URL(item.asset, root));
  const parsed = await boundedAsset(item, new AbortController().signal);
  assert.equal(parsed.byteLength, item.bytes);
}
const good = manifest.samples[0].cases[0];
payload = await readFile(new URL(good.asset, root));
const before = requests;
await assert.rejects(boundedAsset({...good, asset: '../.env'}), /预算/);
await assert.rejects(boundedAsset({...good, bytes: 17 * 1024 * 1024}), /预算/);
assert.equal(requests, before, 'invalid paths and oversized metadata must fail before fetch');
await assert.rejects(boundedAsset({...good, sha256: '0'.repeat(64)}), /校验/);
await assert.rejects(boundedAsset({...good, bytes: good.bytes + 1}), /大小/);
payload = Buffer.alloc(20);
await assert.rejects(boundedAsset({...good, bytes: 20}), /格式/);

function makeGLB(header) {
  let text = JSON.stringify(header); text += ' '.repeat((4 - text.length % 4) % 4);
  const bytes = Buffer.alloc(20 + text.length);
  [0x46546c67, 2, bytes.length, text.length, 0x4e4f534a].forEach((v, i) => bytes.writeUInt32LE(v, i * 4));
  bytes.write(text, 20); return bytes;
}
payload = makeGLB({buffers: [{uri: 'https://unwanted.example/file'}]});
await assert.rejects(boundedAsset({...good, bytes: payload.length}), /自包含/);
payload = makeGLB({accessors: [{count: 1050003}], meshes: [{primitives: [{attributes: {POSITION: 0}}]}]});
await assert.rejects(boundedAsset({...good, bytes: payload.length}), /三角面/);
payload = Buffer.alloc(17 * 1024 * 1024);
await assert.rejects(boundedAsset({...good}), /过大/);
console.log(`Validated ${manifest.ready} real GLBs and 8 negative load controls; no texture or mesh decoding.`);
