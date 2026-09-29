// While the companion writes and its words are checked, the page says so and shows none of
// them (operator: "like a real chat"). Measured on the Spark: an opening
// is written in about 5 s and its rule judges take 12-37 s more, so the wait is counted.
import test from 'node:test';
import assert from 'node:assert/strict';
import { loadStudio } from './load.mjs';

function setup() {
  class Element {
    children = []; hidden = false; className = ''; parent = null; text = '';
    get textContent() { return this.text; }
    set textContent(v) { this.text = v; this.children = []; }  // as the DOM does: text replaces children
    classList = { add() {}, remove() {}, toggle() {} };
    querySelector(sel) { return this.children.find(k => '.' + k.className === sel) || null; }
    appendChild(e) { e.parent = this; this.children.push(e); return e; }
    replaceChildren(...kids) { this.children = []; kids.forEach(k => this.appendChild(k)); }
    contains(e) { return this.children.includes(e); }
    remove() { if (this.parent) this.parent.children = this.parent.children.filter(x => x !== this); }
  }
  const els = new Map(), el = id => { if (!els.has(id)) els.set(id, new Element()); return els.get(id); };
  const S = loadStudio({ files: ['src/24c-portfolio.js', 'src/26-companion.js', 'src/26c-course-history.js'],
    globals: { document: { createElement: () => new Element(), getElementById: el } } });
  S.companion.els = { bubble: el('bubble'), say: el('btn-say') };
  let spoken = 0; S.voice.speak = () => { spoken++; };
  S.state.current = 'a';
  return { S, el, spoken: () => spoken };
}
const texts = node => node.children.map(k => k.children.length ? texts(k) : k.textContent).flat();

test('while words are checked the bubble counts the wait and shows none of them, and nothing is spoken', () => {
  const { S, el, spoken } = setup();
  S.companion.checking({ drawing: 'a' }, Date.now() - 12000);
  assert.match(el('bubble').textContent, /检查/); assert.match(el('bubble').textContent, /12 秒/);
  assert.equal(el('history-messages').children.length, 0, 'the thread gets no draft');
  assert.equal(spoken(), 0, 'nothing the rules have not passed is read aloud');
});

test('while words are written the bubble says so', () => {
  const { S, el } = setup();
  S.companion.checking({ drawing: 'a', writing: true }, Date.now());
  assert.match(el('bubble').textContent, /正在写/);
});

test('the checked words replace the waiting line', () => {
  const { S, el } = setup();
  S.companion.checking({ drawing: 'a' }, Date.now());
  S.companion.say('检查过的话');
  assert.equal(el('bubble').textContent, '检查过的话');
});

test('work on another drawing does not show beside this one', () => {
  const { S, el } = setup();
  S.companion.say('这幅画的话');
  S.companion.checking({ drawing: 'b' }, Date.now());
  assert.equal(el('bubble').textContent, '这幅画的话');
});

test('ending a request keeps the checked words', () => {
  const { S, el } = setup();
  S.companion.checking({ drawing: 'a' }, Date.now());
  S.companion.say('检查过的话');
  S.companion.dropDraft();
  assert.equal(el('bubble').textContent, '检查过的话');
});
