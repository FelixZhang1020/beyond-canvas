// The conversation panel while the partner thinks, and after a round it did not answer.
// Found driving the page on the Spark: the big Stop button appeared where Record
// had been the moment Send was pressed, so a teacher reaching for Record stopped the reply; and
// after a stop the note said to send again over an empty field.
import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { loadStudio } from './load.mjs';

function panel() {
  const els = {}, observers = [], clicks = [], notes = [];
  const make = id => ({
    id, hidden: false, value: '', textContent: '', style: {}, scrollHeight: 40, scrollTop: 0,
    classes: new Set(), children: [],
    classList: { contains(c) { return els[id].classes.has(c); }, add(c) { els[id].classes.add(c); } },
    addEventListener(name, fn) { els[id]['on' + name] = fn; },
    click() { clicks.push(id); },
    querySelector() { return els[id].pending || null; },
    querySelectorAll() { return els[id].bridges || []; },
  });
  const el = id => (els[id] = els[id] || make(id));
  el('course-history').hidden = false;
  el('chat-stop').hidden = true;  // as the page ships it
  const S = loadStudio({
    files: ['src/26d-chat-panel.js'],
    globals: {
      document: { getElementById: el, createElement: () => { const note = { after() {} }; notes.push(note); return note; } },
      MutationObserver: class { constructor(fn) { observers.push(fn); } observe() {} },
      setTimeout: fn => fn(), setInterval: () => 0, clearInterval() {},
    },
  });
  S.state.mode = 'feedback';
  const think = on => { on ? el('splat').classes.add('thinking') : el('splat').classes.delete('thinking'); observers[1](); };
  globalThis.observers = observers;
  return { S, els, el, think, clicks, notes };
}

test('while the partner thinks, Stop is offered in the conversation and nowhere near Record', () => {
  const { S, el, think, clicks } = panel();
  think(true); S.state.busy = true;
  assert.equal(el('chat-stop').hidden, false);
  el('chat-stop').onclick();
  assert.deepEqual(clicks, ['btn-primary'], 'the same stop as the big button');
  think(false); S.state.busy = false;
  assert.equal(el('chat-stop').hidden, true);
  el('chat-stop').onclick();
  assert.deepEqual(clicks, ['btn-primary'], 'a late press does not start a new round');
});

test('Stop is scrolled into sight when it appears, even on a short scrolling thread', () => {
  const { el, think } = panel();
  Object.assign(el('buddy-dialogue'), { scrollTop: 41, scrollHeight: 357, clientHeight: 41 });
  think(true);
  assert.equal(el('buddy-dialogue').scrollTop, 357);
});

test('the conversation stop is not offered outside a conversation', () => {
  const { S, el, think } = panel();
  S.state.mode = 'teacher'; think(true);
  assert.equal(el('chat-stop').hidden, true);
});

test('a round the partner did not answer puts the child words back in the field', () => {
  const { el, think } = panel();
  const words = { classes: new Set(['said-pending']), classList: { add() {} }, after() {}, querySelector: () => ({ textContent: 'the bear goes fishing' }) };
  el('history-messages').pending = words;
  think(true); think(false);
  assert.equal(el('heard-text').value, 'the bear goes fishing');
});

test('a stopped round takes its quick echo with it, so it does not read as an answer', () => {
  const { el, think } = panel();
  const removed = [];
  el('history-messages').pending = { classList: { add() {} }, after() {}, querySelector: () => ({ textContent: 'the bear goes fishing' }) };
  el('history-messages').bridges = [{ remove: () => removed.push('echo') }];
  think(true); think(false);
  assert.deepEqual(removed, ['echo']);
});

test('words the studio never accepted are not called saved (a Send while it was down)', () => {
  const { S, el, think, notes } = panel();
  el('history-messages').pending = { classList: { add() {} }, after() {}, querySelector: () => ({ textContent: 'the river runs past the hut' }) };
  think(true); S.bus.emit('unsent', { drawing: 'd1' }); think(false);
  assert.equal(notes[0].textContent, '这次没有发出去，可以再发一次。');
  assert.doesNotMatch(notes[0].textContent, /记下/, 'nothing was saved, so the note must not say so');
});

test('words the studio accepted keep the note that says they were saved, even after an earlier failed send', () => {
  const { S, el, think, notes } = panel();
  S.bus.emit('unsent', { drawing: 'd1' });  // left over from an earlier round
  el('history-messages').pending = { classList: { add() {} }, after() {}, querySelector: () => ({ textContent: 'the bear goes fishing' }) };
  think(true); think(false);
  assert.equal(notes[0].textContent, '伙伴这次没有回答。孩子的话已经记下，可以再发一次。');
});

test('while a recording becomes words, the empty box says so, and asks again once they are back', () => {
  const { S, el } = panel();
  Object.assign(el('heard-text'), { dataset: {}, placeholder: '孩子说了什么？' });
  S.bus.emit('hearing', { on: true });
  assert.equal(el('heard-text').placeholder, '正在把孩子的话变成文字…');
  S.bus.emit('hearing', { on: false });
  assert.equal(el('heard-text').placeholder, '孩子说了什么？');
  S.bus.emit('hearing', { on: false });
  assert.equal(el('heard-text').placeholder, '孩子说了什么？', 'a second end changes nothing');
});

test('two recordings on their way at once keep the box saying so until both are back, on the story page too', () => {
  const { S, el } = panel();
  Object.assign(el('heard-text'), { dataset: {}, placeholder: '孩子说了什么？' });
  Object.assign(el('ending-text'), { dataset: {}, placeholder: '然后呢？' });
  S.bus.emit('hearing', { on: true }); S.bus.emit('hearing', { on: true });
  S.bus.emit('hearing', { on: false });
  assert.equal(el('heard-text').placeholder, '正在把孩子的话变成文字…', 'one is still on its way');
  assert.equal(el('ending-text').placeholder, '正在把孩子的话变成文字…');
  S.bus.emit('hearing', { on: false });
  assert.equal(el('heard-text').placeholder, '孩子说了什么？');
  assert.equal(el('ending-text').placeholder, '然后呢？');
});

test('words the teacher already started typing are not overwritten', () => {
  const { el, think } = panel();
  el('history-messages').pending = { classList: { add() {} }, after() {}, querySelector: () => ({ textContent: 'old words' }) };
  el('heard-text').value = 'new words';
  think(true); think(false);
  assert.equal(el('heard-text').value, 'new words');
});

test('the big button stays out of a thinking conversation, so the answer row cannot move', () => {
  const css = readFileSync(new URL('../../studio/page/src/04b-chat-panel.css', import.meta.url), 'utf8');
  assert.match(css, /#buddy:has\(#chat-stop:not\(\[hidden\]\)\) #buddy-actions\{display:none\}/);
  assert.match(css, /#app:has\(#splat\.thinking\) #buddy \.heard-gate\{display:none\}/);
});

test('switching tabs mid-task moves Stop with the teacher (review)', () => {
  const { S, el, think } = panel();
  S.state.busy = true; think(true);
  assert.equal(el('chat-stop').hidden, false, 'in the conversation while it thinks');
  S.state.mode = 'move'; observers[2]();
  assert.equal(el('chat-stop').hidden, true, 'not left in a conversation the teacher has left');
  S.state.mode = 'feedback'; observers[2]();
  assert.equal(el('chat-stop').hidden, false, 'and back when the teacher returns to it');
});
