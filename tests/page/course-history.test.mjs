import test from 'node:test';
import assert from 'node:assert/strict';
import { loadStudio } from './load.mjs';

function setup() {
  class Element {
    children = []; hidden = false; textContent = '';
    appendChild(e) { this.children.push(e); return e; }
    replaceChildren(...kids) { this.children = kids; }
    querySelectorAll(selector) {
      return this.children.flatMap(child => [
        ...(selector === '.course-question' && child.className === 'course-question' ? [child] : []),
        ...child.querySelectorAll(selector)
      ]);
    }
    set innerHTML(_) { throw Error('Must use textContent'); }
  }
  const els = new Map(), el = id => { if (!els.has(id)) els.set(id, new Element()); return els.get(id); };
  const S = loadStudio({ files: ['src/24c-portfolio.js', 'src/26c-course-history.js'], globals: {
    document: { createElement: () => new Element(), getElementById: el }
  }});
  S.i18n.lang = 'zh';
  Object.assign(S.state, { session: 'editor', courseId: 'course', current: 'a', transport: {name:'http'} });
  el('portfolio').hidden = true;
  return { S, H: S.courseHistory, el };
}
function course() {
  return { id: 'course', drawings: [{id:'a',url:'/a'}, {id:'b',url:'/b'}], activities: [
    {id:'1', skill:'art-feedback', drawings:['a'], summary:{kind:'text',text:'First',question:'Question?'}},
    {id:'2', skill:'confirmed-words', drawings:['a'], summary:{kind:'text',text:'Answer'}},
    {id:'3', skill:'art-feedback', drawings:['a'], summary:{kind:'text',text:'Last'}},
    {id:'4', skill:'art-feedback', drawings:['b'], summary:{kind:'text',text:'Other drawing'}},
    {id:'mesh', skill:'sketch-to-3d', drawings:['b'], summary:{kind:'relight'}},
    {id:'book', skill:'drawings-to-storybook', drawings:['a','b'], summary:{kind:'book'}}
  ]};
}
test('reopened drawing shows dialogue only, with no creation buttons', async () => {
  const {S,H,el}=setup(); S.portfolio.api=async()=>course(); await H.refresh();
  const items=el('history-messages').children;
  assert.equal(items.length,3);
  assert.deepEqual(items.map(x=>x.children[0].textContent),['画画伙伴','孩子','画画伙伴']);
  assert.deepEqual(items.map(x=>x.children[1].textContent),['First','Answer','Last']);
  assert.equal(items[0].children[2].textContent,'Question?');
  assert.equal(el('history-results').children.length,0, 'another drawing\'s mesh must not appear');
  assert.equal(el('history-books').children.length,0);
  assert.equal(el('course-history').hidden,false);
});
test('switching drawings rejects an older response and ending clears history', async () => {
  const {S,H,el}=setup(); let resolve;
  S.portfolio.api=()=>new Promise(r=>resolve=r); const old=H.refresh();
  S.state.current='b'; S.portfolio.api=async()=>course(); await H.refresh();
  resolve(course());await old;
  assert.equal(el('history-messages').children.length,1);
  assert.equal(el('history-messages').children[0].children[1].textContent,'Other drawing');
  S.state.session=null;await H.refresh();assert.equal(el('course-history').hidden,true);
  assert.equal(el('history-messages').children.length,0);
});
test('failed dialogue loading can retry', async () => {
  const {S,H,el}=setup();S.portfolio.api=async()=>{throw Error('offline');};await H.refresh();
  assert.equal(el('history-retry').hidden,false);
  S.portfolio.api=async()=>course();await H.refresh();assert.equal(el('history-retry').hidden,true);
});
test('conversation playback includes every turn and question for this drawing only', async () => {
  const {S,H,el}=setup(); let played;
  S.voice={selected(){return 'gentle-female';},queueToken:0,stop(){this.queueToken++;},restore(){},unlock(){},playAll(texts,opts){played={texts,opts};}};
  S.portfolio.api=async()=>course(); await H.playConversation();
  assert.deepEqual(Array.from(played.texts, item => item.text),['First Question?','Answer','Last']);
  assert.equal(played.opts.courseId,'course');
  // Operator: the child's answer in the child's own voice; the studio says which, and falls back to its own.
  assert.deepEqual(Array.from(played.texts, item => item.voice), ['gentle-female','child-words:a','gentle-female']);
  let prepared; S.voice.prepareStart = (texts, opts) => { prepared = { texts, opts }; };
  await H.refresh(); el('history-messages').children[1].children.at(-1).onclick();
  assert.deepEqual(Array.from(played.texts, item => item.voice), ['child-words:a'], 'one turn played alone too');
  // Operator: no pause when Play is pressed. What it reads first is fetched as soon as the conversation is shown.
  assert.deepEqual(Array.from(prepared.texts, item => item.text), ['First Question?', 'Answer', 'Last']);
  assert.equal(prepared.opts.courseId, 'course');
  let resolve; played=null; S.portfolio.api=()=>new Promise(r=>resolve=r);
  const pending=H.playConversation(); S.voice.stop(); resolve(course()); await pending;
  assert.equal(played,null,'stop during loading prevents late playback');
});

test('every question stays in the companion\'s own turn: there is no card to move it to', async () => {
  const { S, H, el } = setup();
  const saved = course();
  saved.activities[2].summary.question = 'Next question?';
  S.portfolio.api = async () => saved;
  await H.refresh();
  const questions = el('history-messages').querySelectorAll('.course-question');
  assert.equal(questions.length, 2);
  assert.ok(questions.every(question => !question.hidden), 'the newest question is shown in the thread');
});

test('status records are excluded from displayed and spoken dialogue', async () => {
  const {S,H,el}=setup(); const saved=course(); let played;
  saved.activities.push({id:'status',skill:'art-feedback',drawings:['a'],summary:{kind:'text',status:'failed',message:'Technical status'}});
  S.portfolio.api=async()=>saved;
  S.voice={selected(){return 'gentle-female';},queueToken:0,stop(){this.queueToken++;},restore(){},unlock(){},playAll(texts){played=texts;}};
  await H.refresh(); await H.playConversation();
  assert.equal(el('history-messages').children.length,3);
  assert.deepEqual(Array.from(played, item => item.text),['First Question?','Answer','Last']);
});
