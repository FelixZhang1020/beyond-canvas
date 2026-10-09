import test from 'node:test';
import assert from 'node:assert/strict';
import { existsSync, readFileSync } from 'node:fs';
import { filesOf, isDesign, listDesigns, whichRun } from '../../studio/showpiece/page/rebuild-runs.mjs';
import { caught, culpritNames, makeScenes, passedCheck, prepare, repairRounds, sceneOf } from '../../studio/showpiece/page/rebuild-scenes.mjs';
import { ending, gloss, reply } from '../../studio/showpiece/page/rebuild-gloss.mjs';
import { makeHood } from '../../studio/showpiece/page/rebuild-hood.mjs';
import { briefLine, compareRuns, resultOf } from '../../studio/showpiece/page/rebuild-compare.mjs';

const page = (name) => new URL(`../../studio/showpiece/page/${name}`, import.meta.url);
const load = (name) => JSON.parse(readFileSync(page(name), 'utf8'));
const words = load('rebuild-strings.json');
const t = (key, vars = {}) => (words[key] || key).replace(/\{(\w+)\}/g, (_, k) => String(vars[k] ?? ''));
const designs = load('rebuild-designs.json').designs;
const recordOf = (n) => load(`rebuild-design${n}-record.json`);
const MET = 'BRIEF 7 by 4 bays | corner columns [34.0, 17.7] m apart | 2 rings of columns | bracket sets 48% of the column'
  + ' | meets the brief | brief.png: the photograph above, the hall below';
const SHORT = MET.replace('meets the brief', 'does NOT meet the brief: 1 timber pieces stand out through the roof: Frame 3 | king post;'
  + ' a frame line under the sloping end of the roof is named in frames\' end-lines');

// A stand-in for the page's elements: what the hood writes into them is read back as text.
function elements() {
  const nodes = new Map();
  return (id) => {
    if (!nodes.has(id)) nodes.set(id, { textContent: '', innerHTML: '', className: '', hidden: false, attrs: { class: 'x' }, dataset: {},
      classList: { toggle() {} },
      setAttribute(k, v) { this.attrs[k] = v; }, getAttribute(k) { return this.attrs[k]; } });
    return nodes.get(id);
  };
}

test('?design=N plays the Nth design from its own files, and the four rebuilds keep theirs', () => {
  assert.equal(whichRun('?design=2'), 'design2');
  assert.deepEqual(filesOf(whichRun('?design=2')), { record: 'rebuild-design2-record.json', hall: 'rebuild-design2-hall' });
  assert.deepEqual([whichRun(''), whichRun('?run=2'), whichRun('?design=0'), whichRun('?design=two')], [4, 2, 4, 4]);
  assert.deepEqual([filesOf(4).record, filesOf(2).record], ['rebuild-record.json', 'rebuild-run2-record.json']);
  assert.ok(isDesign('design12') && !isDesign(4) && !isDesign('4'));
  for (const { n } of designs) {
    assert.ok(existsSync(page(filesOf(`design${n}`).record)), `design ${n} has no record`);
    assert.ok(existsSync(page(`${filesOf(`design${n}`).hall}.glb`)), `design ${n} has no hall`);
  }
});

test("a design's gate shows the brief check where a rebuild's shows likeness", () => {
  const pills = (record) => {
    const $ = elements();
    makeHood({ $, t, record, chapters: prepare(record.steps) }).build();
    return $('loop').innerHTML;
  };
  for (const { n } of designs) {
    const loop = pills(recordOf(n));
    assert.match(loop, /id="pill-brief"/, `design ${n}`);
    assert.ok(loop.includes(`>${t('pill.brief')}</text>`), `design ${n}: the pill reads ${t('pill.brief')}`);
    assert.doesNotMatch(loop, /pill-likeness/, `design ${n}`);
  }
  const rebuilt = pills(load('rebuild-record.json'));
  assert.match(rebuilt, /id="pill-likeness"/);
  assert.doesNotMatch(rebuilt, /pill-brief/);
});

test('the brief check reads as its own numbers, and a brief the hall does not meet is caught', () => {
  const met = gloss(MET, t), short = gloss(SHORT, t);
  assert.equal(met.tone, 'good');
  for (const number of ['7', '4', '34.0', '17.7', '48']) assert.ok(met.text.includes(number), `${number} in ${met.text}`);
  assert.equal(short.tone, 'bad');
  const check = (evidence) => prepare([{ step: 3, kind: 'act', tool: 'brief', frame: 'step-2', evidence }])[0];
  assert.ok(passedCheck(check(MET)) && !caught(check(MET)));
  assert.ok(caught(check(SHORT)) && !passedCheck(check(SHORT)));
  assert.equal(sceneOf(check(SHORT)), 'likeness', 'a failed brief paints its pieces as a failed likeness does');
  assert.deepEqual(culpritNames(SHORT), ['Frame 3 | king post']);
  assert.equal(briefLine({ bays: [7, 4], meets: true, current: true }, t), t('compare.brief.meets', { x: 7, y: 4 }));
  assert.equal(briefLine({ bays: [7, 4], meets: true, current: false }, t), t('compare.brief.none'), 'an earlier hall is not the one handed over');
});

