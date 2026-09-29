import test from 'node:test';
import assert from 'node:assert/strict';
import { loadStudio } from './load.mjs';

function node(tag, id) {
  return { tag, id, hidden: true, className: '', textContent: '', children: [],
    append(...v) { this.children.push(...v); }, replaceChildren() { this.children = []; }, addEventListener() {} };
}
function harness() {
  const byId = {}, made = [];
  const document = {
    getElementById: id => (byId[id] ||= node('div', id)),
    createElement: tag => { const el = node(tag); made.push(el); return el; },
  };
  const S = loadStudio({ files: ['src/29e-prompts.js'], globals: { document } });
  return { S, byId, made };
}
const book = { groups: [
  { id: 'feedback', name: { en: '聊聊你的画', zh: '聊聊你的画' }, note: null, entries: [
    { label: { en: 'First look', zh: '第一次点评' }, source: 'skills/art-feedback/assets/prompts/colour-opening.txt',
      text: 'Reply in {language} and in nothing else.' },
    { label: { en: 'Gone', zh: '缺失' }, source: 'studio/prompts/gone.txt', text: '', missing: true }] },
  { id: 'agent', name: { en: 'Agent', zh: '智能体' }, note: { en: '技能说明不在这里显示。', zh: '技能说明不在这里显示。' },
    entries: [{ label: { en: 'Every turn', zh: '每一轮' }, source: 'studio/showpiece/driver.py', text: 'Request: {request}' }] },
] };
const texts = el => [el.textContent, ...el.children.flatMap(texts)];

test('every group and instruction is shown, the wording exactly as it arrived', async () => {
  const { S, byId } = harness();
  S.state.transport = { prompts: async () => book };
  await S.prompts.open();
  const groups = byId['prompts-list'].children;
  assert.equal(groups.length, 2);
  assert.deepEqual(texts(groups[0].children[0]).filter(Boolean), ['聊聊你的画', '2 条指令']);
  const first = groups[0].children[1];
  assert.equal(first.tag, 'details');
  assert.equal(first.children[1].tag, 'pre');
  assert.equal(first.children[1].textContent, 'Reply in {language} and in nothing else.');
  assert.equal(groups[1].children[1].textContent, '技能说明不在这里显示。');
  assert.equal(byId['prompts-status'].textContent, '');
  assert.equal(byId['prompts-overlay'].hidden, false);
  assert.equal(byId['admin-overlay'].hidden, true);
});

test('wording that could not be found says so, naming where it was looked for', async () => {
  const { S, byId } = harness();
  S.state.transport = { prompts: async () => book };
  await S.prompts.open();
  const missing = byId['prompts-list'].children[0].children[2];
  assert.equal(missing.children[1].tag, 'p');
  assert.match(missing.children[1].textContent, /studio\/prompts\/gone\.txt/);
});

test('labels follow the page language and the wording itself does not change', async () => {
  const { S, byId } = harness();
  S.i18n.lang = 'zh';
  S.state.transport = { prompts: async () => book };
  await S.prompts.open();
  const group = byId['prompts-list'].children[0];
  assert.equal(group.children[0].children[0].textContent, '聊聊你的画');
  assert.equal(group.children[1].children[0].children[0].textContent, '第一次点评');
  assert.equal(group.children[1].children[1].textContent, 'Reply in {language} and in nothing else.');
});

test('the page only reads: it makes no field a teacher could type into and asks the server nothing else', async () => {
  const { S, made } = harness();
  const asked = [];
  S.state.transport = new Proxy({}, { get: (_, name) => async () => { asked.push(name); return book; } });
  await S.prompts.open();
  assert.deepEqual(asked, ['prompts']);
  assert.deepEqual(made.filter(el => ['input', 'textarea', 'select', 'button'].includes(el.tag)), []);
  assert.equal(made.some(el => 'contentEditable' in el), false);
});

test('preview mode, a failed read and a late answer each leave the page honest', async () => {
  const { S, byId } = harness();
  S.state.transport = { name: 'mock' };
  await S.prompts.open();
  assert.equal(byId['prompts-status'].textContent, '预览模式下无法查看提示词。');

  S.state.transport = { prompts: async () => { throw new Error('HTTP 503'); } };
  await S.prompts.open();
  assert.equal(byId['prompts-status'].textContent, '指令读取失败。请关闭此页后重新打开。');

  let answer;
  S.state.transport = { prompts: () => new Promise(resolve => { answer = resolve; }) };
  const pending = S.prompts.open();
  S.prompts.close();
  answer(book);
  await pending;
  assert.equal(byId['prompts-list'].children.length, 0);
  assert.equal(byId['admin-overlay'].hidden, false);
});
