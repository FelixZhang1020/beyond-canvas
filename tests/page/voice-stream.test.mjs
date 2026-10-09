import test from 'node:test';
import assert from 'node:assert/strict';
import { StreamingQuestionVoice, voiceEvents } from '../../studio/voice_lab/stream-voice.mjs';

const format = { type: 'format', sample_rate: 16000 };
const pcm = { type: 'pcm', data: Buffer.alloc(16000 * 2 * .32, 12).toString('base64') };
const done = { type: 'done' };
const pack = event => new TextEncoder().encode(JSON.stringify(event) + '\n');

function fixture({ blocked = false, opening = [format, pcm] } = {}) {
  let controller, signal, calls = 0, notify;
  const started = new Promise(resolve => { notify = resolve; });
  const scheduled = [], updates = [];
  const context = {
    state: 'running', currentTime: 0, destination: {},
    resume() { if (blocked) return Promise.reject(new Error('gesture required')); return Promise.resolve(); },
    close() { this.state = 'closed'; return Promise.resolve(); },
    createBuffer(_channels, count, rate) { return { duration: count / rate, copyToChannel() {} }; },
    decoded: [],
    decodeAudioData(bytes) {
      this.decoded.push(new Uint8Array(bytes));
      if (bytes.byteLength < 4) return Promise.reject(new Error('not audio'));
      return Promise.resolve({ sampleRate: 48000, getChannelData: () => new Float32Array(48000 * 1.5) });
    },
    createBufferSource() { return { connect() {}, disconnect() {}, stop() { this.stopped = true; },
      start(at) { this.at = at; scheduled.push(this); notify(); } }; },
  };
  const audio = { hidden: true, plays: 0, pauses: 0, src: '',
    play() { this.plays++; return Promise.resolve(); }, pause() { this.pauses++; },
    removeAttribute() { this.src = ''; }, load() {} };
  const voice = new StreamingQuestionVoice(audio, async (_id, _voice, options) => {
    calls++; signal = options.signal;
    return new Response(new ReadableStream({ start(c) { controller = c; opening.forEach(event => c.enqueue(pack(event))); } }));
  }, update => updates.push(update), { createObjectURL: () => 'blob:completed', revokeObjectURL() {} }, () => context);
  return { voice, audio, context, scheduled, updates, started,
    send: event => controller.enqueue(pack(event)), end: () => controller.close(),
    get signal() { return signal; }, get calls() { return calls; } };
}

test('a line prepared ahead plays at once through Web Audio, with no second request', async () => {
  // Operator: "正在准备声音…" before every line of a conversation and after opening it.
  const f = fixture({ opening: [format, pcm, done] });
  const preparing = f.voice.prepare(7, 'female', { courseId: 'c1' });
  await new Promise(resolve => setTimeout(resolve)); f.end(); await preparing;
  assert.equal(f.calls, 1); assert.equal(f.voice.ready.size, 1);
  await f.voice.prepare(7, 'female');
  assert.equal(f.calls, 1, 'a line already prepared is not asked for again');
  await f.voice.play(7, 'female'); await f.started;
  assert.equal(f.calls, 1, 'played from what was prepared');
  assert.equal(f.scheduled.length, 1, 'through Web Audio, as a streamed line is');
  assert.equal(f.voice.ready.size, 0);
  const child = fixture({ opening: [format, pcm, done] });
  const warming = child.voice.prepare(8, 'child-words:d1', { keep: false });
  await new Promise(resolve => setTimeout(resolve)); child.end(); await warming;
  assert.equal(child.calls, 1); assert.equal(child.voice.ready.size, 0, "a child's voice is only made on the studio");
});

test('audio begins before the server finishes; full audio is cached only after done', async () => {
  const f = fixture(), playing = f.voice.play(0, 'female');
  await f.started;
  assert.equal(f.scheduled.length, 1);
  assert.equal(f.voice.cache.size, 0);
  assert.match(f.updates.at(-1).text, /起播等待/);
  f.send(pcm); f.send(done); f.end(); await playing;
  assert.equal(f.voice.cache.size, 1);
  assert.equal(f.audio.hidden, true, 'native replay stays hidden while stream is audible');
  assert.equal(f.audio.plays, 0); // Do not play the whole clip again over live chunks.
  assert.ok(f.scheduled[1].at >= f.scheduled[0].at + .32);
  assert.equal(f.updates.some(state => state.ended), false, 'download completion is not playback completion');
  f.scheduled[0].onended();
  assert.equal(f.updates.some(state => state.ended), false, 'all scheduled audio must finish');
  f.scheduled[1].onended();
  assert.equal(f.updates.at(-1).ended, true);
  assert.equal(f.audio.hidden, false);
  await f.voice.play(0, 'female');
  assert.equal(f.calls, 1); assert.equal(f.audio.plays, 1);
});

test('a heartbeat between events keeps a slow generation alive without affecting playback', async () => {
  const f = fixture(), playing = f.voice.play(0, 'female');
  await f.started;
  f.send({ type: 'heartbeat' }); f.send(pcm); f.send({ type: 'heartbeat' }); f.send(done); f.end(); await playing;
  assert.equal(f.updates.some(state => state.failed), false);
  assert.equal(f.voice.cache.size, 1);
});

test('stop cancels the request and every scheduled node; late data cannot play or cache', async () => {
  const f = fixture(), playing = f.voice.play(0, 'female');
  await f.started; f.voice.stop();
  assert.equal(f.signal.aborted, true);
  assert.ok(f.scheduled.every(source => source.stopped));
  f.send(pcm); f.send(done); f.end(); await playing;
  assert.equal(f.scheduled.length, 1); assert.equal(f.voice.cache.size, 0);
  assert.equal(f.audio.src, '');
});

