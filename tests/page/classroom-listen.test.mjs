import test from 'node:test';
import assert from 'node:assert/strict';
import { loadStudio } from './load.mjs';

function setup() {
  const pending = [], tracks = [], session = { type: 'playback' };   // as a reading left it (26b-classroom-voice.js)
  class Recorder {
    constructor(stream, options) { this.stream = stream; this.options = options; this.events = {}; this.state = 'inactive'; }
    addEventListener(name, fn) { this.events[name] = fn; }
    start() { this.state = 'recording'; }
    stop() { this.state = 'inactive'; queueMicrotask(() => this.events.stop?.()); }
  }
  const S = loadStudio({ files: ['src/27b-listen.js'], globals: { navigator: { mediaDevices: {
    getUserMedia: () => new Promise(resolve => pending.push(() => {
      const track = { stopped: 0, stop() { this.stopped++; } }; tracks.push(track);
      resolve({ getTracks: () => [track] });
    })) }, audioSession: session }, MediaRecorder: Recorder, Blob, queueMicrotask } });
  return { S, pending, tracks, session };
}

test('recording hands the audio session back to the browser, which then handles the microphone itself', () => {
  // A page that says it plays media loses Safari's own microphone handling (W3C Audio Session).
  const { S, session } = setup();
  S.listen.start();
  assert.equal(session.type, 'auto', 'before the microphone is asked for');
  S.listen.release();
});

test('a late microphone permission cannot take over a newer classroom recording', async () => {
  const { S, pending, tracks } = setup();
  const old = S.listen.start(); S.listen.release();
  const current = S.listen.start(); pending[1](); await current;
  const recorder = S.listen.recorder;
  pending[0](); assert.equal(await old, false);
  assert.equal(S.listen.recorder, recorder);
  assert.equal(tracks[0].stopped, 0);
  assert.equal(tracks[1].stopped, 1);
  S.listen.release(); assert.equal(tracks[0].stopped, 1);
});

test('discarding a recording during stop cannot release or transcribe a newer one', async () => {
  const { S, pending, tracks } = setup();
  const started = S.listen.start(); pending[0](); await started;
  S.listen.chunks.push(new Blob(['audio']));
  let decoded = 0; S.listen.toWav = async blob => { decoded++; return blob; };
  const stopped = S.listen.stop();
  const next = S.listen.start(); pending[1](); await next;
  assert.equal(await stopped, null);
  assert.equal(decoded, 0);
  assert.equal(S.listen.on, true);
  assert.equal(tracks[1].stopped, 0);
  S.listen.release();
});

// The microphone buttons live in 29i-microphones.js since 30-main.js was split.
function microphones({ busy = false, changing = false, elements = {}, listen = {}, transport = {} } = {}) {
  const toasts = [];
  const S = loadStudio({ files: ['src/29i-microphones.js'], globals: { document: { getElementById: id => elements[id]() }, Event } });
  Object.assign(S.state, { busy, session: 's1', current: 'd1', transport });
  S.main = { changing: () => changing, toast: key => toasts.push(key) };
  S.listen = Object.assign({ release() {} }, listen); S.voice = {};
  S.i18n.t = key => key;
  return { S, toasts };
}

test('generation and course switching block recording before requesting a microphone', () => {
  for (const [busy, changing] of [[true, false], [false, true], [false, false]]) {
    let lookups = 0;
    const entered = () => { lookups++; throw new Error('entered recording UI'); };
    const { S } = microphones({ busy, changing, elements: { 'btn-listen': entered } });
    if (busy || changing) { S.microphones.toggle(); assert.equal(lookups, 0); }
    else { assert.throws(() => S.microphones.toggle(), /entered recording UI/); assert.equal(lookups, 1); }
  }
});

