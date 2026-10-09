import test from 'node:test';
import assert from 'node:assert/strict';
import { loadStudio } from './load.mjs';

function deferred() {
  let resolve, reject;
  const promise = new Promise((yes, no) => { resolve = yes; reject = no; });
  return { promise, resolve, reject };
}

function classroom() {
  const revoked = [], uploads = [];
  const S = loadStudio({ files: ['src/25-camera.js'], globals: {
    URL: { revokeObjectURL: url => revoked.push(url) }
  } });
  S.state.session = 'class-1';
  S.state.transport = {
    addDrawing: (id, blob) => { uploads.push({ id, blob }); return Promise.resolve({ drawing_id: 'art-1' }); },
    forgetSession: () => Promise.resolve()
  };
  const prepared = { blob: new Blob(['prepared']), url: 'blob:prepared' };
  S.photos.prepare = () => Promise.resolve(prepared);
  S.photos.stats = () => Promise.resolve({ mean: 170, variance: 100 });
  return { S, prepared, revoked, uploads };
}

test('switching classes during image preparation discards its URL before checking or uploading', async () => {
  const { S, prepared, revoked, uploads } = classroom();
  const decoding = deferred();
  S.photos.prepare = () => decoding.promise;
  S.photos.stats = () => assert.fail('a stale image must not be inspected');
  const importing = S.photos.importDrawing(new Blob(['original']));
  S.state.session = 'class-2';
  decoding.resolve(prepared);
  assert.equal(await importing, null);
  assert.equal(S.state.session, 'class-2');
  assert.equal(S.state.drawings.length, 0);
  assert.deepEqual(uploads, []);
  assert.deepEqual(revoked, ['blob:prepared']);
});

test('switching classes during the light check cannot upload into the newer class', async () => {
  const { S, revoked, uploads } = classroom();
  const checking = deferred(), started = deferred();
  S.photos.stats = () => { started.resolve(); return checking.promise; };
  const importing = S.photos.importDrawing(new Blob(['original']));
  await started.promise;
  S.state.session = 'class-2';
  checking.resolve({ mean: 170, variance: 100 });
  assert.equal(await importing, null);
  assert.equal(S.state.current, null);
  assert.deepEqual(uploads, []);
  assert.deepEqual(revoked, ['blob:prepared']);
});

test('ending a class while preparing an image stops the import before deletion completes', async () => {
  const { S, prepared, revoked, uploads } = classroom();
  const decoding = deferred(), deletion = deferred();
  S.photos.prepare = () => decoding.promise;
  S.state.transport.forgetSession = () => deletion.promise;
  const importing = S.photos.importDrawing(new Blob(['original']));
  const ending = S.session.end();
  decoding.resolve(prepared);
  assert.equal(await importing, null);
  assert.equal(S.state.session, 'class-1', 'the delete request is still pending');
  assert.deepEqual(uploads, []);
  assert.deepEqual(revoked, ['blob:prepared']);
  deletion.resolve();
  await ending;
});

test('a delayed camera or sample result retains the class that originally requested it', async () => {
  const { S, uploads, revoked } = classroom();
  S.state.session = 'class-2';
  S.photos.prepare = () => assert.fail('the old producer must be ignored before decoding');
  assert.equal(await S.photos.importDrawing(new Blob(['old sample']), 'class-1'), null);
  assert.deepEqual(uploads, []);
  assert.deepEqual(revoked, []);
});

test('a valid active image is prepared, checked and uploaded into its original class', async () => {
  const { S, prepared, revoked, uploads } = classroom();
  const drawing = await S.photos.importDrawing(new Blob(['original']));
  assert.equal(drawing.id, 'art-1');
  assert.equal(drawing.url, prepared.url);
  assert.equal(drawing.blob, prepared.blob);
  assert.deepEqual(uploads, [{ id: 'class-1', blob: prepared.blob }]);
  assert.equal(S.state.current, 'art-1');
  assert.equal(S.state.drawings.length, 1);
  assert.deepEqual(revoked, [], 'the displayed image still owns its URL');
});

test('a dark active image reports the light problem and releases its unused URL', async () => {
  const { S, revoked, uploads } = classroom();
  S.photos.stats = () => Promise.resolve({ mean: 10, variance: 5 });
  await assert.rejects(S.photos.importDrawing(new Blob(['dark'])), { code: 'dark_image' });
  assert.deepEqual(uploads, []);
  assert.deepEqual(revoked, ['blob:prepared']);
});

test('preparation errors are reported for the active class and ignored after a switch', async () => {
  const { S, revoked, uploads } = classroom();
  S.photos.prepare = () => Promise.reject(new Error('invalid image'));
  await assert.rejects(S.photos.importDrawing(new Blob()), /invalid image/);
  const decoding = deferred();
  S.photos.prepare = () => decoding.promise;
  const importing = S.photos.importDrawing(new Blob());
  S.state.session = 'class-2';
  decoding.reject(new Error('old failure'));
  assert.equal(await importing, null);
  assert.deepEqual(revoked, []);
  assert.deepEqual(uploads, []);
});

test('a failed light check and a failed upload each release the prepared URL once', async () => {
  for (const stage of ['stats', 'upload']) {
    const { S, revoked } = classroom();
    const fail = () => Promise.reject(new Error('failed ' + stage));
    if (stage === 'stats') S.photos.stats = fail;
    else S.state.transport.addDrawing = fail;
    await assert.rejects(S.photos.importDrawing(new Blob()), new RegExp('failed ' + stage));
    assert.deepEqual(revoked, ['blob:prepared']);
    assert.equal(S.state.drawings.length, 0);
  }
});
