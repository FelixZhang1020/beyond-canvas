import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { createContext, runInContext } from 'node:vm';

// Exercise the actual controller without starting fetches or a browser animation loop.
test('idle animation frames preserve the DOM, while explicit redraws and pinned cards update it', () => {
  const source = readFileSync(new URL('../../studio/showpiece/page/harness.js', import.meta.url), 'utf8')
    .replace(/^import .*;\n/gm, '').replace(/\nboot\(\);\s*$/, '');
  const context = createContext({window: {matchMedia: () => ({matches: false})}, calls: 0});
  runInContext(source, context);
  runInContext('idle = () => { calls += 1; }; paint(true);', context);
  assert.equal(context.calls, 1, 'initial shell is populated');
  runInContext('for (let frame = 0; frame < 120; frame++) paint(false);', context);
  assert.equal(context.calls, 1, 'idle frames must not rebuild the log and detail card');
  runInContext('pin("loop");', context);
  assert.equal(context.calls, 2, 'a user selection still redraws');
  runInContext('pin("loop");', context);
  assert.equal(context.calls, 3, 'releasing the selection still redraws');
});
