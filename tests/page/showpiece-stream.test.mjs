import test from "node:test";
import assert from "node:assert/strict";
import { typeMs, typedLength, cardLine, statusOf, skillsUsed, bigPicture, SKILLS, replayPlan, PACES, FILM_FINALES } from "../../studio/showpiece/page/stream.mjs";

const events = [
  { step: 1, kind: "think", text: "x".repeat(50) },
  { step: 2, kind: "act", skill: "model-anatomy", tool: "inventory", text: "Read blend\nANATOMY 11 pieces\nBlender quit", files: ["anatomy.json"] },
  { step: 3, kind: "act", skill: "joint-reveal", tool: "explode", picture: "explode-open.png", files: ["explode-open.png", "explode.mp4"], text: "EXPLODE 9 pieces" },
  { step: 4, kind: "act", skill: "shot-judge", tool: "judge", verdict: { verdict: "pass", seen: "pieces apart" }, text: "{}" },
  { step: 5, kind: "final", text: "done" },
];

test("words type at a reading pace, faster at a higher speed", () => {
  assert.equal(typeMs(events[0], 1), 50 * 22);
  assert.equal(typeMs(events[0], 4), (50 * 22) / 4);
  assert.equal(typeMs(events[1], 1), 0, "a tool card appears whole");
  assert.equal(typeMs({ kind: "think", text: "y".repeat(10000) }, 1), 3000, "never longer than three seconds");
  assert.equal(typedLength(100, 250, 1000), 25);
  assert.equal(typedLength(100, 5000, 1000), 100);
  assert.equal(typedLength(100, 10, 0), 100);
});

test("a tool card shows the last line printed, or the error", () => {
  assert.equal(cardLine(events[1]), "ANATOMY 11 pieces", "the tool's own summary, not Blender's chatter");
  assert.equal(cardLine({ text: "00:00.2  blend | Read blend: x\nBlender 5.2.1 LTS\nBlender quit" }), "");
  assert.equal(cardLine({ text: "no such tool x/y; the tools are a, b" }), "no such tool x/y; the tools are a, b");
  assert.equal(cardLine({ text: "exit 1: Traceback\n  boom\nTypeError: x" }), "exit 1: Traceback");
  assert.equal(cardLine({ text: "" }), "");
});

test("the status line follows the heartbeat", () => {
  assert.deepEqual(statusOf(null, []), { key: "idle", pct: null });
  assert.equal(statusOf(null, events).key, "finished");
  assert.equal(statusOf({ phase: "thinking", seconds: 3 }, events).key, "thinking");
  const beat = { phase: "tool", skill: "joint-reveal", tool: "explode", frames: 45, expected: 180, seconds: 30, newest: "explode/f0045.png" };
  assert.deepEqual(statusOf(beat, events), { key: "rendering", tool: "explode", frames: 45, expected: 180, seconds: 30, pct: 25 });
  assert.equal(statusOf({ phase: "tool", tool: "judge", seconds: 2 }, events).key, "judging");
  assert.equal(statusOf({ phase: "tool", tool: "inventory", seconds: 1 }, events).key, "running");
});

test("the checklist ticks the skills as they run", () => {
  const list = skillsUsed(events.slice(0, 2), { phase: "tool", skill: "joint-reveal", tool: "explode" });
  assert.deepEqual(list.map((s) => s.state), ["done", "todo", "active", "todo", "todo", "todo"]);
  assert.equal(SKILLS.length, 6);
});

test("the big screen shows the frame being painted, else the judged picture, else the video", () => {
  const beat = { phase: "tool", tool: "explode", newest: "explode/f0045.png" };
  assert.deepEqual(bigPicture(events, beat), { src: "explode/f0045.png", live: true, verdict: null });
  assert.deepEqual(bigPicture(events, null), { src: "explode-open.png", live: false, verdict: { verdict: "pass", seen: "pieces apart" } });
  assert.deepEqual(bigPicture([events[2]].map((e) => ({ ...e, picture: null })), null), { src: "explode.mp4", video: true, live: false, verdict: null });
  assert.equal(bigPicture([events[0]], null), null);
});