test('every step of every design says what the harness answered, and every catch reads as a stop', () => {
  for (const { n } of designs) {
    const record = recordOf(n);
    for (const ch of prepare(record.steps)) {
      const said = reply(ch, record, t);
      assert.ok(said.text, `design ${n} step ${ch.step}: nothing said`);
      assert.doesNotMatch(said.text, /\{\w+\}|^gloss\.|^param\./, `design ${n} step ${ch.step}: ${said.text}`);
      assert.ok(ch.scene, `design ${n} step ${ch.step}: no picture`);
      if (caught(ch)) assert.equal(gloss(ch.evidence, t)?.tone, 'bad', `design ${n} step ${ch.step}: ${ch.evidence.slice(0, 80)}`);
    }
  }
});

test("a design's repair rounds are the laps its own scorecard counted, and a broken tool call changed nothing", () => {
  for (const { n } of designs) {
    const record = recordOf(n);
    assert.equal(Math.max(0, ...repairRounds(prepare(record.steps))), record.harness.turns.repair_laps, `design ${n}`);
  }
  const broken = prepare(recordOf(2).steps).filter((ch) => /^exit \d+:/.test(ch.evidence || ''));
  assert.deepEqual(broken.map((ch) => ch.step), [58, 64, 96], 'the bearing check broke three times on purlins the model had removed');
  for (const ch of broken) assert.ok(sceneOf(ch) === 'refused' && caught(ch), `step ${ch.step}`);
});

// A design handed over under the checks of its day, with what today's brief check found on its final hall.
function adopted(faults) {
  return { design: true, run: 9, measured: { adopted: true, wall_seconds: 60, tokens: 10, actions: 2 },
    harness: { limits: { laps: 6 }, still_owed: [], brief: { bays: [7, 4], span: [34, 17.7], column_rings: 2, meets: true, current: true,
      brackets: { of_column: 0.6 } } },
    faults: { fell: [], hanging: [], through_the_roof: [], beyond_the_eaves: [], found_later: false, ...faults },
    steps: [{ step: 2, kind: 'act', tool: 'platform', frame: 'step-2', evidence: 'PLACED platform: 1 pieces' },
      { step: 3, kind: 'act', tool: 'brief', frame: 'step-2', evidence: MET },
      { step: 4, kind: 'final', frame: 'step-2', evidence: 'The hall is designed.' }] };
}
const LATER = { on: 'step-2', checked: '2026-09-30', meets: false, new_checks: ['beyond_the_eaves'],
  short_of_the_brief: ['2 timber pieces stand past the edge of the roof, with no covering over them: 1 bracket arms, 1 outriggers'] };

// The last scene of a design, played on a stand-in hall that remembers which pieces were painted red.
function lastScene(record) {
  const pieces = [['Platform', 'stone'], ['Bracket 3 | tier 1 arm', 'brackets'], ['Bracket 3 | outrigger', 'brackets']];
  const red = [], $ = elements(), chapters = prepare(record.steps);
  const hall = { record: { pieces, stages: { 'step-2': [0, 1, 2] } }, finishEffects() {}, clearColour() {}, setStage() {}, look() {},
    hideFamilies() {}, mark(ids, rgb) { if (rgb[0] > .8 && rgb[1] < .2) red.push(...ids); } };
  makeScenes({ hall, t, $, protocol: {}, chapters, record }).enter(chapters.at(-1), chapters.length - 1);
  return { red, $ };
}

test('a design adopted by its day that a check added since fails is labelled adopted wrongly, its pieces red', () => {
  const record = adopted({ found_later: true, beyond_the_eaves: ['Bracket 3 | tier 1 arm', 'Bracket 3 | outrigger'], later: LATER });
  const { red, $ } = lastScene(record);
  assert.deepEqual(red, [1, 2], 'the pieces past the eaves are painted red on the final hall');
  assert.equal(resultOf(record), 'wrong');
  assert.equal(t(`result.${resultOf(record)}`), t('result.wrong'));
  assert.equal($('catch-title').textContent, t('catch.ended.wrong'));
  assert.ok($('catch-note').textContent.includes('beyond_the_eaves'), 'the note names the check that came later');
  assert.ok(!/\d{4}-\d{2}-\d{2}/.test($('catch-note').textContent), 'and shows no date (operator: no specific dates on the page)');
  assert.ok($('catch-note').textContent.includes(t('later.eaves', { n: 2 })), $('catch-note').textContent);
  assert.equal(ending(record.steps.at(-1), record, t).line.tone, 'bad');
});

