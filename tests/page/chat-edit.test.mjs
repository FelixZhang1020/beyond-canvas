// Taking back the child's last answer, or clearing a drawing's whole conversation. The page lets go
// of what it held only once the studio has erased it, reads what is left back from the saved
// course, and a refusal says which one it was.
import test from 'node:test';
import assert from 'node:assert/strict';
import { loadStudio } from './load.mjs';

const OPENING = { id: 'a1', skill: 'art-feedback', drawings: ['d1'], summary: { text: 'Snow.', question: 'Falling?', beat: 'opening' } };
const WORDS = { id: 'a2', skill: 'confirmed-words', drawings: ['d1'], summary: { text: 'Still falling' } };
const REPLY = { id: 'a3', skill: 'art-feedback', drawings: ['d1'], summary: { text: 'Softly.', beat: 'reply' } };

function page(forgetChat, left = []) {
  const els = {}, calls = [];
  const el = id => (els[id] = els[id] || { id, hidden: true, disabled: false, textContent: '', addEventListener() {},
    click() { calls.push('primary'); } });
  const S = loadStudio({
    files: ['src/26f-chat-edit.js'],
    globals: { document: { getElementById: el }, MutationObserver: class { observe() {} }, setTimeout: () => 0, clearTimeout() {} },
  });
  S.state.transport = { forgetChat };
  S.state.session = 's1'; S.state.courseId = 'c1'; S.state.mode = 'feedback';
  S.state.drawings = [{ id: 'd1', url: '/a' }, { id: 'd2', url: '/b' }]; S.state.current = 'd1';
  S.state.feedback = { d1: { text: 'Later.' }, d2: { text: 'Kept.' } };
  S.state.said = { d1: 'UNDONE', d2: 'kept' }; S.state.asked = { d1: 2 }; S.state.drafts = { d1: 'typed', d2: 'kept' };
  S.portfolio = { api: () => Promise.resolve({ activities: left }) };
  S.courseHistory = { said: { drawing: 'd1', text: 'UNDONE' }, clearDraft() { calls.push('clearDraft'); } };
  S.companion = { restoreFeedback: out => calls.push(['restore', out && out.text]), openHeard: () => calls.push('openHeard') };
  return { S, els, calls };
}

test('taking back an answer leaves the earlier rounds and opens the field to answer again', async () => {
  const asked = [];
  const { S, els, calls } = page((...args) => { asked.push(args); return Promise.resolve(null); }, [OPENING, WORDS, REPLY]);
  await S.chatEdit.undo();
  assert.deepEqual(asked, [['s1', 'd1', 'last-round']]);
  assert.equal(S.state.said.d1, 'Still falling');
  assert.equal(S.state.feedback.d1.text, 'Softly.');
  assert.equal(S.state.said.d2, 'kept', 'another drawing keeps its conversation');
  assert.equal(S.courseHistory.said, null, 'the erased words are not left pending on screen');
  assert.deepEqual(calls.filter(c => c !== 'clearDraft'), [['restore', 'Softly.'], 'openHeard']);
  assert.equal(els.toast.textContent, S.i18n.t('chatEdit.undone'));
});

test('taking back the only answer leaves the opening as what the companion last said', async () => {
  const { S } = page(() => Promise.resolve(null), [OPENING]);
  await S.chatEdit.undo();
  assert.equal(S.state.said.d1, undefined);
  assert.equal(S.state.feedback.d1.question, 'Falling?');
  assert.equal(S.state.asked.d1, 1);
});

test('clearing erases what the page held and stays idle until the teacher starts again', async () => {
  const asked = [];
  const { S, els, calls } = page((...args) => { asked.push(args); return Promise.resolve(null); });
  S.chatEdit.ask();
  assert.equal(els['chat-clear-overlay'].hidden, false, 'it asks before clearing');
  assert.deepEqual(asked, []);
  await S.chatEdit.confirm();
  assert.deepEqual(asked, [['s1', 'd1', 'conversation']]);
  assert.equal(els['chat-clear-overlay'].hidden, true);
  for (const held of ['feedback', 'said', 'asked', 'drafts']) assert.equal(S.state[held].d1, undefined, held);
  assert.equal(S.state.drafts.d2, 'kept');
  assert.deepEqual(calls.filter(c => c !== 'clearDraft'), [['restore', undefined]]);
  assert.equal(S.state.busy, false, 'clearing does not launch another model request');
});

test('a refusal keeps the conversation, and the teacher is told why in her own words', async () => {
  for (const [code, key] of [['drawing_busy', 'busy'], ['nothing_to_undo', 'nothing'], ['course_closed', 'closed'], [undefined, 'failed']]) {
    const { S, els } = page(() => Promise.reject(Object.assign(new Error('HTTP 400'), { code })));
    await S.chatEdit.undo();
    assert.equal(S.state.said.d1, 'UNDONE');
    assert.equal(els.toast.textContent, S.i18n.t('chatEdit.' + key));
    S.chatEdit.ask(); await S.chatEdit.confirm();
    assert.equal(S.state.feedback.d1.text, 'Later.');
    assert.equal(els['chat-clear-overlay'].hidden, true);
  }
});

test('nothing is taken back while the companion is still answering', async () => {
  const { S, els } = page(() => assert.fail('must not ask the studio'));
  S.state.busy = true;
  await S.chatEdit.undo();
  S.chatEdit.ask();
  assert.equal(S.chatEdit.el('chat-clear-overlay').hidden, true);
  assert.equal(els.toast.textContent, S.i18n.t('chatEdit.busy'));
});

test('the buttons show only when there is something to take back', () => {
  const { S, els } = page(() => Promise.resolve(null));
  S.chatEdit.sync();
  assert.equal(els['btn-chat-undo'].hidden, false); assert.equal(els['btn-chat-clear'].hidden, false);
  delete S.state.said.d1; S.chatEdit.sync();
  assert.equal(els['btn-chat-undo'].hidden, true, 'no answer to take back'); assert.equal(els['btn-chat-clear'].hidden, false);
  delete S.state.feedback.d1; S.chatEdit.sync();
  assert.equal(els['chat-edit'].hidden, true, 'a drawing nobody has talked about yet');
});
