// Deleting the whole class from Lesson settings: it asks once and names what goes, the page lets the
// class go only once the studio has deleted it, and a failure keeps the class and says so.
import test from 'node:test';
import assert from 'node:assert/strict';
import { loadStudio } from './load.mjs';

function page(deleteCourse) {
  const els = {}, asked = [];
  const el = id => (els[id] = els[id] || { id, hidden: true, disabled: false, textContent: '', addEventListener() {} });
  const S = loadStudio({
    files: ['src/26g-delete-class.js'],
    globals: { document: { getElementById: el }, URL: { revokeObjectURL() {} }, setTimeout: () => 0, clearTimeout() {} },
  });
  S.state.transport = { deleteCourse: id => { asked.push(['delete', id]); return deleteCourse(id); },
    forgetSession: id => { asked.push(['forget', id]); return Promise.resolve(null); } };
  S.state.session = 's1'; S.state.courseId = 'c1';
  S.state.settings = { title: '彩画课堂 · 09.24' };
  S.state.drawings = [{ id: 'd1', url: '/api/x' }, { id: 'd2', url: '/api/y' }];
  S.state.current = 'd1';
  S.portfolio = { actions: { home: () => asked.push(['home']) } };
  return { S, els, asked };
}

test('the button shows only while a class is open', () => {
  const { S, els } = page(() => Promise.resolve(null));
  S.deleteClass.sync();
  assert.equal(els['lesson-delete'].hidden, false);
  S.state.session = null; S.deleteClass.sync();
  assert.equal(els['lesson-delete'].hidden, true);
});

test('it asks first, naming the class and how many drawings go', () => {
  const { S, els, asked } = page(() => assert.fail('must not delete before the teacher confirms'));
  els['lesson-overlay'] = { hidden: false };
  S.deleteClass.ask();
  assert.equal(els['delete-class-overlay'].hidden, false);
  assert.equal(els['lesson-overlay'].hidden, true);
  assert.equal(els['delete-class-note'].textContent, S.i18n.t('deleteClass.note', { title: '彩画课堂 · 09.24', count: 2 }));
  assert.match(els['delete-class-note'].textContent, /彩画课堂 · 09\.24.*2 幅画/);
  S.deleteClass.close(true);
  assert.equal(els['lesson-overlay'].hidden, false, 'keeping it goes back to Lesson settings');
  assert.deepEqual(asked, []);
});

test('confirming deletes the course, lets the class go and returns to the Portfolio', async () => {
  const { S, els, asked } = page(() => Promise.resolve(null));
  S.deleteClass.ask();
  await S.deleteClass.confirm();
  assert.deepEqual(asked.map(a => a.join(':')), ['delete:c1', 'home']);
  assert.equal(S.state.session, null); assert.equal(S.state.drawings.length, 0);
  assert.equal(els['delete-class-overlay'].hidden, true);
  assert.equal(els.toast.textContent, S.i18n.t('deleteClass.done'));
});

test('a failure keeps the class open and says so', async () => {
  const { S, els, asked } = page(() => Promise.reject(new Error('HTTP 500')));
  S.deleteClass.ask();
  await S.deleteClass.confirm();
  assert.deepEqual(asked.map(a => a[0]), ['delete']);
  assert.equal(S.state.session, 's1');
  assert.equal(els['lesson-overlay'].hidden, false);
  assert.equal(els.toast.textContent, S.i18n.t('deleteClass.failed'));
});

test('once the course is deleted the page lets the class go without asking the studio again', async () => {
  const { S, asked } = page(() => Promise.resolve(null));
  S.state.transport.forgetSession = () => assert.fail('the studio already closed the editor');
  S.deleteClass.ask();
  await S.deleteClass.confirm();
  assert.deepEqual(asked.map(a => a[0]), ['delete', 'home']);
  assert.equal(S.state.session, null);
});

test('an unnamed class is named in the question by the name the studio gave it', async () => {
  const { S, els } = page(() => Promise.resolve(null));
  S.state.settings = { title: '', entrance: 'colour' };
  let fetched;
  S.portfolio.api = path => { fetched = path; return Promise.resolve({ title: '彩画课堂 · 09.24' }); };
  S.deleteClass.ask();
  assert.match(els['delete-class-note'].textContent, /「彩画课堂」/);
  await new Promise(resolve => setImmediate(resolve));
  assert.equal(fetched, '/c1');
  assert.match(els['delete-class-note'].textContent, /「彩画课堂 · 09\.24」的 2 幅画/);
});
