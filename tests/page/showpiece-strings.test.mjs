// The showpiece page's words. Chinese only now: the page used to carry a CN/EN button, and
// what it chose was kept in the browser, so one press left it in English on every later visit. The
// operator's decision is Chinese everywhere, and tests/page/showpiece-one-language.test.mjs is what
// holds the switch out. These check the words themselves are all there and say something.
import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { SKILLS } from "../../studio/showpiece/page/stream.mjs";

const strings = JSON.parse(readFileSync(new URL("../../studio/showpiece/page/strings.json", import.meta.url), "utf8"));
const zh = strings.zh;

test("the page carries one language and it is Chinese", () => {
  assert.deepEqual(Object.keys(strings), ["zh"]);
});

test("every skill has a plain gloss beside its code name", () => {
  for (const skill of SKILLS) {
    const gloss = zh[`skill.${skill}`];
    assert.ok(gloss && gloss !== skill, `gloss for ${skill}`);
  }
});

test("a machine without a GPU reading says where one appears", () => {
  assert.match(zh["gpu.spark"], /Spark/);
});

test("the live scenarios are one per showpiece, each with its words and its minutes", () => {
  const items = zh["live.items"];
  assert.ok(items.length >= 5, "the five scenarios are there");
  for (const item of items) {
    assert.ok(item.label && item.request.length > 5 && String(item.minutes).length > 0, String(item.label));
  }
  assert.ok(items.every((i) => /大殿|斗拱|构件/.test(i.request)), "every live question is about the hall");
});

test("the prompt row is the one-press five, in their order, each by the sentence its recording was asked in", () => {
  // The prompt row used to keep its own list of prompt texts beside its own order of kinds. The rows were
  // then made one list, and each row shows its own thing: names, the sentences (from the recordings), live runs.
  const app = readFileSync(new URL("../../studio/showpiece/page/app.js", import.meta.url), "utf8");
  const demos = JSON.parse(app.match(/const DEMOS = (\[[^\]]*\])/)[1]);
  const recorded = JSON.parse(readFileSync(new URL("../../studio/showpiece/prompts/recorded.json", import.meta.url), "utf8"));
  assert.ok(!app.includes("PRESET_KINDS") && !("presets" in zh), "one list of kinds, not two that drift apart");
  assert.ok(demos.includes("settle") && demos.includes("explode"));
  for (const kind of demos) {
    assert.ok(zh[`demo.${kind}`], `${kind} has its button name`);
    assert.ok(recorded[kind].request.zh.length > 5, `${kind} keeps the words it was asked in`);
  }
});

test("the header names the Harness page", () => {
  // Harness stays English inside Chinese text, with Judge, Gate, Ledger and the rest: the operator
  // read the translated forms as strange.
  assert.match(zh["harness.link"], /Harness/);
});

test("each row and each view of the screen says what it is", () => {
  for (const key of ["demo.hint", "prompts.hint", "live.hint", "rebuild.hint"]) assert.ok(zh[key].length > 10, key);
  assert.ok(zh.rebuild, "the from-nothing replay has its own place on the switch");
  for (const view of ["live", "picture", "3d", "film", "idle", "working", "plain"]) {
    assert.ok(zh[`view.hint.${view}`].length > 5, `view ${view}`);
  }
});
