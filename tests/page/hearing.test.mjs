// The format the listening model reads without help, and the second route to
// the child's voice.
//
// The measured record calls 16 kHz mono WAV "the one format every speech model
// reads without help" — the page encodes it itself precisely so the server does
// not have to shell out to ffmpeg, which is what took the whole listening path
// down. Nothing tested that encoder until now.
import test from 'node:test';
import assert from 'node:assert';
import { loadStudio } from './load.mjs';

// A Blob that keeps its bytes, which is all the encoder needs of one.
class Bytes {
  constructor(parts, options) {
    this.parts = parts;
    this.type = (options || {}).type || '';
    this.view = new DataView(parts[0].buffer !== undefined ? parts[0].buffer : parts[0]);
  }
}

function studio() {
  return loadStudio({ files: ['src/27b-listen.js'], globals: { Blob: Bytes, navigator: {} } });
}

function buffer(samples) {
  return { getChannelData: () => Float32Array.from(samples) };
}

function read(wav) {
  const v = wav.view;
  const text = (at, n) => String.fromCharCode(
    ...Array.from({ length: n }, (_, i) => v.getUint8(at + i)));
  return {
    riff: text(0, 4),
    wave: text(8, 4),
    format: v.getUint16(20, true),
    channels: v.getUint16(22, true),
    rate: v.getUint32(24, true),
    bits: v.getUint16(34, true),
    dataBytes: v.getUint32(40, true),
    sampleAt: (i) => v.getInt16(44 + i * 2, true),
  };
}

test('a recording leaves as 16 kHz mono 16-bit WAV, whatever went in', () => {
  const S = studio();
  const wav = read(S.listen.encodeWav(buffer([0, 0.5, -0.5, 0])));
  assert.equal(wav.riff, 'RIFF');
  assert.equal(wav.wave, 'WAVE');
  assert.equal(wav.format, 1, 'plain PCM: no codec for the model to guess at');
  assert.equal(wav.channels, 1);
  assert.equal(wav.rate, 16000);
  assert.equal(wav.bits, 16);
  assert.equal(wav.dataBytes, 8, 'four samples, two bytes each');
});

test('a loud child does not wrap around into a burst of noise', () => {
  // Clipping is the difference between a loud sentence and something the model
  // transcribes as nothing at all.
  const S = studio();
  const wav = read(S.listen.encodeWav(buffer([2, -2])));
  assert.equal(wav.sampleAt(0), 32767);
  assert.equal(wav.sampleAt(1), -32768);
});

test('silence encodes as silence rather than as an empty file', () => {
  const S = studio();
  const wav = read(S.listen.encodeWav(buffer([0, 0, 0])));
  assert.equal(wav.dataBytes, 6);
  assert.equal(wav.sampleAt(1), 0);
});

test('a recording made earlier can be brought in, by the same road as a live one', () => {
  // 3.2 names two routes to the child's voice: the teacher recorded it earlier,
  // or the studio drew it out on the spot. Only the second existed — the file
  // input accepted images alone.
  const S = studio();
  assert.equal(typeof S.listen.fromFile, 'function');
});

test('a file with no sound in it is refused with a reason, not a silent failure', async () => {
  const S = studio();
  await assert.rejects(() => S.listen.fromFile(null), /nothing to listen to/i);
});