test('a truncated or failed stream is visible and never cached as complete', async () => {
  for (const error of [false, true]) {
    const f = fixture(), playing = f.voice.play(0, 'female');
    await f.started;
    if (error) f.send({ type: 'error', error: '模型未完成，请重试。' });
    f.end(); await playing;
    assert.equal(f.voice.cache.size, 0);
    assert.equal(f.updates.at(-1).failed, true);
    assert.ok(f.scheduled.every(source => source.stopped));
  }
});

test('autoplay refusal collects a complete clip and leaves the native player available', async () => {
  const f = fixture({ blocked: true }), playing = f.voice.play(0, 'female');
  // Let load create the stream, without relying on actual audio playback.
  while (!f.signal) await Promise.resolve();
  f.send(done); f.end(); await playing;
  assert.equal(f.scheduled.length, 0); assert.equal(f.audio.hidden, false);
  assert.equal(f.voice.cache.size, 1); assert.match(f.updates.at(-1).text, /点击播放器/);
  assert.equal(f.updates.some(state => state.ended), false);
});

test('native replay can stop the streamed nodes without pausing the native player', async () => {
  const f = fixture(), playing = f.voice.play(0, 'female');
  await f.started; f.send(done); f.end(); await playing;
  const pauses = f.audio.pauses;
  f.voice.stopStream();
  assert.equal(f.audio.pauses, pauses);
  assert.ok(f.scheduled.every(source => source.stopped));
});

test('ending releases context and cache, and late source completion cannot change new status', async () => {
  const f = fixture(), playing = f.voice.play(0, 'female');
  await f.started; f.send(done); f.end(); await playing;
  f.voice.clear();
  assert.equal(f.context.state, 'closed'); assert.equal(f.voice.cache.size, 0);
  const last = f.updates.at(-1); f.scheduled[0].onended();
  assert.equal(f.updates.at(-1), last);
});

test('stream framing handles UTF-8 characters divided across network reads', async () => {
  const expected = { type: 'error', error: '声音中断，请重试。' }, bytes = pack(expected);
  const response = new Response(new ReadableStream({ start(c) {
    for (const byte of bytes) c.enqueue(Uint8Array.of(byte)); c.close();
  } }));
  const events = []; for await (const event of voiceEvents(response)) events.push(event);
  assert.deepEqual(events, [expected]);
});


test('classroom buffered mode has only native playback, so its progress controls the audible audio', async () => {
  const f = fixture(); f.voice.bufferedPlayback = true;
  const playing = f.voice.play('text', 'soft-child');
  await new Promise(resolve => setTimeout(resolve, 0));
  assert.equal(f.scheduled.length, 0);
  assert.equal(f.audio.plays, 0);
  f.send(done); f.end(); await playing;
  assert.equal(f.audio.plays, 1);
  assert.equal(f.audio.hidden, false);
  assert.equal(f.scheduled.length, 0);
  f.voice.stop();
  assert.ok(f.audio.pauses > 0);
});

test('stopping while the classroom prepares audio never starts a late native player', async () => {
  const f = fixture(); f.voice.bufferedPlayback = true;
  const playing = f.voice.play('text', 'soft-child');
  await new Promise(resolve => setTimeout(resolve, 0));
  f.voice.stop(); assert.equal(f.signal.aborted, true);
  f.send(done); f.end(); await playing;
  assert.equal(f.audio.plays, 0); assert.equal(f.scheduled.length, 0);
});

// Raw sound needs 64 KB a second and the relay to the classroom delivered 29, so the
// class heard speech in bursts. The class voice now sends each sentence whole, as MP3.
const mp3 = { type: 'mp3', data: Buffer.from('ID3 a whole sentence').toString('base64') };

test('an mp3 sentence is decoded whole, played at once, and kept for replay at its own rate', async () => {
  const f = fixture({ opening: [{ type: 'format', sample_rate: 24000 }, mp3] }), playing = f.voice.play(0, 'female');
  await f.started;
  assert.equal(f.context.decoded.length, 1);
  assert.equal(new TextDecoder().decode(f.context.decoded[0]), 'ID3 a whole sentence');
  assert.equal(f.scheduled.length, 1, 'a whole sentence starts at once, with no waiting for more');
  f.send(mp3); f.send(done); f.end(); await playing;
  assert.equal(f.scheduled.length, 2);
  assert.ok(f.scheduled[1].at >= f.scheduled[0].at + 1.5, 'the second sentence follows the first, not over it');
  assert.equal(f.voice.cache.size, 1, 'the whole reply is kept for replay');
  assert.equal(f.updates.some(state => state.failed), false);
});

test('an mp3 sentence that will not decode stops with a message rather than playing noise', async () => {
  const broken = { type: 'mp3', data: Buffer.from('no').toString('base64') };
  const f = fixture({ opening: [{ type: 'format', sample_rate: 24000 }, broken] });
  await f.voice.play(0, 'female');
  assert.equal(f.updates.at(-1).failed, true);
  assert.equal(f.voice.cache.size, 0);
});

test('a stream that mixes raw sound and mp3 is refused, not played at the wrong speed (review)', async () => {
  const f = fixture({ opening: [format, pcm, mp3] });
  await f.voice.play(0, 'female');
  assert.equal(f.updates.at(-1).failed, true);
  assert.equal(f.voice.cache.size, 0);
});
