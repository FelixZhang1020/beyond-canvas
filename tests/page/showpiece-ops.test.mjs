import test from "node:test";
import assert from "node:assert/strict";
import { blockBar, sparkBlocks, clock, tokensText, processRows, treeLines, logLine, beatLine } from "../../studio/showpiece/page/ops.mjs";

const run = [
  { step: 1, kind: "think", text: "游一圈得先认得地标", tokens: 812 },
  { step: 2, kind: "act", skill: "model-anatomy", tool: "inventory", seconds: 14.2, text: "ANATOMY 8170 pieces", files: ["anatomy.json"] },
  { step: 3, kind: "act", skill: "model-anatomy", tool: "bearing", seconds: 90.7, text: "BEARING 6264 pieces", files: ["bearing.json"] },
];
const rendering = { phase: "tool", skill: "structure-tour", tool: "tour", seconds: 12, frames: 262, expected: 480, newest: "tour/f0262.png" };

test("block bars and spark blocks draw with characters, and the clock reads m:ss", () => {
  assert.equal(blockBar(50, 10), "█████░░░░░");
  assert.equal(blockBar(null, 4), "░░░░");
  assert.equal(sparkBlocks([1, 2, 4, 8]), "▁▂▄█");
  assert.equal(sparkBlocks([null, null]), "");
  assert.equal(clock(125), "2:05");
  assert.equal(tokensText(2155), "2.2k tok");
  assert.equal(tokensText(0), "–", "a recording has no token count");
});

test("the process table lights the skill and Blender while a render runs, and sums what is done", () => {
  const rows = processRows(run, rendering, 19);
  const by = Object.fromEntries(rows.map((r) => [r.name, r]));
  assert.equal(rows.length, 10, "four components and six skills");
  assert.deepEqual([by["model-anatomy"].state, by["model-anatomy"].time, by["model-anatomy"].calls], ["done", "105 s", 2]);
  assert.deepEqual([by["structure-tour"].state, by["structure-tour"].time, by["structure-tour"].busy], ["▶ tour", "12 s", true]);
  assert.deepEqual([by.blender.state, by.blender.time, by.blender.busy], ["262/480", "12 s", true]);
  assert.equal(by["load-path"].state, "–");
  assert.equal(by.driver.time, "0:19");
  const idle = processRows([...run, { step: 4, kind: "final", text: "done" }], null, 30);
  assert.equal(idle[0].state, "done");
});

test("the tree lights the branch the work is on", () => {
  const lines = treeLines(run, rendering, "带我里里外外看一遍这座大殿");
  assert.equal(lines.length, 8);
  assert.ok(lines[3].lit && lines[3].text.includes("skill/structure-tour"));
  assert.ok(lines[4].lit && lines[4].text.includes("262/480"));
  assert.ok(lines[7].lit && lines[7].text.endsWith("f0262.png"));
  assert.ok(!lines[2].lit, "the model is not thinking while Blender renders");
});

test("a log line per step, and a live line per heartbeat", () => {
  assert.deepEqual(logLine(run[1]), { who: "model-anatomy", text: "inventory  ANATOMY 8170 pieces · 14.2 s", tone: "ok" });
  assert.equal(logLine({ kind: "act", skill: "load-path", tool: "flow", text: "exit 1: boom" }).tone, "warn");
  assert.deepEqual(beatLine(rendering), { who: "blender", text: "tour frame 262/480 · 12 s" });
  assert.deepEqual(beatLine({ phase: "thinking", seconds: 3 }), { who: "model", text: "thinking · 3 s" });
  assert.equal(beatLine(null), null);
});
