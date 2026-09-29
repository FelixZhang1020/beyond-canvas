import test from 'node:test';
import assert from 'node:assert/strict';
import { loadStudio } from './load.mjs';

function setup(saved = []) {
  const elements = new Map();
  function el(id) {
    if (!elements.has(id)) elements.set(id, { hidden: true, textContent: '', value: '', events: {}, classes: new Set(),
      classList: { toggle(name, on) { const c = elements.get(id).classes; on ? c.add(name) : c.delete(name); },
                   remove(name) { elements.get(id).classes.delete(name); } },
      addEventListener(name, fn) { this.events[name] = fn; } });
    return elements.get(id);
  }
  const storage = new Map(saved);
  const S = loadStudio({ files: ['src/26-companion.js', 'src/26b-classroom-voice.js'], globals: {
    document: { getElementById: el }, localStorage: { getItem: k => storage.get(k), setItem: (k, v) => storage.set(k, v) }
  } });
  class Player {
    constructor(audio, load, update) { Object.assign(this, { audio, load, update }); this.cache = new Map(); }
    stop() { this.update({ stopped: true }); this.update({ streaming: false }); this.stops = (this.stops || 0) + 1; }
    clearSource() { this.audio.hidden = true; }
    clear() { this.stop(); this.cache.clear(); }
    play(text, voice) { this.stop(); return this.load(text, voice, { signal: 'signal' }); }
  }
  S.StreamingQuestionVoice = Player;
  S.voice.init();
  const calls = [];
  Object.assign(S.state, { session: 'first', transport: { name: 'http', speak: (...args) => { calls.push(args); return Promise.resolve({}); } } });
  S.voice.configure({ speech: { available: true } });
  return { S, calls, el };
}

test('classroom uses its own session and selected local voice; completion waits for playback', async () => {
  const { S, calls, el } = setup();
  let completed = 0;
  await S.voice.speak('The bird flies.', { onend: () => completed++ });
  assert.deepEqual(calls[0].slice(0, 3), ['first', 'The bird flies.', 'gentle-female']);
  assert.equal(completed, 0, 'internal stop transitions must not finish a book page');
  S.voice.player.update({ streaming: false, ended: true, text: 'complete' });
  assert.equal(completed, 1);
  el('f-voice').value = 'gentle-male'; el('f-voice').events.change();
  await S.voice.speak('Again');
  assert.equal(calls[1][2], 'gentle-male');
});

test('switching drawings stops speech and ending clears all class audio', async () => {
  const { S } = setup();
  S.voice.player.cache.set('old', 'recording');
  const before = S.voice.player.stops || 0;
  S.bus.emit('current', { id: 'next' });
  assert.ok(S.voice.player.stops > before);
  S.bus.emit('ended');
  assert.equal(S.voice.player.cache.size, 0);
});

test('ready, blocked and failed speech do not report successful narration',async()=>{
  const {S}=setup();let completed=0,failed=0;
  for(const state of [{streaming:false,text:'ready'},{blocked:true},{failed:true}]) {
    await S.voice.speak('Story',{onend:()=>completed++,onerror:()=>failed++});
    S.voice.player.update(state);
  }
  assert.equal(completed,0);assert.equal(failed,3);
});

test('when the browser blocks playing, the chat shows its Play again, and hides it once the line plays', async () => {
  const { S, el } = setup();
  await S.voice.speak('Story');
  S.voice.player.update({ blocked: true });
  assert.equal(el('classroom-voice').classes.has('voice-manual'), true, 'Play is the only way to hear it');
  el('classroom-audio').events.play();
  assert.equal(el('classroom-voice').classes.has('voice-manual'), false);
  S.voice.player.update({ firstPlaySeconds: 0.4 });
  assert.equal(el('classroom-voice').classes.has('voice-manual'), false);
});

test('manual playback waits for the audio to end before continuing the conversation', async () => {
  const { S, calls, el } = setup();
  S.voice.playAll(['First', 'Second']);
  el('classroom-audio').hidden = false;
  S.voice.player.update({ streaming: false, text: 'ready' });
  assert.equal(calls.length, 1, 'a ready clip has not been heard yet');
  assert.equal(el('voice-status').textContent, S.i18n.t('voice.tapPlay'));
  el('classroom-audio').events.play();
  assert.equal(el('voice-status').textContent, S.i18n.t('voice.playing'));
  el('classroom-audio').events.ended();
  assert.equal(calls.length, 2, 'the next part starts only after the first is heard');
});

test('missing backend voice stays explicit and never requests speech', async () => {
  const { S, calls, el } = setup();
  S.voice.configure({ speech: { available: false } });
  S.voice.speak('Hi');
  assert.equal(calls.length, 0);
  assert.equal(el('voice-status').textContent, S.i18n.t('voice.unavailable'));
});