test('a design that still meets the brief it was adopted under stays adopted, with nothing painted', () => {
  const record = adopted({ later: { ...LATER, meets: true, short_of_the_brief: [] } });
  const { red, $ } = lastScene(record);
  assert.deepEqual(red, []);
  assert.equal(resultOf(record), 'yes');
  assert.equal($('catch-title').textContent, t('catch.ended.yes'));
  assert.equal(ending(record.steps.at(-1), record, t).line.tone, 'good');
});

// Just enough of a page for the design list and its dressing to run as they do in the browser: elements
// with children, a class and data, found by tag or class; the document finds links by data-run and cards.
class Element {
  constructor(tag) { Object.assign(this, { tagName: tag.toUpperCase(), children: [], dataset: {}, textContent: '', className: '', hidden: false }); }
  append(...kids) { for (const kid of kids) this.children.push(typeof kid === 'string' ? Object.assign(new Element('#text'), { textContent: kid }) : kid); }
  all() { return this.children.flatMap((kid) => [kid, ...kid.all()]); }
  querySelector(sel) {
    return this.all().find((el) => (sel.startsWith('.') ? el.className.split(' ').includes(sel.slice(1)) : el.tagName === sel.toUpperCase())) || null;
  }
}

// The success path and the halls beside the real one as the page draws them from rebuild-designs.json, each
// dressed from its own record; `changed` stands in for records that say something else.
async function drawnPath(listed = load('rebuild-designs.json'), changed = {}) {
  const ids = new Map(), $ = (id) => ids.get(id) || ids.set(id, new Element('div')).get(id);
  const roots = ['design-runs', 'path-stages', 'design-cards'].map($);
  const find = (sel) => {
    const key = sel.match(/data-run="([^"]+)"/)?.[1];
    return roots.flatMap((root) => root.all()).filter((el) => (key ? el.tagName === 'A' && el.dataset.run === key : el.tagName === 'LI' && el.dataset.run));
  };
  globalThis.document = { createElement: (tag) => new Element(tag), querySelectorAll: find, querySelector: (sel) => find(sel)[0] || null };
  globalThis.fetch = async (name) => ({ ok: name in changed || existsSync(page(name)), json: async () => changed[name] ?? load(name) });
  listDesigns({ $, t, designs: listed.designs, path: listed.path });
  await compareRuns($, t);
  return { $, chips: $('path-stages').children.map((stage) => stage.all().filter((el) => el.className === 'chip')) };
}

test('the success path shows every design once, in run order, each chip reading its own record as its button does', async () => {
  const { $, chips } = await drawnPath();
  const all = chips.flat();
  assert.equal($('design-path').hidden, false);
  assert.deepEqual(all.map((chip) => chip.dataset.run), designs.map(({ n }) => `design${n}`), 'each design once, in run order');
  for (const chip of all) {
    const record = load(filesOf(chip.dataset.run).record), result = resultOf(record);
    assert.equal(chip.dataset.result, result, chip.dataset.run);
    assert.equal(chip.querySelector('em').textContent, t(`result.${result}`), chip.dataset.run);
    assert.equal(chip.href, `rebuild.html?design=${chip.dataset.run.slice('design'.length)}`);
  }
  const reads = (n) => all.find((chip) => chip.dataset.run === `design${n}`).querySelector('em').textContent;
  assert.deepEqual([4, 6, 9, 10].map(reads), ['result.wrong', 'result.wrong', 'result.yes', 'result.yes'].map((key) => t(key)));
});

test('every word on the success path is in the page strings, and the path ends at two clean adoptions', () => {
  const { path } = load('rebuild-designs.json');
  const keys = ['path.title', 'path.found.label', 'path.fixed.label', 'path.end.label', 'design.tab',
    ...path.flatMap((stage) => [stage.found, stage.fixed, stage.end].filter(Boolean))];
  for (const key of keys) assert.ok(words[key], `${key} has no words`);
  for (const stage of path.slice(0, -1)) assert.ok(stage.found && stage.fixed && !stage.end, `stage ${stage.runs} says what it found and fixed`);
  const last = path.at(-1);
  assert.ok(last.end && !last.fixed, 'the last stage is where the path ends');
  assert.ok(last.runs.every((n) => resultOf(recordOf(n)) === 'yes'), 'it ends on adopted runs with nothing found later');
});

// The five numbers as a reader would check them against a record: whole roof rings, metres to one decimal.
const metres = (v) => (v == null ? '–' : Number(v).toFixed(1));
const shown = (v) => ({ rings: v.roof_rings == null ? '–' : String(v.roof_rings), ridge: metres(v.ridge_m),
  eaves: v.eaves_m.map(metres).join(' / '), outline: v.outline_m.map(metres).join(' × '), top: metres(v.top_m) });
