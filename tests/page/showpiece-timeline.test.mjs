import test from "node:test";
import assert from "node:assert/strict";
import { reduce, chip, fold, unjudgedPicture } from "../../studio/showpiece/page/timeline.mjs";

const events = [
  { step: 1, kind: "think", text: "look first" },
  { step: 2, kind: "act", skill: "joint-reveal", tool: "closeup", picture: "tenon.png", files: ["tenon.png"], text: "CLOSEUP", seconds: 3.1 },
  { step: 3, kind: "act", skill: "shot-judge", tool: "judge", verdict: { verdict: "pass", seen: "a tenon" }, files: [], text: "{}" },
  { step: 4, kind: "look", verdict: { verdict: "pass", seen: "a tenon" }, text: "a tenon" },
  { step: 5, kind: "act", skill: "joint-reveal", tool: "explode", files: ["explode.mp4", "explode-open.png"], text: "EXPLODE" },
  { step: 6, kind: "final", text: "done" },
];

test("acts are paired with the look that judges their picture", () => {
  const { rows, gallery } = reduce(events);
  assert.equal(rows.length, 6);
  assert.equal(rows[1].verdict.verdict, "pass");
  assert.deepEqual(gallery.map((g) => g.name), ["explode-open.png", "explode.mp4", "tenon.png"]);
});

test("chips carry a tone the css knows", () => {
  assert.deepEqual(chip("look", { verdict: "fail" }), { label: "look", tone: "rust" });
  assert.equal(chip("final").tone, "olive");
});

test("pacing spreads a finished run over time and instant collapses it", () => {
});

test("a verdict belongs to the latest picture no judge has seen, live and in one go alike", () => {
  assert.equal(unjudgedPicture(events.slice(0, 2)), 2, "the close-up waits for its verdict");
  assert.equal(unjudgedPicture(events.slice(0, 3)), null, "the judge act has spoken");
  assert.equal(unjudgedPicture(events.slice(0, 4)), null, "and the look repeats it");
  const twice = [events[1], { ...events[1], step: 7, picture: "second.png" }, events[2]];
  assert.equal(unjudgedPicture(twice.slice(0, 2)), 7, "the newest picture gets the verdict");
  assert.equal(reduce(twice).rows[0].verdict, null, "the older one stays unjudged in the full draw too");
  assert.equal(reduce(twice).rows[1].verdict.verdict, "pass");
});

test("a long printout keeps its last lines and counts the rest", () => {
  const lines = Array.from({ length: 20 }, (_, i) => `line ${i + 1}`).join("\n");
  const folded = fold(lines, 6);
  assert.equal(folded.hidden, 14);
  assert.ok(folded.shown.startsWith("line 15") && folded.shown.endsWith("line 20"));
  assert.deepEqual(fold("short\ntext"), { shown: "short\ntext", hidden: 0 });
  assert.deepEqual(fold(undefined), { shown: "", hidden: 0 });
});