test("a child's voice is asked for again each time, never replayed from what the page kept", async () => {
  // Before the fix: after an answer was taken back and said again in another voice, the book played the old reading.
  const { S, calls } = setup();
  await S.voice.speak('Hello.', {});   // the first line of a class starts the page's memory afresh
  S.voice.player.cache.set(JSON.stringify(['Page one.', 'child:fish']), 'the voice taken back');
  S.voice.player.cache.set(JSON.stringify(['Page one.', 'soft-child']), 'the studio voice');
  await S.voice.speak('Page one.', { voice: 'child:fish' });
  assert.deepEqual(calls.at(-1).slice(1, 3), ['Page one.', 'child:fish'], 'asked of the studio');
  assert.equal(S.voice.player.cache.has(JSON.stringify(['Page one.', 'child:fish'])), false);
  assert.equal(S.voice.player.cache.has(JSON.stringify(['Page one.', 'soft-child'])), true, 'other voices keep theirs');
});

test('an archived book can speak without opening a new classroom, with isolated cache', async () => {
  const { S, calls } = setup();
  const history = [];
  S.portfolio = { speak: (...args) => { history.push(args); return Promise.resolve({}); } };
  S.state.session = null;
  S.voice.player.cache.set('live-clip', 'old');
  await S.voice.speak('The saved ending.', { courseId: 'saved-class' });
  assert.equal(calls.length, 0);
  assert.deepEqual(history[0].slice(0, 3), ['saved-class', 'The saved ending.', 'gentle-female']);
  assert.equal(S.voice.player.cache.size, 0);
  S.state.session = 'new-class';
  await S.voice.speak('A new question.');
  assert.equal(calls[0][0], 'new-class');
  assert.equal(S.voice.courseId, null);
});

test('whole conversation advances only after playback and stops on cancellation or error', async () => {
  const { S, calls } = setup();
  S.voice.playAll(['First question', 'Child answer', 'Last reply']);
  assert.equal(calls.length, 1);
  S.voice.player.update({ ended: true });
  assert.equal(calls[1][1], 'Child answer');
  const late = S.voice.onend;
  S.voice.stop(); late();
  assert.equal(calls.length, 2);
  S.voice.playAll(['Retry', 'Must not play']);
  S.voice.player.update({ failed: true });
  assert.equal(calls.length, 3);
});

test('description narration uses the child preset without changing companion preferences', async () => {
  const { S, calls } = setup([['beyond-canvas.companion-voice-v3', 'gentle-male']]);
  S.voice.playAll(['First', 'Second'], { voice: 'soft-child' });
  assert.equal(calls[0][2], 'soft-child');
  S.voice.player.update({ ended: true });
  assert.equal(calls[1][2], 'soft-child');
  await S.voice.speak('Companion');
  assert.equal(calls[2][2], 'gentle-male');
});


test('old child preference does not override the adult companion default', async () => {
  const { S, calls, el } = setup([['beyond-canvas.companion-voice-v2', 'soft-child']]);
  assert.equal(el('f-voice').value, 'gentle-female');
  await S.voice.speak('A companion response');
  assert.equal(calls[0][2], 'gentle-female');
});

test('long narration starts with a short Unicode-safe passage and shows preparation progress', () => {
  const { S, calls, el } = setup();
  const text = '小象🐘在散步。'.repeat(20);
  S.voice.playAll([text]);
  assert.ok(Array.from(calls[0][1]).length <= 60);
  assert.ok(!calls[0][1].includes('\uFFFD'));
  S.voice.player.update({ loading: true, preparedSeconds: 2.56 });
  assert.ok(el('voice-status').textContent.includes('2.6'));
});


test('continuous dialogue switches adult-child-adult without reading role labels and stop cancels the rest', () => {
  const { S, calls } = setup();
  S.voice.playAll([{text:'Question?',voice:'gentle-female'},{text:'My answer.',voice:'soft-child'},{text:'Response.',voice:'gentle-female'}]);
  assert.deepEqual(calls[0].slice(1,3), ['Question?', 'gentle-female']);
  S.voice.player.update({ended:true});
  assert.deepEqual(calls[1].slice(1,3), ['My answer.', 'soft-child']);
  S.voice.player.update({ended:true});
  assert.deepEqual(calls[2].slice(1,3), ['Response.', 'gentle-female']);
  S.voice.stop(); S.voice.player.update({ended:true});
  assert.equal(calls.length,3);
});

test('stop control appears during preparation and playback, then hides after stop or completion', () => {
  const { S, el } = setup();
  const stop = el('voice-stop');
  assert.equal(stop.hidden, true);
  S.voice.player.update({ loading: true });
  assert.equal(stop.hidden, false);
  S.voice.stop();
  assert.equal(stop.hidden, true);
  el('classroom-audio').events.play();
  assert.equal(stop.hidden, false);
  el('classroom-audio').events.ended();
  assert.equal(stop.hidden, true);
  S.voice.player.update({ loading: true });
  S.voice.player.update({ failed: true });
  assert.equal(stop.hidden, true);
});


test('all classroom narration uses incremental playback instead of waiting for the full clip', () => {
  const { S } = setup();
  assert.equal(S.voice.player.bufferedPlayback, false);
});