test('a recording the studio could not turn into words is not blamed on the microphone', async () => {
  // Before the fix: every transcription in a class failed and the page said the device had no
  // microphone, though it had just recorded with one. A failed transcription asks again instead.
  const field = { value: '', focus() {} };
  const button = { disabled: false, firstChild: { dataset: {} }, classList: { add() {}, remove() {} } };
  const { S, toasts } = microphones({ elements: { 'btn-listen': () => button, 'heard-text': () => field },
    listen: { on: true, stop: async () => ({ size: 1 }) }, transport: { hear: async () => ({ text: '', listening: false }) } });
  await S.microphones.toggle();
  assert.deepEqual(toasts, ['listen.nothing']);
  assert.equal(button.disabled, false);
});

test('a spoken answer remembers its recording for the drawing it was said about, and a file never does', async () => {
  // The first answer said out loud about a drawing reads its storybook page in the child's voice.
  const field = { value: '', focus() {} }, sent = [];
  const form = { dispatchEvent: event => { sent.push([event.type, field.value, { ...S.state.heardSample }]); return false; } };
  const button = { disabled: false, firstChild: { dataset: {} }, classList: { add() {}, remove() {} },
    querySelector: () => ({ dataset: {} }) };
  const { S } = microphones({ elements: { 'btn-listen': () => button, 'heard-text': () => field, 'btn-said-file': () => button,
    'ending-listen': () => button, heard: () => form },
    listen: { on: true, stop: async () => ({ size: 1 }), fromFile: async file => file },
    transport: { hear: async () => ({ text: 'the fish swim home', sample: 'held-1' }) } });
  S.state.feedback.d1 = { text: 'The fish swim in a line.' };   // the companion has opened this drawing
  await S.microphones.toggle();
  assert.equal(field.value, 'the fish swim home');
  // Operator: what was said goes into the conversation at once, through the chat's own Send, recording and all.
  assert.deepEqual(sent, [['submit', 'the fish swim home', { drawing: 'd1', id: 'held-1' }]]);
  await S.microphones.fromFile({ name: 'before-class.wav' });
  assert.equal(S.state.heardSample, null, "a recording the teacher adds is not the child's voice for the book");
  assert.equal(sent.length, 1, 'what was heard in a file waits in the field for the teacher');
});

test('words said before the companion has opened the drawing wait in the field, and the stop tap readies the reply', async () => {
  // Review: sent at once, they reached the studio before its opening, which refused them in front of the child.
  const field = { value: '', focused: 0, focus() { this.focused++; } }, sent = [];
  const button = { disabled: false, firstChild: { dataset: {} }, classList: { add() {}, remove() {} } };
  const { S } = microphones({ elements: { 'btn-listen': () => button, 'heard-text': () => field,
    heard: () => ({ dispatchEvent: event => sent.push(event.type) }) },
    listen: { on: true, stop: async () => ({ size: 1 }) }, transport: { hear: async () => ({ text: 'a red house' }) } });
  let unlocked = 0; S.voice = { unlock() { unlocked++; } };
  const stopping = S.microphones.toggle();
  assert.equal(unlocked, 1, "within the tap: the reply is spoken after no tap of its own (iPad Safari)");
  await stopping;
  assert.equal(field.value, 'a red house');
  assert.deepEqual(sent, [], 'nothing goes to the studio before the opening');
  assert.equal(field.focused, 1);
});

test('the record button of the ending writes into its label, and what was heard lands in the ending box', async () => {
  // Before the fix: the label was a text node, the page threw, and a recorded ending never reached the studio.
  const label = { textContent: '', dataset: {} }, field = { value: '', focus() {} };
  const button = { disabled: false, firstChild: label, querySelector: () => label, classList: { add() {}, remove() {} } };
  const saidFile = { disabled: false };
  const { S } = microphones({ elements: { 'ending-listen': () => button, 'ending-text': () => field, 'btn-listen': () => button, 'btn-said-file': () => saidFile },
    listen: { on: false, start: async () => true }, transport: { hear: async () => ({ text: 'They shared the cheese.' }) } });
  await S.microphones.ending();
  assert.equal(label.dataset.t, 'listen.stop');
  S.listen.on = true; S.listen.stop = async () => ({ size: 1 });
  await S.microphones.ending();
  assert.equal(field.value, 'They shared the cheese.');
});

