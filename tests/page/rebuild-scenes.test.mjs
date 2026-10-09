import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { existsSync } from 'node:fs';
import { caught, culpritNames, durationOf, failedCheck, prepare, repairRounds, sceneOf } from '../../studio/showpiece/page/rebuild-scenes.mjs';

const page = (name) => new URL(`../../studio/showpiece/page/${name}`, import.meta.url);
const load = (name) => JSON.parse(readFileSync(page(name), 'utf8'));
const record = load('rebuild-record.json');
const steps = prepare(record.steps);
const at = (n) => steps.find((s) => s.step === n);

test('every recorded step of the replay has a picture, and only the survey shows the photograph', () => {
  assert.equal(steps.length, 145);
  const scenes = steps.map(sceneOf);
  assert.deepEqual([...new Set(steps.filter((s) => s.frame === 'temple').map(sceneOf))], ['temple']);
  for (const kind of ['build', 'brackets', 'weights', 'settle', 'shake', 'likeness', 'repair', 'refused', 'passed', 'final']) {
    assert.ok(scenes.includes(kind), `no step shows ${kind}`);
  }
});

test('the bracket assembly is given about a minute, not the quarter-minute it flashed past in', () => {
  assert.equal(sceneOf(at(18)), 'brackets');
  assert.ok(durationOf(at(18)) >= 50000, `${durationOf(at(18))} ms`);
});

test('each of the seven tested rounds shows all three tests, the first and last in full', () => {
  for (const tool of ['weights', 'settle', 'shake']) {
    const rounds = steps.filter((s) => (s.physics || s.tool) === tool);
    assert.equal(rounds.length, 7, tool);
    const first = durationOf(rounds[0]), last = durationOf(rounds.at(-1));
    for (const middle of rounds.slice(1, -1)) assert.ok(durationOf(middle) < first && durationOf(middle) < last, tool);
    assert.ok(first >= 7000, `${tool} first round ${first} ms`);
  }
});

test('the dirty work is shown: three refused calls and five failed checks, each stopped by the harness', () => {
  assert.deepEqual(steps.filter((s) => sceneOf(s) === 'refused').map((s) => s.step), [26, 48, 50]);
  assert.deepEqual(steps.filter(caught).map((s) => s.step), [26, 44, 48, 50, 66, 80, 94, 108]);
  assert.equal(caught(at(143)), false, 'the engineer not answering is advice missing, not a catch');
});

test('repairs are counted as the harness counts laps, and the hall passes on the sixth of six', () => {
  assert.deepEqual(steps.filter((s) => sceneOf(s) === 'repair').map((s) => s.step), [52, 54, 68, 82, 96, 110, 126]);
  const rounds = repairRounds(steps);
  const roundOf = (n) => rounds[steps.indexOf(at(n))];
  assert.deepEqual([52, 54, 68, 82, 96, 110, 126].map(roundOf), [1, 1, 2, 3, 4, 5, 6]);
  assert.equal(roundOf(138), 6);
});

test('the pieces a failed check names are read whole, though their names hold the separator', () => {
  assert.deepEqual(culpritNames(at(44).evidence), ['Frame -12.49 | king post', 'Frame 12.49 | king post']);
  assert.deepEqual(culpritNames(at(66).evidence), ['Frame -12.49 | king post']);
  assert.deepEqual(culpritNames(at(138).evidence), []);
});

test('the three earlier runs play too, each ending as it did: stopped, adopted wrongly, adopted', () => {
  const runs = [1, 2, 3].map((n) => ({ n, record: load(`rebuild-run${n}-record.json`) }));
  for (const { n, record: r } of runs) {
    const played = prepare(r.steps);
    assert.ok(played.every((ch) => ch.scene), `run ${n}: a step has no picture`);
    for (const ch of played.filter((c) => c.media)) {
      for (const file of [ch.media.image, ch.media.video].filter(Boolean)) assert.ok(existsSync(page(file)), `run ${n}: ${file} is missing`);
    }
    const hall = load(`rebuild-run${n}-hall.json`), names = new Set(hall.pieces.map(([name]) => name));
    for (const name of [...r.faults.fell, ...r.faults.hanging, ...r.faults.through_the_roof]) assert.ok(names.has(name), `run ${n}: ${name} is not in its hall`);
  }
  const [one, two, three] = runs.map(({ record: r }) => r);
  assert.equal(one.steps.at(-1).kind, 'stop');
  assert.deepEqual([one.faults.fell.length, one.faults.hanging.length], [26, 6]);
  assert.equal(two.measured.adopted, true);
  assert.ok(two.faults.found_later && two.faults.through_the_roof.includes('Frame -12.49 | king post'), 'run 2 is shown wrong by today\'s check');
  assert.ok(prepare(three.steps).filter(caught).some((ch) => ch.tool === 'judge'), 'run 3: the eyes failing the hall is a catch');
});

test('a check that found a fault counts as caught in any run: hanging, fallen, not alike or the eyes saying no', () => {
  const one = prepare(load('rebuild-run1-record.json').steps);
  const found = one.filter(caught).map((ch) => ch.tool);
  assert.ok(found.includes('bearing') && found.includes('settle'), found.join());
});

test("the repair rounds the page counts are the laps each run's own scorecard counted", () => {
  for (const name of ['rebuild-record.json', 'rebuild-run1-record.json', 'rebuild-run3-record.json']) {
    const r = load(name);
    assert.equal(Math.max(0, ...repairRounds(prepare(r.steps))), r.harness.turns.repair_laps, name);
  }
  // Run 2's scorecard counted a lap after the piece count too, which the harness no longer
  // does; docs/measured/from-nothing-rebuild.md lists its repair laps as "0 real".
  const two = load('rebuild-run2-record.json');
  assert.equal(two.harness.turns.repair_laps, 2);
  assert.equal(Math.max(0, ...repairRounds(prepare(two.steps))), 0);
});

test('a shake fails only on what came down, as the gate reads it; a let-go fails on anything that fell or shifted', () => {
  const act = (evidence) => ({ kind: 'act', evidence });
  assert.equal(failedCheck(act('SHAKE 1894 pieces fell 0 shifted 1 | the ground moved 8.0 mm | 0 came down | 0 had moved')), false);
  assert.equal(failedCheck(act('SHAKE 1894 pieces fell 0 shifted 0 | the ground moved 8.0 mm | 2 came down | 0 had moved')), true);
  assert.equal(failedCheck(act('SETTLE 2243 pieces fell 0 shifted 1')), true);
});
