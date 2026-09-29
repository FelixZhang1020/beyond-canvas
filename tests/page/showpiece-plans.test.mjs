import test from "node:test";
import assert from "node:assert/strict";
import { yUp, ease, explodeAt, raiseAt, loadTint, tourAt, settleShift, showpieceOf, groupOf } from "../../studio/showpiece/page/plans.mjs";

test("Blender's z-up becomes the GLB's y-up", () => {
  assert.deepEqual(yUp([1, 2, 3]), [1, 3, -2]);
  assert.equal(ease(0), 0); assert.equal(ease(1), 1); assert.ok(ease(0.5) > 0.49 && ease(0.5) < 0.51);
});

test("the pull-apart opens along each piece's offset", () => {
  const plan = { pieces: [{ name: "Slab", tier: 0, offset: [0, 0, 0] }, { name: "Tile sheet", tier: 4, offset: [0, 0, 0.72] }] };
  assert.deepEqual(explodeAt(plan, 0)["Tile sheet"], [0, 0, -0]);
  assert.deepEqual(explodeAt(plan, 1)["Tile sheet"], [0, 0.72, -0]);
  assert.deepEqual(explodeAt(plan, 1).Slab, [0, 0, -0]);
  assert.deepEqual(explodeAt({ pieces: [{ name: "Ludou foot | JOINT", offset: [0, 0, 1] }] }, 1), { "Ludou foot": [0, 1, -0] }, "a joint copy moves the piece itself");
});

test("the build-up shows the scenes so far, the newest dropping in", () => {
  const scenes = { scenes: [{ index: 1, pieces: ["Column SW"] }, { index: 2, pieces: ["Lintel front"] }, { index: 3, pieces: ["Tile sheet"] }] };
  const start = raiseAt(scenes, 0);
  assert.deepEqual([...start.visible], ["Column SW"]);
  assert.equal(start.offsets["Column SW"][1], 3, "still three metres up");
  const mid = raiseAt(scenes, 0.5);
  assert.deepEqual([...mid.visible], ["Column SW", "Lintel front"]);
  assert.equal(mid.offsets["Column SW"], undefined, "an earlier scene has landed");
  assert.ok(mid.offsets["Lintel front"][1] > 0 && mid.offsets["Lintel front"][1] < 3);
  const end = raiseAt(scenes, 1);
  assert.equal(end.visible.size, 3); assert.deepEqual(end.offsets, {});
  assert.equal(raiseAt({ scenes: [] }, 0.5).visible.size, 0);
});

test("load tint runs from blue to red on a log scale", () => {
  const loads = { pieces: { light: { carries_N: 100 }, heavy: { carries_N: 2e6 } } };
  const blue = loadTint(loads, "light"), red = loadTint(loads, "heavy");
  assert.ok(blue[2] > blue[0] && red[0] > red[2]);
  assert.equal(loadTint(loads, "nobody"), null);
});

test("the tour camera moves through the segment that holds the frame", () => {
  const tour = { frames: 240, segments: [
    { name: "outside", at: [[0, -10, 5], [10, 0, 5]], look: [[0, 0, 2], [0, 0, 2]], hidden_roles: [], frames: [1, 120] },
    { name: "overhead", at: [[0, 0, 20], [0, 0, 20]], look: [[0, 0, 0], [0, 0, 0]], hidden_roles: ["covering", "rafter"], frames: [121, 240] }] };
  const first = tourAt(tour, 0);
  assert.equal(first.name, "outside"); assert.deepEqual(first.at, [0, 5, 10]);
  const half = tourAt(tour, 0.25);
  assert.ok(half.at[0] > 4 && half.at[0] < 6, "half way along the first segment");
  const last = tourAt(tour, 1);
  assert.equal(last.name, "overhead"); assert.deepEqual(last.hidden, ["covering", "rafter"]); assert.deepEqual(last.at, [0, 20, -0]);
  assert.equal(tourAt({ segments: [] }, 0.5), null);
});

test("settle sinks the movers and names them", () => {
  const settle = { pieces: { ear: { moved_m: 8.9, drop_m: 8.6 }, seat: { moved_m: 0.004, drop_m: 0.004 } } };
  assert.deepEqual(settleShift(settle, "ear"), { offset: [0, -8.6, 0], moved: true, fell: true });
  assert.equal(settleShift(settle, "seat").moved, false);
  assert.equal(settleShift(settle, "nobody"), null);
});

test("the showpiece of a run is the last plan it wrote", () => {
  assert.equal(showpieceOf(["anatomy.json", "bearing.json", "explode.json", "explode.mp4"]), "explode");
  assert.equal(showpieceOf(["scenes.json", "raise.json", "settle.json"]), "settle");
  assert.equal(showpieceOf(["anatomy.json"]), null);
});

test("pieces that move together are drawn together", () => {
  const explode = { pieces: [{ name: "Slab", offset: [0, 0, 0] }, { name: "Tile sheet", offset: [0, 0, 0.7] }] };
  const g = groupOf("explode", explode);
  assert.equal(g("Slab"), "static"); assert.equal(g("Tile sheet"), "p:Tile sheet"); assert.equal(g("stranger"), "static");
  const raise = { scenes: [{ pieces: ["Column SW"] }, { pieces: ["Lintel front"] }] };
  const r = groupOf("raise", raise);
  assert.equal(r("Column SW"), "s:0"); assert.equal(r("Lintel front"), "s:1"); assert.equal(r("Slab"), "static");
  const tour = groupOf("tour", {}, { "Tile sheet": "covering", "Column SW": "timber" });
  assert.equal(tour("Tile sheet"), "r:covering"); assert.equal(tour("nobody"), "r:none");
  const settle = groupOf("settle", { pieces: { ear: { moved_m: 8 }, seat: { moved_m: 0.001 } } });
  assert.equal(settle("ear"), "p:ear"); assert.equal(settle("seat"), "static");
  const roofRoles = { "Tile sheet": "covering", "Rafter back": "rafter", "Column SW": "timber" };
  const load = groupOf("load", {}, roofRoles);
  assert.equal(load("Tile sheet"), "r:covering"); assert.equal(load("Rafter back"), "r:rafter"); assert.equal(load("Column SW"), "static");
  assert.equal(groupOf("settle", { pieces: {} }, roofRoles)("Tile sheet"), "r:covering", "settle lifts the roof off too");
});

test("every piece wears the colour of its role, and an unknown role a pale one", async () => {
  const { roleTint } = await import("../../studio/showpiece/page/plans.mjs");
  assert.notDeepEqual(roleTint("timber"), roleTint("covering"), "wood and roof tiles differ");
  assert.deepEqual(roleTint("nothing-like-this"), [0.82, 0.79, 0.73]);
  for (const role of ["timber", "rafter", "covering", "wall", "ground"]) assert.ok(roleTint(role).every((c) => c > 0 && c <= 1), role);
});
