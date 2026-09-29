import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { gloss, reply } from '../../studio/showpiece/page/rebuild-gloss.mjs';
import { caught, prepare } from '../../studio/showpiece/page/rebuild-scenes.mjs';

const page = (name) => JSON.parse(readFileSync(new URL(`../../studio/showpiece/page/${name}`, import.meta.url), 'utf8'));
const words = page('rebuild-strings.json');
const t = (key, vars = {}) => (words[key] || key).replace(/\{(\w+)\}/g, (_, k) => String(vars[k] ?? ''));
const records = ['rebuild-record.json', 'rebuild-run1-record.json', 'rebuild-run2-record.json', 'rebuild-run3-record.json'].map(page);

test('every step of all four runs says what the harness answered, in words with nothing left unfilled', () => {
  for (const record of records) {
    for (const ch of prepare(record.steps)) {
      const said = reply(ch, record, t);
      assert.ok(said.text, `step ${ch.step}: nothing said`);
      assert.doesNotMatch(said.text, /\{\w+\}|^gloss\.|^param\./, `step ${ch.step}: ${said.text}`);
    }
  }
});

test('whatever the harness caught gets a plain line that reads as a stop, not only its English', () => {
  for (const record of records) {
    for (const ch of prepare(record.steps).filter(caught)) {
      const line = gloss(ch.evidence, t);
      assert.ok(line, `step ${ch.step}: no line for ${ch.evidence.slice(0, 80)}`);
      assert.equal(line.tone, 'bad', `step ${ch.step}`);
    }
  }
});

test('the refusals read the numbers the tool gave', () => {
  assert.equal(gloss('REFUSED spacing 0.05 is out of range; give between 0.2 and 5 metres', t).text, t('gloss.refused.spacing', { x: '0.05', a: '0.2', b: '5' }));
  assert.match(gloss("REFUSED thickness 0.0 is not a timber's size in metres; give between 0.02 and 5", t).text, new RegExp(t('param.thickness')));
});

test('a check call that errored leaves the gate as it was: it ran no check', async () => {
  const { makeHood } = await import('../../studio/showpiece/page/rebuild-hood.mjs');
  const record = page('rebuild-run1-record.json'), chapters = prepare(record.steps);
  const nodes = new Map(), $ = (id) => {
    if (!nodes.has(id)) nodes.set(id, { textContent: '', innerHTML: '', className: '', hidden: false, attrs: { class: 'x' },
      setAttribute(k, v) { this.attrs[k] = v; }, getAttribute(k) { return this.attrs[k]; } });
    return nodes.get(id);
  };
  const hood = makeHood({ $, t, record, chapters });
  const errored = chapters.findIndex((ch) => ch.tool === 'settle' && /error:/.test(ch.evidence));
  hood.show(errored);
  assert.doesNotMatch($('pill-settle').getAttribute('class'), /good/);
});

test('the bracket counts and heights on the page come from the model and the record, not from its words', () => {
  for (const key of ['bracket.count', 'bracket.all', 'bracket.whole', 'bracket.p6.detail', 'bracket.p7.detail']) {
    assert.doesNotMatch(words[key].replace(/\{\w+\}/g, ''), /\d/, key);
  }
});

test('the checks the design runs added read in one line each: past the eaves, an open roof, a part on an old one', () => {
  const eaves = gloss('not handed over yet: 148 timber pieces stand past the edge of the roof, with no covering over them: 48 bracket arms', t);
  assert.equal(eaves.tone, 'bad');
  assert.equal(eaves.text, t('gloss.eaves', { n: '148' }));
  const open = gloss('BRIEF x | the roof is open at the hips: 35.04 m2 where one covering sheet stands up to 0.97 m over another', t);
  assert.equal(open.tone, 'bad');
  const stale = gloss('PLACED frames: 44 pieces | lines 6 | the purlins, rafters and roof stand on the old frames: place them again, in that order, before checking', t);
  assert.equal(stale.text, t('gloss.stale', { n: '44', parts: [t('part.purlins'), t('part.rafters'), t('part.roof')].join(t('part.sep')), base: t('part.frames') }));
  assert.doesNotMatch(stale.text, /part\./, 'every part has its Chinese name');
});

test('a design found later with its roof open says so, not "one more way short of the brief"', async () => {
  const { laterFinding } = await import('../../studio/showpiece/page/rebuild-gloss.mjs');
  const said = laterFinding({ beyond_the_eaves: [], through_the_roof: [], later: { new_checks: ['open_roof'], short_of_the_brief: ['the roof is open at the hips: 35.04 m2'] } }, t);
  assert.equal(said, t('later.open'));
});
