// The child's turn on screen: shown when it is sent, and kept when the round fails.
//
// Measured in one class: a typed answer took 113 s to appear,
// because the column is drawn from the saved course and the page only redrew it
// after the whole reply had been written. The third answer never appeared at
// all — it is in the course database, but the round it belonged to was
// cancelled, so nothing ever redrew the column.
import test from 'node:test';
import assert from 'node:assert/strict';
import { loadStudio } from './load.mjs';

function setup() {
  class Element {
    children = []; hidden = false; textContent = ''; type = '';
    appendChild(e) { this.children.push(e); return e; }
    replaceChildren(...kids) { this.children = kids; }
    querySelectorAll() { return []; }
    set innerHTML(_) { throw Error('Must use textContent'); }
  }
  const els = new Map(), el = id => { if (!els.has(id)) els.set(id, new Element()); return els.get(id); };
  const S = loadStudio({ files: ['src/24c-portfolio.js', 'src/26c-course-history.js'], globals: {
    document: { createElement: () => new Element(), getElementById: el }
  }});
  S.i18n.lang = 'zh';
  Object.assign(S.state, { session: 'editor', courseId: 'course', current: 'a', transport: { name: 'http' } });
  el('portfolio').hidden = true;
  return { S, H: S.courseHistory, el };
}

const opening = { id: '1', skill: 'art-feedback', drawings: ['a'], summary: { kind: 'text', text: '我看见了一只熊。', question: '他要去哪里？' } };
const words = { id: '2-words', skill: 'confirmed-words', drawings: ['a'], summary: { kind: 'text', text: '他要去上学。' } };
const reply = { id: '2', skill: 'art-feedback', drawings: ['a'], summary: { kind: 'text', text: '他要去上学呀。', beat: 'reply' } };
const course = activities => ({ id: 'course', drawings: [{ id: 'a', url: '/a' }], activities });

function labels(el) { return el('history-messages').children.map(x => x.children[0].textContent); }
function lines(el) { return el('history-messages').children.map(x => x.children[1].textContent); }

test('the words a teacher sends are on screen before the studio has answered', () => {
  const { S, H, el } = setup();
  S.portfolio.api = () => { throw Error('showing what was just sent asks the server for nothing'); };
  H.showSaid('a', '他要去上学。');
  assert.deepEqual(labels(el), ['孩子']);
  assert.deepEqual(lines(el), ['他要去上学。']);
});

test('the saved copy replaces the sent one instead of doubling it', async () => {
  const { S, H, el } = setup();
  H.showSaid('a', '他要去上学。');
  S.portfolio.api = async () => course([opening, words, reply]);
  await H.refresh();
  assert.deepEqual(lines(el), ['我看见了一只熊。', '他要去上学。', '他要去上学呀。']);
});

test('a round that never finishes still leaves the words the child said', async () => {
  const { S, H, el } = setup();
  H.showSaid('a', '会的。');
  S.portfolio.api = async () => course([opening]);
  await H.refresh();
  assert.deepEqual(lines(el), ['我看见了一只熊。', '会的。']);
  assert.deepEqual(labels(el), ['画画伙伴', '孩子']);
});

test('the same words sent again replace the unanswered copy instead of stacking under it', () => {
  const { H, el } = setup();
  const list = el('history-messages'), gone = [];
  const note = { classList: { contains: name => name === 'said-note' }, remove: () => gone.push('note') };
  const unanswered = { querySelector: () => ({ textContent: '听不懂，所以具体要怎么画' }), nextElementSibling: note,
                       remove: () => gone.push('words') };
  const other = { querySelector: () => ({ textContent: '会的。' }), nextElementSibling: null, remove: () => gone.push('other') };
  list.querySelectorAll = sel => (sel === '.said-unanswered' ? [other, unanswered] : []);
  H.showSaid('a', '听不懂，所以具体要怎么画');
  assert.deepEqual(gone, ['note', 'words'], 'only the copy of these words, with its note');
  assert.deepEqual(lines(el), ['听不懂，所以具体要怎么画']);
});

test('the words belong to their own drawing and do not follow the teacher to the next one', async () => {
  const { S, H, el } = setup();
  H.showSaid('a', '会的。');
  S.state.current = 'b';
  S.portfolio.api = async () => ({ id: 'course', drawings: [{ id: 'b', url: '/b' }], activities: [] });
  await H.refresh();
  const shown = el('history-messages').children.flatMap(item => (item.children || []).map(part => part.textContent).concat(item.textContent));
  assert.equal(shown.includes('会的。'), false);
});

test('sending a child\'s words announces them, so the column can show them at once', async () => {
  const said = [];
  const fetch = () => Promise.resolve({ ok: true, status: 200, json: () => Promise.resolve({ request_id: 'r1' }) });
  const S = loadStudio({ files: ['src/23-transport-http.js'], globals: { fetch, EventSource: class { addEventListener() {} close() {} } } });
  S.bus.on('said', payload => said.push(payload));
  S.transports.http.request('s1', 'art-feedback', ['a'], { transcript: '他要去上学。' }, () => {});
  // Field by field: this object is made inside the sandbox, so deepEqual sees a
  // different Object prototype and refuses two identical shapes.
  assert.equal(said.length, 1);
  assert.equal(said[0].drawing, 'a');
  assert.equal(said[0].text, '他要去上学。');
});

// Before the fix: a Send while the studio was down was told the child's words had been saved.
function sendWith(fetch, streamFails) {
  const order = [];
  const EventSource = class {
    addEventListener() {}
    close() {}
    set onerror(fn) { if (streamFails) Promise.resolve().then(fn); }
  };
  const S = loadStudio({ files: ['src/23-transport-http.js'], globals: { fetch, EventSource } });
  S.bus.on('unsent', () => order.push('unsent'));
  S.transports.http.request('s1', 'art-feedback', ['a'], { transcript: 'the river runs past the hut' },
    ev => order.push(ev.status + (ev.reason_code ? ':' + ev.reason_code : '')));
  return new Promise(resolve => setTimeout(() => resolve(order), 20));
}

test('words the studio never took are announced as unsent before the round is said to stop', async () => {
  const order = await sendWith(() => Promise.reject(new TypeError('Failed to fetch')));
  assert.deepEqual([...order], ['unsent', 'stopped:server_unreachable']);
});

test('words the studio took are not called unsent when only the answer stream is lost', async () => {
  const fetch = () => Promise.resolve({ ok: true, status: 200, json: () => Promise.resolve({ request_id: 'r1' }) });
  const order = await sendWith(fetch, true);
  assert.deepEqual([...order], ['submitted', 'stopped:connection_lost']);
});
