import test from "node:test";
import assert from "node:assert/strict";
import { NODES, LINKS, activity, tallies, frameRate, push, sparkPath } from "../../studio/showpiece/page/flow.mjs";

test("the monitor lights the component at work and the link it hands off along", () => {
  assert.deepEqual(activity({ phase: "thinking" }, []).lit, ["driver", "model"]);
  const render = activity({ phase: "tool", skill: "joint-reveal", tool: "explode", frames: 40 }, []);
  assert.deepEqual(render.lit, ["skill", "blender", "screen"]); assert.deepEqual(render.link, ["blender", "screen"]); assert.equal(render.skill, "joint-reveal");
  assert.deepEqual(activity({ phase: "tool", tool: "judge" }, []).lit, ["driver", "judge"]);
  assert.deepEqual(activity({ phase: "tool", skill: "model-anatomy", tool: "inventory" }, []).link, ["skill", "blender"]);
  assert.deepEqual(activity(null, [{ kind: "act", tool: "raise" }]).lit, ["ffmpeg", "screen"], "a film was just encoded");
  assert.deepEqual(activity(null, [{ kind: "look", verdict: {} }]).lit, ["judge", "screen"]);
  assert.deepEqual(activity(null, [{ kind: "final" }]).lit, ["screen"]);
  assert.deepEqual(activity(null, []).lit, []);
  for (const [a, b] of LINKS) assert.ok(NODES.includes(a) && NODES.includes(b));
});

test("the tallies add up tokens, tool seconds, frames and verdicts", () => {
  const t = tallies([
    { kind: "think", tokens: 1200 }, { kind: "act", tool: "raise", seconds: 799.4, text: "RAISE 24 scenes 296 frames" },
    { kind: "act", tool: "judge", seconds: 5, text: "{}" }, { kind: "look", verdict: { verdict: "pass" } }, { kind: "look", verdict: { verdict: "fail" } }]);
  assert.deepEqual(t, { tokens: 1200, toolSeconds: 804, acts: 2, judged: 2, passed: 1, frames: 296 });
});

test("frames per second come from two heartbeats of the same tool", () => {
  assert.equal(frameRate({ tool: "raise", frames: 10, seconds: 10 }, { tool: "raise", frames: 40, seconds: 20 }), 3);
  assert.equal(frameRate({ tool: "raise", frames: 10, seconds: 10 }, { tool: "tour", frames: 40, seconds: 20 }), null);
  assert.equal(frameRate(null, { tool: "raise", frames: 1, seconds: 1 }), null);
});

test("a sparkline keeps the last samples and draws a path scaled to its peak", () => {
  let h = [];
  for (let i = 0; i < 100; i += 1) h = push(h, i, 90);
  assert.equal(h.length, 90); assert.equal(h[89], 99);
  const path = sparkPath([0, 5, 10], 100, 20);
  assert.ok(path.startsWith("M0.0,20.0") && path.endsWith("L100.0,0.0"), path);
  assert.equal(sparkPath([null, 3], 100, 20), "", "one point is no line");
});
