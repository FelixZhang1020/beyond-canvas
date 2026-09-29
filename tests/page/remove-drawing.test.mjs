// Deleting a drawing from today's strip: the page lets go of it only once the studio has deleted it,
// the picture beside it takes its place, and a refusal says which one it was.
import test from 'node:test';
import assert from 'node:assert/strict';
import { loadStudio } from './load.mjs';

function page(removeDrawing) {
  const els = {}, released = [];
  const el = id => (els[id] = els[id] || { id, hidden: true, disabled: false, textContent: '', addEventListener() {} });
  const S = loadStudio({
    files: ['src/26e-remove-drawing.js'],
    globals: { document: { getElementById: el }, URL: { revokeObjectURL: url => released.push(url) }, setTimeout: () => 0, clearTimeout() {} },
  });
  S.state.transport = { removeDrawing };
  S.state.session = 's1';
  S.state.drawings = [{ id: 'd1', url: 'blob:one' }, { id: 'd2', url: 'blob:two' }, { id: 'd3', url: '/api/x' }];
  S.state.current = 'd2';
  S.state.feedback = { d2: { text: 'Warm.' } }; S.state.said = { d2: 'a dog' }; S.state.drafts = { d1: 'keep', d2: 'go' };
  S.state.chosen = ['d1', 'd2'];
  return { S, els, released };
}

test('a deleted drawing leaves the strip and the next one is shown in its place', async () => {
  const asked = [];
  const { S, released } = page((sid, did) => { asked.push([sid, did]); return Promise.resolve(null); });
  assert.equal(await S.session.removeDrawing('d2'), true);
  assert.deepEqual(asked, [['s1', 'd2']]);
  assert.deepEqual([...S.state.drawings.map(d => d.id)], ['d1', 'd3']);
  assert.equal(S.state.current, 'd3');
  assert.deepEqual(released, ['blob:two']);
  assert.equal(S.state.feedback.d2, undefined); assert.equal(S.state.said.d2, undefined);
  assert.deepEqual({ ...S.state.drafts }, { d1: 'keep' }); assert.deepEqual([...S.state.chosen], ['d1']);
});

test('the last drawing deleted leaves nothing shown', async () => {
  const { S } = page(() => Promise.resolve(null));
  S.state.drawings = [{ id: 'd2', url: '/api/x' }];
  await S.session.removeDrawing('d2');
  assert.equal(S.state.current, null);
});

test('a refusal keeps the drawing, and the teacher is told why in her own words', async () => {
  for (const [code, key] of [['in_book', 'inBook'], ['drawing_busy', 'busy'], ['course_closed', 'closed'], [undefined, 'failed']]) {
    const { S, els } = page(() => Promise.reject(Object.assign(new Error('HTTP 400'), { code })));
    S.removeDrawing.ask();
    assert.equal(els['remove-drawing-overlay'].hidden, false, 'it asks before deleting');
    await S.removeDrawing.confirm();
    assert.equal(S.state.drawings.length, 3);
    assert.equal(els.toast.textContent, S.i18n.t('remove.' + key));
    assert.equal(els['remove-drawing-overlay'].hidden, true);
  }
});

test('nothing is asked while the studio is still working', () => {
  const { S, els } = page(() => assert.fail('must not delete'));
  S.state.busy = true;
  S.removeDrawing.ask();
  assert.equal(S.removeDrawing.el('remove-drawing-overlay').hidden, true);
  assert.equal(els.toast.textContent, S.i18n.t('remove.busy'));
});
