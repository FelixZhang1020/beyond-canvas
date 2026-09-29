// Words a model is still writing. A teacher review shows in its own panel as it is written
// (operator). The companion's words in the chat do not: they arrive whole once they
// have passed the rules, like a message in a chat (operator), and nothing unchecked
// is ever on the screen or read aloud.
import test from 'node:test';
import assert from 'node:assert/strict';
import { loadStudio } from './load.mjs';

function setup() {
  class Element {
    children = []; hidden = false; parent = null; text = ''; dataset = {}; disabled = false; names = new Set();
    get className() { return [...this.names].join(' '); }
    set className(v) { this.names = new Set(String(v).split(' ').filter(Boolean)); }
    get textContent() { return this.text; }
    set textContent(v) { this.text = v; this.children = []; }
    classList = { add: n => this.names.add(n), remove: n => this.names.delete(n), contains: n => this.names.has(n), toggle() {} };
    querySelector(sel) { return this.children.find(k => k.names.has(sel.slice(1))) || null; }
    querySelectorAll(sel) { return this.children.filter(k => k.names.has(sel.slice(1))); }
    appendChild(e) { e.parent = this; this.children.push(e); return e; }
    replaceChildren(...kids) { this.children = []; kids.forEach(k => this.appendChild(k)); }
    contains(e) { return this.children.includes(e); }
    remove() { if (this.parent) this.parent.children = this.parent.children.filter(x => x !== this); }
  }
  const els = new Map(), el = id => { if (!els.has(id)) els.set(id, new Element()); return els.get(id); };
  const S = loadStudio({ files: ['src/24c-portfolio.js', 'src/26-companion.js', 'src/26c-course-history.js', 'src/29g-text-stream.js'],
    globals: { document: { createElement: () => new Element(), getElementById: el } } });
  S.companion.els = { bubble: el('bubble'), say: el('btn-say'), ask: el('ask') };
  let spoken = 0; S.voice.speak = () => { spoken++; };
  Object.assign(S.state, { session: 'class', courseId: 'course', current: 'a', runSince: Date.now(), transport: { name: 'http' } });
  el('ask').hidden = true;
  return { S, el, spoken: () => spoken };
}
const words = node => node.children.map(k => k.children.length ? words(k) : k.textContent).flat();
const writing = (text, question = '', more = {}) => Object.assign({ text, question, writing: true, revised: false }, more);

test('words the companion is still writing or checking never reach the screen', () => {
  const { S, el, spoken } = setup();
  el('history-messages').appendChild(S.portfolio.text('p', '这幅画还没有保存的聊天。', 'history-empty'));
  S.textStream.partial('art-feedback', writing('我看见'), { id: 'a' }, true);
  S.textStream.partial('art-feedback', Object.assign(writing('我看见一只熊。', '它要去哪里？'), { writing: false, checking: true }),
                       { id: 'a' }, true);
  assert.deepEqual(words(el('history-messages')), ['这幅画还没有保存的聊天。'], 'the thread gets no draft');
  assert.doesNotMatch(el('bubble').textContent, /熊|哪里/, 'nor does the bubble');
  assert.match(el('bubble').textContent, /检查/, 'the bubble says only what the companion is doing');
  assert.equal(spoken(), 0);
});

test('the checked words arrive whole, as the partner\'s turn, where the typing was', () => {
  const { S, el } = setup();
  S.courseHistory.saved = 2;
  S.courseHistory.showBridge('我听到啦！让我再好好看看你的画。');
  S.textStream.partial('art-feedback', writing('我看见一只熊。', '它要去哪里？'), { id: 'a' }, true);
  S.textStream.settle({ text: '我看见一只熊。', question: '它要去哪里？' });
  S.companion.say('我看见一只熊。');
  S.textStream.drop();
  const turns = el('history-messages').children;
  assert.equal(turns.length, 1, 'the typing bubble gave its place to the answer');
  assert.deepEqual(words(turns[0]), ['画画伙伴', '我看见一只熊。', '它要去哪里？'], 'the question is part of the turn');
  assert.equal(turns[0].className, 'course-message');
  assert.equal(el('history-count').textContent, '3 条对话');
});

