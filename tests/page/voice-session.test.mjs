import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import vm from 'node:vm';

const source = fs.readFileSync(new URL('../../studio/voice_lab/app.js', import.meta.url), 'utf8')
  .replace(/^import .*;\n/gm, '');
const deferred = () => { let resolve; const promise = new Promise(r => { resolve = r; }); return { promise, resolve }; };

function fixture() {
  const nodes = new Map(), requests = [], recorders = [], conversion = deferred(), microphone = deferred();
  const node = id => {
    if (!nodes.has(id)) nodes.set(id, { value: '', textContent: '', style: {}, dataset: {}, hidden: false,
      classList: {add() {}, remove() {}, toggle() {}}, listeners: {},
      addEventListener(name, fn) { this.listeners[name] = fn; },
      removeAttribute() {}, setAttribute() {}, replaceChildren() {}, append() {}, pause() {}, load() {} });
    return nodes.get(id);
  };
  class Recorder {
    constructor() { this.released = false; recorders.push(this); }
    start() { return microphone.promise; }
    stop() { return conversion.promise; }
    release() { this.released = true; }
  }
  class Voice { stop() {} clear() {} clearSource() {} }
  const context = vm.createContext({
    Blob, URL: {createObjectURL: () => 'blob:test', revokeObjectURL() {}}, console,
    Recorder, QuestionVoice: Voice, StreamingQuestionVoice: Voice, toWav: () => conversion.promise,
    document: {getElementById: node, querySelectorAll: () => [], createElement: () => node(Symbol())},
    window: {addEventListener() {}}, navigator: {}, setInterval: () => 1, clearInterval() {},
    setTimeout: () => 1, clearTimeout() {},
    fetch: async (url, options) => {
      if (url === '/api/status') return new Promise(() => {});
      requests.push({url, session: options.headers['X-Lab-Session'], body: options.body});
      return {ok: true, json: async () => ({id: 'sample', transcript: '测试', reference_text: '测试',
        quality: {seconds: 6, reason: '清晰'}, asr_s: 0}), blob: async () => new Blob(['audio'])};
    },
  });
  vm.runInContext(source + '\nglobalThis.lab = {state, acceptRecording, toggleRecord};', context);
  const lab = context.lab;
  Object.assign(lab.state, {session: 'old-session', epoch: 1});
  return {lab, nodes, requests, recorders, conversion, microphone};
}

test('a recording converted after a session switch is never uploaded into the new session', async () => {
  const f = fixture(); f.lab.state.recording = true;
  const pending = f.lab.toggleRecord();
  Object.assign(f.lab.state, {epoch: 2, session: 'new-session', busy: false});
  f.conversion.resolve(new Blob(['old recording'])); await pending;
  assert.equal(f.requests.length, 0);
  assert.equal(f.lab.state.busy, false);
  assert.equal(f.lab.state.draft, null);
});

test('an imported recording converted after ending also makes no upload request', async () => {
  const f = fixture();
  const pending = f.nodes.get('audio-file').listeners.change({target: {files: [new Blob(['old file'])]}});
  Object.assign(f.lab.state, {epoch: 2, session: '', busy: false});
  f.conversion.resolve(new Blob(['converted'])); await pending;
  assert.equal(f.requests.length, 0);
  assert.equal(f.lab.state.busy, false);
});

test('a current recording is uploaded and its reference is shown in the same session', async () => {
  const f = fixture(), audio = new Blob(['current recording']);
  await f.lab.acceptRecording(audio, 1);
  assert.equal(f.requests.length, 2);
  assert.equal(f.requests[0].body, audio);
  assert.ok(f.requests.every(r => r.session === 'old-session'));
  assert.equal(f.lab.state.draft.id, 'sample');
  assert.equal(f.nodes.get('draft').hidden, false);
});

test('a late microphone start releases only its old recorder, leaving the new attempt usable', async () => {
  const f = fixture();
  const first = f.lab.toggleRecord();
  Object.assign(f.lab.state, {epoch: 2, session: 'new-session', busy: false});
  const second = f.lab.toggleRecord();
  f.microphone.resolve(); await Promise.all([first, second]);
  assert.equal(f.recorders.at(-1).released, false);
  assert.equal(f.lab.state.recording, true);
});

test('a final recorder event after release cannot restore cleared audio chunks', async () => {
  const audioSource = fs.readFileSync(new URL('../../studio/voice_lab/audio.mjs', import.meta.url), 'utf8')
    .replace(/^export /gm, '');
  let media;
  class MediaRecorder {
    constructor() { media = this; this.listeners = {}; this.state = 'inactive'; }
    addEventListener(name, fn) { this.listeners[name] = fn; }
    start() { this.state = 'recording'; }
    stop() { this.state = 'inactive'; }
  }
  class AudioContext {
    state = 'running';
    createMediaStreamSource() { return {connect() {}}; }
    createAnalyser() { return {}; }
    close() { this.state = 'closed'; return Promise.resolve(); }
  }
  const Recorder = vm.runInNewContext(audioSource + '\nRecorder;', {
    MediaRecorder, window: {MediaRecorder, AudioContext},
    navigator: {mediaDevices: {getUserMedia: async () => ({getTracks: () => [{stop() {}}]})}},
    setInterval: () => 1, clearInterval() {},
  });
  const recorder = new Recorder(); await recorder.start(() => {});
  media.listeners.dataavailable({data: new Blob(['current audio'])});
  assert.equal(recorder.chunks.length, 1);
  recorder.release();
  media.listeners.dataavailable({data: new Blob(['late final audio'])});
  assert.equal(recorder.chunks.length, 0);
});
