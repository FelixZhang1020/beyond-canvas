// The exhibit pages have one language and no way to change it.
//
// The classroom page lost its CN/EN control because teachers pressed it by accident
// and then could not read the studio well enough to put it back. The two exhibit pages -- the
// Agentic 3D showpiece and the Harness board, which are what a judge opens -- kept theirs, and
// theirs was worse: the choice was written to localStorage under `showpiece.lang`, so one press
// left the page in English on every later visit until somebody pressed it back. Both pages already
// declared `<html lang="zh">` and started in Chinese, so nothing looked wrong until it happened.
//
// These read the source rather than drive the page because what is being asserted is an absence,
// and an absence is only worth testing where it cannot be quietly re-added: a button built at
// runtime is invisible to anyone searching the HTML, which is how this survived the first sweep.
import test from 'node:test';
import assert from 'node:assert';
import { readFileSync } from 'node:fs';

const PAGE = new URL('../../studio/showpiece/page/', import.meta.url);
const read = (name) => readFileSync(new URL(name, PAGE), 'utf8');
const SCRIPTS = ['app.js', 'harness.js'];
const TABLES = ['strings.json', 'harness-strings.json'];

test('neither exhibit page builds a language button', () => {
  for (const name of SCRIPTS) {
    assert.ok(!/id:\s*["']lang["']/.test(read(name)), `${name} still builds a language control`);
  }
});

test('neither exhibit page has anything to press it with', () => {
  for (const name of SCRIPTS) {
    const source = read(name);
    assert.ok(!/\$\(\s*["']lang["']\s*\)/.test(source), `${name} still wires a language control`);
    assert.ok(!/switchLang/.test(source), `${name} still has a language switch`);
  }
});

test('nothing remembers a language between visits', () => {
  // The part that made this worse than the classroom page: a press outlived the visit.
  for (const name of SCRIPTS) {
    assert.ok(!read(name).includes('showpiece.lang'), `${name} still keeps a language preference`);
  }
});

test('the language cannot be reassigned, so it stays the constant it is declared as', () => {
  for (const name of SCRIPTS) {
    const source = read(name);
    assert.ok(/const state = \{ lang: "zh"/.test(source), `${name} does not declare Chinese`);
    assert.ok(!/state\.lang\s*=/.test(source), `${name} assigns to state.lang somewhere`);
  }
});

test('the word tables hold Chinese and nothing else', () => {
  for (const name of TABLES) {
    const table = JSON.parse(read(name));
    assert.deepEqual(Object.keys(table), ['zh'], `${name} still carries another language`);
  }
});

test('both pages declare themselves Chinese to the browser', () => {
  for (const name of ['index.html', 'harness.html']) {
    assert.ok(read(name).includes('<html lang="zh">'), `${name} does not declare Chinese`);
  }
});
