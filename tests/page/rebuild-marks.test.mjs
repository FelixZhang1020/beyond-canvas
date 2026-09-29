import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { isKey, keySeconds, nextKey } from '../../studio/showpiece/page/rebuild-marks.mjs';
import { caught, durationOf, prepare } from '../../studio/showpiece/page/rebuild-scenes.mjs';

const load = (name) => JSON.parse(readFileSync(new URL(`../../studio/showpiece/page/${name}`, import.meta.url), 'utf8'));
const runs = ['rebuild-record.json', 'rebuild-run1-record.json', 'rebuild-run2-record.json', 'rebuild-run3-record.json']
  .map((name) => ({ name, steps: prepare(load(name).steps) }));

test('key moments only keeps every catch, repair, pass and ending of every run, and skips the thinking', () => {
  for (const { name, steps } of runs) {
    for (const ch of steps) {
      if (caught(ch) || ['repair', 'passed', 'brackets', 'refused'].includes(ch.scene) || ch.kind === 'final' || ch.kind === 'stop') {
        assert.ok(isKey(ch), `${name} step ${ch.step} (${ch.scene}) is not kept`);
      }
      if (ch.kind === 'think') assert.equal(isKey(ch), false, `${name} step ${ch.step}: a thinking step is kept`);
    }
  }
});

test('playing only the key moments of the adopted run is clearly shorter, though it keeps the bracket minute', () => {
  // Measured: 235 s of 423 s. The bracket chapter's minute and every catch and repair stay in.
  const { steps } = runs[0];
  const all = Math.round(steps.reduce((sum, ch) => sum + durationOf(ch), 0) / 1000);
  assert.ok(keySeconds(steps, durationOf) < all * 0.6, `${keySeconds(steps, durationOf)} s of ${all} s`);
});

test('the next and previous key moment are found from any step, and there is none past the ends', () => {
  const { steps } = runs[0];
  const first = nextKey(steps, -1);
  assert.ok(first !== null && isKey(steps[first]));
  assert.equal(nextKey(steps, steps.length - 1), null);
  const back = nextKey(steps, steps.length - 1, -1);
  assert.ok(back !== null && isKey(steps[back]) && back < steps.length - 1);
});