test("a recorded run replays as if live: heartbeats count the frames up, then the step lands", () => {
  const recorded = [
    { step: 1, kind: "think", text: "x".repeat(20) },
    { step: 2, kind: "act", skill: "raise-the-hall", tool: "raise", text: "RAISE 24 scenes 296 frames", seconds: 799, files: ["raise.mp4"] },
    { step: 3, kind: "final", text: "done" },
  ];
  const plan = replayPlan(recorded);
  assert.equal(plan[0].beat.phase, "thinking", "a moment of thinking before the words");
  assert.equal(plan[1].event.step, 1);
  const beats = plan.filter((p) => p.beat && p.beat.phase === "tool");
  assert.equal(beats.length, 40, "twenty seconds of half-second heartbeats for a 799 s render");
  assert.equal(beats[0].beat.frames, 1); assert.equal(beats[0].beat.newest, "raise/f0001.png"); assert.equal(beats[0].beat.expected, 296);
  assert.ok(beats[beats.length - 1].beat.frames > 280 && beats[beats.length - 1].beat.frames % 3 === 1, "every third frame, the recording's own files");
  const landing = plan.find((p) => p.event && p.event.step === 2);
  assert.ok(landing.at_ms > beats[beats.length - 1].at_ms, "the act lands after its last heartbeat");
  assert.equal(plan[plan.length - 1].event.step, 3);
  const quick = replayPlan([{ step: 1, kind: "act", skill: "model-anatomy", tool: "inventory", text: "ANATOMY 11 pieces", seconds: 0.5 }]);
  assert.equal(quick.filter((p) => p.beat).length, 5, "a half-second tool still gets two and a half seconds");
  assert.equal(quick[0].beat.frames, undefined, "no frames for a tool that renders none");
});

test("a one-press button plays every step of the longest recording briskly, and ends on the 3D showpiece", () => {
  const raise = [   // the shape of the recorded raise run: its tool seconds as measured
    { step: 1, kind: "think", text: "x".repeat(40) },
    { step: 2, kind: "act", skill: "model-anatomy", tool: "inventory", text: "ANATOMY 8170 pieces", seconds: 14 },
    { step: 3, kind: "act", skill: "model-anatomy", tool: "bearing", text: "BEARING 6264 pieces 36 stages", seconds: 90 },
    { step: 4, kind: "act", skill: "raise-the-hall", tool: "stages", text: "STAGES 36", seconds: 0.4 },
    { step: 5, kind: "act", skill: "raise-the-hall", tool: "raise", text: "RAISE 36 scenes 296 frames", seconds: 1165, files: ["raise.mp4"] },
    { step: 6, kind: "final", text: "y".repeat(60) },
  ];
  const slow = replayPlan(raise, PACES.replay);
  const brisk = replayPlan(raise, PACES.brisk);
  const landed = (plan) => plan.filter((p) => p.event).map((p) => p.event.step);
  assert.deepEqual(landed(brisk), [1, 2, 3, 4, 5, 6], "every step still lands, in order");
  assert.ok(slow[slow.length - 1].at_ms > 30000, `the chip's replay takes over half a minute (${slow[slow.length - 1].at_ms} ms)`);
  assert.ok(brisk[brisk.length - 1].at_ms < 20000, `the button plays it in under twenty seconds (${brisk[brisk.length - 1].at_ms} ms)`);
  assert.ok(brisk.filter((p) => p.beat && p.beat.newest).length >= 10, "the render still paints its frames on the screen");
  assert.equal(PACES.brisk.finale, "3d", "a button ends on the 3D showpiece moving");
  assert.equal(PACES.replay.finale, "film", "a chip ends on the film, large");
});

test("the newest film of a run is the thing to put large at the end", async () => {
  const { newestFilm } = await import("../../studio/showpiece/page/stream.mjs");
  assert.equal(newestFilm(events), "explode.mp4");
  assert.equal(newestFilm(events.slice(0, 2)), null, "no film yet");
  assert.equal(newestFilm([...events, { kind: "act", files: ["tour", "tour.mp4"] }]), "tour.mp4", "the newest wins");
});

test("a file read says the file, not its contents", () => {
  assert.equal(cardLine({ kind: "act", skill: "showpiece", tool: "read", args: { file: "anatomy.json" }, text: "x".repeat(6500) }), "anatomy.json · 6 KB");
});

test("a card shows the tool's last real lines, Blender's chatter dropped", async () => {
  const { outputTail } = await import("../../studio/showpiece/page/stream.mjs");
  const text = "Blender 5.2.1\nRead blend: x\n00:00.371  blend | Read\nSaved: '/x/f0001.png'\nBEARING 9 pieces 0 floating 5 stages\nwrote bearing.json\nBlender quit\n";
  assert.deepEqual(outputTail(text, 4), ["Read blend: x", "BEARING 9 pieces 0 floating 5 stages", "wrote bearing.json"]);
  assert.deepEqual(outputTail("", 4), []);
});


test("every one-press demonstration ends on its film and keeps it, at the brisk pace", () => {
  // The build-up, the tour and the load used to fall back to the hall turning in 3D once they had played.
  assert.equal(PACES.briskFilm.finale, "film");
  assert.equal(PACES.briskFilm.maxMs, PACES.brisk.maxMs, "as quick as it was");
  for (const kind of ["raise", "tour", "explode", "load", "settle"]) assert.ok(FILM_FINALES.has(kind), kind);
});
