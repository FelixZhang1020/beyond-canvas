import test from 'node:test';
import assert from 'node:assert';
import { readFileSync, readdirSync } from 'node:fs';
import { loadStudio } from './load.mjs';

test('every text box starts empty, so the example written into it can show', () => {
  // A browser shows a placeholder only while a box is empty, and whitespace between the
  // tags counts as content. The lesson line held ten spaces from the start, so a teacher
  // never saw its example, including the subject-first one added later.
  const source = readFileSync(new URL('../../studio/page/src/10-app.html', import.meta.url), 'utf8');
  const boxes = Array.from(source.matchAll(/<textarea\b[^>]*\bid="([^"]+)"[^>]*>([\s\S]*?)<\/textarea>/g));
  // A box the pattern cannot read, with no id or an unusual attribute, must not pass unseen.
  assert.equal(boxes.length, source.match(/<textarea\b/g).length);
  for (const [, id, content] of boxes) assert.equal(content, '', id);
});

test('Chinese is the only language, and an unknown key returns itself', () => {
  const S = loadStudio();
  assert.equal(S.i18n.t('mode.feedback'), '聊聊你的画');
  assert.equal(S.i18n.t('mode.pose'), '让画动起来');
  assert.equal(S.i18n.t('mode.book'), '做本故事书');
  assert.equal(S.i18n.t('no.such.key'), 'no.such.key');
});

test('nothing can put the studio into another language', () => {
  // A CN/EN switch used to sit in the bar. Teachers pressed it by
  // accident and then could not read the studio well enough to put it back, so
  // the operator had both the switch and the English table removed. What this
  // holds is that neither can come back by halves: no second table, and no way
  // to select one even if a table appeared.
  const S = loadStudio();
  assert.equal(S.i18n.lang, 'zh');
  assert.equal(S.strings.en, undefined, 'an English table is back');
  assert.equal(typeof S.i18n.set, 'undefined', 'the language can be changed again');
  assert.deepEqual(Object.keys(S.strings), ['zh']);
});

test('placeholders are filled in the Chinese wording', () => {
  const S = loadStudio();
  assert.equal(S.i18n.t('count', { n: 3 }), '今天 3 幅画');
  assert.equal(S.i18n.t('book.page', { i: 2, n: 5 }), '第 2 页，共 5 页');
});

test('every label the page asks for has Chinese, since nothing falls back now', () => {
  // This is what the English table used to do by accident: a key with no
  // Chinese showed English rather than showing as a bare key. With English
  // gone, the only thing standing between a missing string and a teacher
  // reading "sheet.begin" on a button is this.
  const S = loadStudio();
  const sources = readdirSync(new URL('../../studio/page/src/', import.meta.url))
    .filter((name) => name.endsWith('.js'));
  const asked = new Set();
  for (const name of sources) {
    const code = readFileSync(new URL(`../../studio/page/src/${name}`, import.meta.url), 'utf8');
    // The literal must be the whole argument: `t('status.gate_' + gate)` is a
    // prefix being built, not a key, and asking for it would always fail.
    for (const hit of code.matchAll(/\bt\(\s*'([\w.-]+)'\s*[,)]/g)) asked.add(hit[1]);
  }
  assert.ok(asked.size > 100, `only ${asked.size} keys found; the search stopped working`);
  const known = Object.keys(S.strings.zh);
  const missing = [...asked].filter((key) => {
    if (S.strings.zh[key] !== undefined) return false;
    // Some modules keep their own t() that adds a prefix, as the Portfolio does
    // with portfolio.emptyTitle and portfolio.result.book. A name counts when
    // one of those exists under a prefix.
    return !known.some((k) => k.endsWith('.' + key));
  });
  assert.deepEqual(missing, [], 'these would show as bare keys on screen');
});

test('the class sheet offers the two entrances and no suggestion switch', () => {
  const S = loadStudio();
  assert.equal(S.i18n.t('entrance.colour'), '彩画');
  assert.equal(S.i18n.t('entrance.sketch'), '素描');
  for (const key of Object.keys(S.strings.zh)) assert.ok(!key.startsWith('sheet.suggest'), key);
});

test('nothing a teacher reads is in English except the names we keep', () => {
  // The switch and the English table went, but English kept
  // turning up in places the sweep missed: three labels a script writes, which
  // sat in the markup in English until boot, and twenty-one spoken labels that
  // only a screen reader ever hears. This reads the built page the way a person
  // meets it -- element text, placeholders, titles, spoken labels -- and allows
  // only names that have no Chinese form.
  const NAMES = new Set([
    'Beyond', 'Canvas',                       // the studio's own name
    'TRELLIS', 'Wan', 'FLUX', 'StepFun', 'Step', 'Astra', 'GPT', 'Whisper', 'VoxCPM',
    'Nemotron', 'NVIDIA', 'DGX', 'Spark',     // models, makers and machines
    'Splat',                                  // the companion's name
    'GPU', 'JSON', 'token', 'tokens', 'USD',  // terms kept English, by decision
    'Agentic', 'Skills',                      // the showpiece's entrance, named by the operator
  ]);
  const page = readFileSync(new URL('../../studio/page/index.html', import.meta.url), 'utf8');
  const markup = page.slice(0, page.indexOf('<script>'));
  const read = [];
  for (const hit of markup.matchAll(/>([^<>{}]{2,120})</g)) read.push(hit[1].trim());
  for (const attr of ['placeholder', 'aria-label', 'title', 'alt']) {
    for (const hit of markup.matchAll(new RegExp(`${attr}="([^"]{2,120})"`, 'g'))) read.push(hit[1].trim());
  }
  assert.ok(read.length > 200, `only ${read.length} strings read; the search stopped working`);
  const english = new Set();
  for (const line of read) {
    for (const word of line.match(/[A-Za-z][A-Za-z']{2,}/g) || []) {
      if (!NAMES.has(word)) english.add(`${word}  (in: ${line.slice(0, 60)})`);
    }
  }
  assert.deepEqual([...english], [], 'English a teacher would meet before any script runs');
});
