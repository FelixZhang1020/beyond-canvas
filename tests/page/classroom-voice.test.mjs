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
  const storage = new Map(saved), session = { type: 'auto' };   // Safari's W3C Audio Session
  const S = loadStudio({ files: ['src/26-companion.js', 'src/26b-classroom-voice.js'], globals: {
    document: { getElementById: el }, localStorage: { getItem: k => storage.get(k), setItem: (k, v) => storage.set(k, v) },
    navigator: { audioSession: session }
  } });
  class Player {
    constructor(audio, load, update) { Object.assign(this, { audio, load, update }); this.cache = new Map(); }
    stop() { this.update({ stopped: true }); this.update({ streaming: false }); this.stops = (this.stops || 0) + 1; }
    clearSource() { this.audio.hidden = true; }
    clear() { this.stop(); this.cache.clear(); }
    play(text, voice) { this.stop(); return this.load(text, voice, { signal: 'signal' }); }
    prepare(text, voice, opts) { (this.prepared ||= []).push([text, voice, opts]); }
  }
  S.StreamingQuestionVoice = Player;
  S.voice.init();
  const calls = [];
  Object.assign(S.state, { session: 'first', transport: { name: 'http', speak: (...args) => { calls.push(args); return Promise.resolve({}); } } });
  S.voice.configure({ speech: { available: true } });
  return { S, calls, el, session };
}

test('speaking says the page plays media, so an iPhone in silent mode is heard, but never while recording', async () => {
  // Operator: no voice on an iPhone with the ring switch off. Safari mutes the web's sound unless it plays media.
  const { S, session } = setup();
  S.voice.unlock();
  assert.equal(session.type, 'playback', 'from the tap that starts a reading');
  session.type = 'auto'; S.listen = { on: true };
  await S.voice.speak('The bird flies.', {});
  assert.equal(session.type, 'auto', 'the microphone is left to the browser while it records');
  S.listen.on = false;
  await S.voice.speak('The bird flies.', {});
  assert.equal(session.type, 'playback');
});

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
  S.voice.player.cache.set(JSON.stringify(['Answer.', 'child-words:fish']), 'the answer taken back');
  await S.voice.speak('Answer.', { voice: 'child-words:fish' });
  assert.equal(S.voice.player.cache.has(JSON.stringify(['Answer.', 'child-words:fish'])), false, "the chat's playback too");
});

test('an archived book can speak without opening a new classroom, and what is ready stays ready', async () => {
  const { S, calls } = setup();
  const history = [];
  S.portfolio = { speak: (...args) => { history.push(args); return Promise.resolve({}); } };
  S.state.session = null;
  S.voice.player.cache.set('live-clip', 'old');
  await S.voice.speak('The saved ending.', { courseId: 'saved-class' });
  assert.equal(calls.length, 0);
  assert.deepEqual(history[0].slice(0, 3), ['saved-class', 'The saved ending.', 'gentle-female']);
  // Operator: no pause before a line prepared ahead. Switching classes used to throw it away, and close the player.
  assert.equal(S.voice.player.cache.size, 1, 'the same words in the same voice are the same sound in any class');
  S.state.session = 'new-class';
  await S.voice.speak('A new question.');
  assert.equal(calls[0][0], 'new-class');
  assert.equal(S.voice.courseId, null);
});

test('whole conversation advances only after playback and stops on cancellation or error', async () => {
  const { S, calls } = setup();
  S.voice.playAll(['First question', 'Child answer', 'Last reply']);
  assert.equal(calls.length, 1);
  // Operator: no pause between lines. The next one is fetched while this one plays.
  const plain = value => JSON.parse(JSON.stringify(value));   // the page's objects are another realm's
  assert.deepEqual(plain(S.voice.player.prepared), [['Child answer', 'gentle-female', { courseId: null, keep: true }]]);
  S.voice.player.update({ ended: true });
  assert.equal(calls[1][1], 'Child answer');
  assert.equal(S.voice.player.prepared.at(-1)[0], 'Last reply');
  S.voice.prepareStart([{ text: 'Your fish is blue.', voice: 'child-words:d1' }], { courseId: 'c1' });
  assert.deepEqual(plain(S.voice.player.prepared.at(-1)), ['Your fish is blue.', 'child-words:d1', { courseId: 'c1', keep: false }],
    "a child's voice is made ahead on the studio only");
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
