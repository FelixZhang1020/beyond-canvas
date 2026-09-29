// The quick line is spoken at once; the checked answer waits for it to finish, and
// is dropped if the teacher has moved to another drawing (operator).
import test from 'node:test';
import assert from 'node:assert/strict';
import { loadStudio } from './load.mjs';

function setup() {
  const S = loadStudio({ files: ['src/26-companion.js'], globals: { setTimeout: () => 1, clearTimeout: () => {} } });
  const spoken = []; let finish = null;
  S.voice.speak = (text, opts) => { spoken.push(text); if (opts && opts.onend) finish = opts.onend; };
  S.courseHistory = { showBridge: () => {} };
  S.state.current = 'a';
  return { S, spoken, end: () => finish && finish() };
}

test('the answer that arrives during the bridge is spoken after it, not over it', () => {
  const { S, spoken, end } = setup();
  S.companion.bridge('你说它要去找朋友玩呀。', 'a');
  S.companion.speak('检查过的回答');
  assert.deepEqual(spoken, ['你说它要去找朋友玩呀。']);
  end();
  assert.deepEqual(spoken, ['你说它要去找朋友玩呀。', '检查过的回答']);
});

test('an answer for a drawing the teacher has left is not spoken', () => {
  const { S, spoken, end } = setup();
  S.companion.bridge('你说它要去找朋友玩呀。', 'a');
  S.companion.speak('检查过的回答');
  S.state.current = 'b';
  end();
  assert.deepEqual(spoken, ['你说它要去找朋友玩呀。']);
});

test('with no bridge playing, an answer is spoken at once', () => {
  const { S, spoken } = setup();
  S.companion.speak('检查过的回答');
  assert.deepEqual(spoken, ['检查过的回答']);
});

test('moving to another drawing ends the bridge, so that drawing is not kept silent', () => {
  const { S, spoken } = setup();
  S.companion.bridge('你说它要去找朋友玩呀。', 'a');
  S.companion.speak('A 的回答');
  S.state.current = 'b'; S.companion.endBridge();   // what the page's 'current' event does
  S.companion.speak('B 的开场');
  assert.deepEqual(spoken, ['你说它要去找朋友玩呀。', 'B 的开场']);
});
