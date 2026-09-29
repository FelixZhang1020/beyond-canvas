import test from 'node:test';
import assert from 'node:assert/strict';
import { encodeWav } from '../../studio/voice_lab/audio.mjs';
import { QuestionVoice } from '../../studio/voice_lab/question-voice.mjs';

test('reference PCM retains 24 kHz, clamps clipping, and never encodes NaN as speech', async () => {
  const wav = encodeWav(Float32Array.of(2, -2, .5, NaN));
  const view = new DataView(await wav.arrayBuffer());
  assert.equal(view.getUint32(24, true), 24000);
  assert.equal(view.getUint16(22, true), 1);
  assert.equal(view.getInt16(44, true), 32767);
  assert.equal(view.getInt16(46, true), -32768);
  assert.equal(view.getInt16(48, true), 16383);
  assert.equal(view.getInt16(50, true), 0);
  assert.equal(view.getUint32(40, true), 8);
});

function playbackFixture(load) {
  const audio = { src: '', hidden: true, plays: 0, pauses: 0,
    pause() { this.pauses++; }, play() { this.plays++; return Promise.resolve(); },
    removeAttribute() { this.src = ''; }, load() {} };
  const updates = [], released = [];
  const voice = new QuestionVoice(audio, load, update => updates.push(update), {
    createObjectURL: () => 'blob:test', revokeObjectURL: url => released.push(url),
  });
  return { voice, audio, updates, released };
}

test('replay uses the cached blob and clearing releases audio and cache', async () => {
  let calls = 0;
  const f = playbackFixture(async () => { calls++; return new Blob(['audio']); });
  await f.voice.play(0); await f.voice.play(0);
  assert.equal(calls, 1); assert.equal(f.audio.plays, 2);
  f.voice.clear();
  assert.equal(f.audio.src, ''); assert.equal(f.audio.hidden, true);
  assert.equal(f.voice.cache.size, 0); assert.equal(f.released.length, 2);
  await f.voice.play(0);
  assert.equal(calls, 2);
});

test('a stopped request cannot speak over recording, but can later be replayed', async () => {
  let resolve;
  const f = playbackFixture(() => new Promise(done => { resolve = done; }));
  const pending = f.voice.play(0);
  f.voice.stop(); resolve(new Blob(['audio'])); await pending;
  assert.equal(f.audio.plays, 0); assert.equal(f.audio.src, '');
  await f.voice.play(0);
  assert.equal(f.audio.plays, 1);
});

test('audio from an ended conversation never replaces the next conversation', async () => {
  let first;
  let calls = 0;
  const f = playbackFixture(() => ++calls === 1 ? new Promise(done => { first = done; }) : Promise.resolve(new Blob(['new'])));
  const pending = f.voice.play(0); f.voice.clear();
  await f.voice.play(0);
  first(new Blob(['old'])); await pending;
  assert.equal(f.audio.plays, 1);
});

test('failed synthesis is visible with no automatic retry; explicit retry can succeed', async () => {
  let calls = 0;
  const f = playbackFixture(async () => {
    if (++calls === 1) throw new Error('Step temporarily unavailable');
    return new Blob(['audio']);
  });
  await f.voice.play(0);
  assert.equal(calls, 1); assert.equal(f.audio.plays, 0);
  assert.equal(f.updates.at(-1).failed, true);
  await f.voice.play(0);
  assert.equal(calls, 2); assert.equal(f.audio.plays, 1);
});

test('autoplay refusal leaves a visible native player and reuses audio on retry', async () => {
  let calls = 0;
  const f = playbackFixture(async () => { calls++; return new Blob(['audio']); });
  f.audio.play = async () => { throw new Error('NotAllowedError'); };
  await f.voice.play(0);
  assert.equal(f.audio.hidden, false); assert.equal(f.audio.src, 'blob:test');
  assert.match(f.updates.at(-1).text, /点击播放器/);
  await f.voice.play(0); assert.equal(calls, 1);
});

test('switching voices synthesizes each voice once for the same question', async () => {
  const calls = [];
  const f = playbackFixture(async (questionId, voiceId) => {
    calls.push([questionId, voiceId]); return new Blob([voiceId]);
  });
  await f.voice.play(0, 'female', '女声');
  await f.voice.play(0, 'male', '男声');
  await f.voice.play(0, 'female', '女声');
  await f.voice.play(0, 'male', '男声');
  assert.deepEqual(calls, [[0, 'female'], [0, 'male']]);
  assert.equal(f.audio.plays, 4);
});

test('a late previous voice cannot start playing after switching voices', async () => {
  let finishFemale;
  const f = playbackFixture((_, voice) => voice === 'female'
    ? new Promise(resolve => { finishFemale = resolve; })
    : Promise.resolve(new Blob(['male'])));
  const female = f.voice.play(0, 'female');
  await f.voice.play(0, 'male');
  finishFemale(new Blob(['female'])); await female;
  assert.equal(f.audio.plays, 1);
  await f.voice.play(0, 'female');
  assert.equal(f.audio.plays, 2);
});
