// The class's name lives in Lesson settings: filled when the sheet opens, saved with the rest of it.
import test from 'node:test';
import assert from 'node:assert/strict';
import { loadStudio } from './load.mjs';

function page(api) {
  const els = {}, calls = [];
  const el = id => (els[id] = els[id] || { id, hidden: true, value: '' });
  const S = loadStudio({ files: ['src/26h-course-name.js'], globals: { document: { getElementById: el } } });
  S.state.session = 's1'; S.state.courseId = 'c1'; S.state.settings = { title: '光影课' };
  S.portfolio = { api: (path, opts) => { calls.push([path, opts && JSON.parse(opts.body)]); return api(path, opts); } };
  return { S, els, calls };
}

test('the sheet opens with the class name, and without the field when no class is open', () => {
  const { S, els } = page(() => assert.fail('a named class is not asked for'));
  S.courseName.fill();
  assert.equal(els['lesson-name-field'].hidden, false); assert.equal(els['f-name'].value, '光影课');
  S.state.session = null; S.courseName.fill();
  assert.equal(els['lesson-name-field'].hidden, true);
});

test('an unnamed class shows the dated name the studio gave it', async () => {
  const { S, els, calls } = page(() => Promise.resolve({ title: '彩画课堂 · 09.24' }));
  S.state.settings.title = '';
  await S.courseName.fill();
  assert.deepEqual(calls, [['/c1', undefined]]);
  assert.equal(els['f-name'].value, '彩画课堂 · 09.24'); assert.equal(S.state.settings.title, '彩画课堂 · 09.24');
});

test('a changed name is saved to the class and shown from then on', async () => {
  const { S, els, calls } = page(() => Promise.resolve(null));
  els['f-name'] = { value: '  星空下的花园 ' };
  assert.equal(await S.courseName.save(), true);
  assert.deepEqual(calls, [['/c1', { title: '星空下的花园' }]]);
  assert.equal(S.state.settings.title, '星空下的花园');
});

test('an empty or unchanged name saves nothing', async () => {
  const { S, els, calls } = page(() => assert.fail('nothing to save'));
  for (const value of ['', '   ', '光影课']) {
    els['f-name'] = { value };
    assert.equal(await S.courseName.save(), false);
  }
  assert.deepEqual(calls, []);
});

test('a refused rename keeps the old name and lets Save report it', async () => {
  const { S, els } = page(() => Promise.reject(new Error('Course history unavailable')));
  els['f-name'] = { value: '新名字' };
  await assert.rejects(S.courseName.save());
  assert.equal(S.state.settings.title, '光影课');
});