// The wait between Stop and the words used to be mostly sending a WAV eight times the size.
test('the browser is asked to record at speech rate, so what it sends is small', async () => {
  const { S, pending } = setup();
  const started = S.listen.start(); pending[0](); await started;
  assert.equal(S.listen.recorder.options.audioBitsPerSecond, 24000);
  S.listen.release();
});

test('a WebM or Ogg recording goes as the browser made it, and anything else is still unpacked here', async () => {
  const { S } = setup();
  let unpacked = 0; S.listen.toWav = async blob => { unpacked++; return blob; };
  for (const type of ['audio/webm;codecs=opus', 'audio/ogg;codecs=opus']) {
    const blob = new Blob(['x'], { type });
    assert.equal(await S.listen.sendable(blob), blob);
  }
  assert.equal(unpacked, 0);
  await S.listen.sendable(new Blob(['x'], { type: 'audio/mp4' }));
  assert.equal(unpacked, 1, 'Safari records MP4, which the studio cannot read from a pipe');
});

test('sending a recording says so while it is on its way, names it by what it is, and says when it is back', async () => {
  const sent = [], told = [];
  const fetch = (url, opts) => { sent.push(opts.body.get('audio').name); told.push('asked');
    return Promise.resolve({ ok: true, status: 200, json: () => Promise.resolve({ text: 'hi' }) }); };
  const S = loadStudio({ files: ['src/23-transport-http.js'], globals: { fetch, FormData, Blob } });
  S.bus.on('hearing', ({ on }) => told.push(on ? 'on' : 'off'));
  await S.transports.http.hear('s1', new Blob(['x'], { type: 'audio/webm;codecs=opus' }));
  await S.transports.http.hear('s1', new Blob(['x'], { type: 'audio/wav' }));
  assert.deepEqual([...sent], ['said.webm', 'said.wav']);
  assert.deepEqual([...told], ['on', 'asked', 'off', 'on', 'asked', 'off']);
});

test('a hearing that fails still says it is over', async () => {
  const told = [];
  const S = loadStudio({ files: ['src/23-transport-http.js'], globals: { fetch: () => Promise.reject(new TypeError('offline')), FormData, Blob } });
  S.bus.on('hearing', ({ on }) => told.push(on));
  await S.transports.http.hear('s1', new Blob(['x'])).catch(() => {});
  assert.deepEqual([...told], [true, false]);
});

test('a recording the studio cannot unpack is unpacked here and sent once more, not blamed on the child', async () => {
  const sent = [];
  const answers = [
    { ok: false, status: 400, json: () => Promise.resolve({ code: 'unreadable_audio' }) },
    { ok: true, status: 200, json: () => Promise.resolve({ text: 'the bear goes fishing' }) },
  ];
  const fetch = (url, opts) => { sent.push(opts.body.get('audio').name); return Promise.resolve(answers.shift()); };
  const S = loadStudio({ files: ['src/27b-listen.js', 'src/23-transport-http.js'], globals: { fetch, FormData, Blob } });
  S.listen.toWav = async () => new Blob(['wav'], { type: 'audio/wav' });
  const heard = await S.transports.http.hear('s1', new Blob(['x'], { type: 'audio/webm;codecs=opus' }));
  assert.equal(heard.text, 'the bear goes fishing');
  assert.deepEqual([...sent], ['said.webm', 'said.wav']);
});

test('a WAV the studio cannot read is not sent again, since there is nothing left to unpack', async () => {
  let asked = 0;
  const fetch = () => { asked++; return Promise.resolve({ ok: false, status: 400, json: () => Promise.resolve({ code: 'unreadable_audio' }) }); };
  const S = loadStudio({ files: ['src/27b-listen.js', 'src/23-transport-http.js'], globals: { fetch, FormData, Blob } });
  await assert.rejects(S.transports.http.hear('s1', new Blob(['x'], { type: 'audio/wav' })));
  assert.equal(asked, 1);
});