test('a reply that settles marks the words it answered as answered, so they are not offered to send again', () => {
  // Found on the Spark: the column now stays up while it reloads, and the
  // chat panel read the child's still-pending words as a round the partner never answered.
  const { S, el } = setup();
  S.courseHistory.showSaid('a', '它们在一起跳舞');
  S.textStream.partial('art-feedback', writing('它们在一起跳舞呀。'), { id: 'a' }, true);
  S.textStream.settle({ text: '它们在一起跳舞呀。', question: '' });
  assert.equal(el('history-messages').querySelectorAll('.said-pending').length, 0);
  assert.equal(el('history-messages').children.length, 2, 'the words themselves stay');
});

test('a stop leaves the conversation as it was', () => {
  const { S, el } = setup();
  S.courseHistory.saved = 2;
  el('history-messages').appendChild(S.portfolio.text('article', '', 'course-message'));
  S.textStream.partial('art-feedback', writing('没检查过。', '新问题？'), { id: 'a' }, true);
  S.textStream.drop();
  assert.equal(el('history-messages').children.length, 1);
  assert.doesNotMatch(words(el('history-messages')).join(''), /没检查过|新问题/);
});

test('a teacher review is written into its own panel and a stop puts the saved one back', () => {
  const { S, el } = setup();
  el('teacher-review-text').dataset.key = 'a|saved review';
  S.textStream.partial('teacher-review', { text: '这幅画', writing: true }, { id: 'a' }, true);
  assert.equal(el('teacher-review-text').textContent, '这幅画');
  assert.equal(el('teacher-review-text').classList.contains('streaming'), true);
  assert.equal(el('history-messages').children.length, 0, 'a review is not a turn in the conversation');
  S.textStream.drop();
  assert.equal(el('teacher-review-text').classList.contains('streaming'), false);
  assert.equal(el('teacher-review-text').dataset.key, '', 'the panel is redrawn from the saved review');
});

test('a review arriving while the teacher is on another page is not written over what they see', () => {
  const { S, el } = setup();
  el('teacher-review-text').textContent = 'what is showing';
  S.textStream.partial('teacher-review', { text: '这幅画', writing: true }, { id: 'a' }, false);
  assert.equal(el('teacher-review-text').textContent, 'what is showing');
});

test('a scene or a story goes to the planner that asked for it', () => {
  const { S } = setup();
  const shown = [];
  S.creation = { owns: skill => skill === 'scene-description', preview: text => shown.push(text) };
  S.textStream.partial('scene-description', { text: '小熊在跳舞。', writing: true }, { id: 'a' }, true);
  S.textStream.drop();
  assert.deepEqual(shown, ['小熊在跳舞。', '']);
});

test('a settled turn stays on screen while the saved conversation loads, then the saved copy takes its place', async () => {
  const { S, el } = setup();
  S.courseHistory.drawn = 'a';
  let answer; S.portfolio.api = () => new Promise(resolve => { answer = resolve; });
  S.textStream.partial('art-feedback', writing('我看见一只熊。'), { id: 'a' }, true);
  S.textStream.settle({ text: '我看见一只熊。', question: '' });
  const loading = S.courseHistory.refresh();
  assert.deepEqual(words(el('history-messages').children[0]).slice(1), ['我看见一只熊。'], 'nothing vanishes while it loads');
  answer({ activities: [{ skill: 'art-feedback', drawings: ['a'], summary: { kind: 'text', text: '我看见一只熊。' } }] });
  await loading;
  assert.equal(el('history-messages').children.length, 1, 'replaced, not doubled');
});

test('any other redraw of the same drawing starts empty, so a cleared conversation does not linger', () => {
  const { S, el } = setup();
  S.courseHistory.drawn = 'a';
  el('history-messages').appendChild(S.portfolio.text('article', '', 'course-message'));
  S.portfolio.api = () => new Promise(() => {});
  S.courseHistory.refresh();
  assert.equal(el('history-messages').children.length, 0);
});