const beside = (design, real) => Object.keys(shown(real)).map((key) => t('versus.line', { what: t(`versus.${key}`), d: shown(design)[key], r: shown(real)[key] }));
const short = (design, real) => Object.keys(shown(real))
  .map((key) => t('versus.pair', { what: t(`versus.short.${key}`), d: shown(design)[key], r: shown(real)[key] })).join(' · ');
const cardRow = ($, n) => $('design-cards').children.find((card) => card.dataset.run === `design${n}`).all()
  .filter((el) => el.tagName === 'DIV').find((row) => row.children[0].textContent === t('compare.real'))?.children[1].textContent;

test('beside the real hall stand exactly the adopted designs, each hall with its own numbers and the real one\'s', async () => {
  const { $ } = await drawnPath();
  const real = load('rebuild-real-hall.json'), halls = $('versus-halls').children;
  const adopted = designs.map(({ n }) => recordOf(n)).filter((record) => resultOf(record) === 'yes');
  assert.ok(adopted.length >= 2 && $('design-versus').hidden === false);
  assert.deepEqual(halls.map((hall) => hall.querySelector('figcaption').textContent),
    [t('versus.real.caption'), ...adopted.map((record) => t('versus.design.caption', { n: record.run }))], 'the real hall, then each adopted design');
  assert.equal(halls[0].querySelector('img').src, 'rebuild-temple.jpg');
  assert.deepEqual(halls[0].querySelector('ul').children.map((li) => li.textContent),
    Object.entries(shown(real)).map(([key, v]) => t('versus.own', { what: t(`versus.${key}`), v })));
  adopted.forEach((record, i) => {
    const hall = halls[i + 1], picture = hall.querySelector('img').src;
    assert.deepEqual(hall.querySelector('ul').children.map((li) => li.textContent), beside(record.versus_real, real), `design ${record.run}`);
    assert.ok(/-brief\.jpg$/.test(picture) && existsSync(page(picture)), `design ${record.run}: ${picture}`);
    assert.equal($('design-cards').children.find((card) => card.dataset.run === `design${record.run}`).querySelector('span').textContent,
      t('design.card.adopted'), 'an adopted card says what adopted means here');
  });
  const text = [$('versus-title'), $('versus-lede'), ...halls.flatMap((hall) => hall.all())].map((el) => el.textContent).join(' ');
  assert.doesNotMatch(text, /\b20\d\d\b|\b\d{1,2}-\d{2}\b/, 'no dates');
  assert.doesNotMatch(text, /versus\.|compare\.|\{\w+\}/, 'every word comes from the strings');
});

test('every design card with a roofed final hall reads its numbers beside the real hall, short', async () => {
  const { $ } = await drawnPath(), real = load('rebuild-real-hall.json');
  for (const { n } of designs) {
    const record = recordOf(n);
    assert.equal(cardRow($, n), record.versus_real ? short(record.versus_real, real) : undefined, `design ${n}`);
  }
});

test('a design whose record changes shows the change, beside the real hall and on its card', async () => {
  const nine = recordOf(9), real = load('rebuild-real-hall.json');
  const changed = { ...nine, versus_real: { ...nine.versus_real, roof_rings: 5, top_m: 15.4 } };
  const { $ } = await drawnPath(undefined, { 'rebuild-design9-record.json': changed });
  const hall = $('versus-halls').children.find((h) => h.querySelector('figcaption').textContent === t('versus.design.caption', { n: 9 }));
  assert.deepEqual(hall.querySelector('ul').children.map((li) => li.textContent), beside(changed.versus_real, real));
  assert.ok(hall.querySelector('ul').children[4].textContent.includes('15.4'));
  assert.equal(cardRow($, 9), short(changed.versus_real, real));
});

test('a page file that does not come the first time is asked for again, and a failure is said only after the last try', async () => {
  const { getJson } = await import('../../studio/showpiece/page/rebuild-runs.mjs');
  let asked = 0;
  globalThis.fetch = async () => { asked += 1; if (asked < 3) throw new TypeError('Failed to fetch'); return { ok: true, json: async () => ({ designs: [1] }) }; };
  assert.deepEqual(await getJson('rebuild-designs.json', [0, 0, 0]), { designs: [1] });
  assert.equal(asked, 3, 'two failures, then the answer');
  asked = 0;
  globalThis.fetch = async () => { asked += 1; return { ok: false, status: 502 }; };
  await assert.rejects(getJson('rebuild-designs.json', [0, 0]), /HTTP 502/);
  assert.equal(asked, 3, 'one try and two more, then it gives up in words');
});
