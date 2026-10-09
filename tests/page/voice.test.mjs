// The other half of the voice: what Splat sounds like when it reads a line out
// loud. No test could reach this module before, so the rules it keeps — never a
// novelty voice, never the wrong language, never two lines at once — were held
// only by having been written once.
import test from 'node:test';
import assert from 'node:assert';
import { loadStudio } from './load.mjs';

class Utterance {
  constructor(text) { this.text = text; }
}

function speech(names) {
  const state = { spoken: [], cancelled: 0 };
  const voices = names.map((n) => ({
    name: n.name, lang: n.lang, localService: n.local !== false,
  }));
  return {
    state,
    api: {
      getVoices: () => voices,
      speak: (u) => state.spoken.push(u),
      cancel: () => { state.cancelled += 1; },
      addEventListener: () => {},
    },
  };
}

function studio(names, lang) {
  const s = speech(names);
  const S = loadStudio({
    files: ['src/26-companion.js'],
    globals: { speechSynthesis: s.api, SpeechSynthesisUtterance: Utterance },
  });
  S.i18n.lang = lang || 'en';
  return { S, heard: s.state };
}

const TINGTING = { name: 'Tingting', lang: 'zh-CN' };
const MEIJIA = { name: 'Meijia', lang: 'zh_CN' };
const FLO = { name: 'Flo', lang: 'zh-CN' };
const SAMANTHA = { name: 'Samantha', lang: 'en-US' };

test('a novelty voice is never given to a child', () => {
  // macOS ships Flo, Grandpa, Bells and a dozen others. One of them reading a
  // five-year-old's story back is a joke at the child's expense.
  const { S } = studio([FLO, TINGTING]);
  assert.equal(S.voice.pick('zh').name, 'Tingting');
});

test('when every installed voice is a novelty, none is chosen at all', () => {
  const { S } = studio([FLO, { name: 'Grandpa', lang: 'zh-CN' }]);
  assert.equal(S.voice.pick('zh'), null, 'better the browser default than a joke voice');
});

test('the language decides the voice, and an underscore is still Chinese', () => {
  // Some platforms report zh_CN rather than zh-CN. A string comparison that
  // misses that hands a Chinese class an English voice.
  const { S } = studio([SAMANTHA, MEIJIA]);
  assert.equal(S.voice.pick('zh').name, 'Meijia');
  assert.equal(S.voice.pick('en').name, 'Samantha');
});

test('saying a line aloud speaks it in the language the studio is in', () => {
  const { S, heard } = studio([SAMANTHA, TINGTING], 'zh');
  const said = S.voice.speak('你好，给我看看画');
  assert.equal(heard.spoken.length, 1);
  assert.equal(said.lang, 'zh-CN');
  assert.equal(said.voice.name, 'Tingting');
  assert.equal(said.text, '你好，给我看看画');
});

test('a new line stops the one before it, so two never talk over each other', () => {
  const { S, heard } = studio([SAMANTHA], 'en');
  S.voice.speak('first');
  S.voice.speak('second');
  assert.equal(heard.cancelled, 2, 'each line cancels what was already speaking');
  assert.equal(heard.spoken.length, 2);
});

test('an empty line is not spoken', () => {
  const { S, heard } = studio([SAMANTHA], 'en');
  assert.equal(S.voice.speak(''), null);
  assert.equal(heard.spoken.length, 0);
});
