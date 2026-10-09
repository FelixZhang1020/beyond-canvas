// The harness view is fed by checked data, not a live run, so the data is what the tests hold to:
// every part on the board is a common harness part named by its general term, and names code in
// this repository that plays that role; every skill on the shelf is a folder under
// skills/; every journey step stands on a real part; and the journeys stay honest about what
// runs before what.
import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync, readdirSync, existsSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";
import { STEP_MS, timeline, stateAt, litOf, linesUpTo, cardFor, captionOf, logUpTo } from "../../studio/showpiece/page/harnessplay.mjs";
import { arranged } from "../../studio/showpiece/page/harnessboard.mjs";

const here = dirname(fileURLToPath(import.meta.url));
const root = join(here, "..", "..");
const page = join(root, "studio", "showpiece", "page");
const read = (name) => JSON.parse(readFileSync(join(page, name), "utf8"));
const roster = read("harness-roster.json");
const journeys = read("harness-journeys.json");
const strings = read("harness-strings.json");
const PARTS = ["request", "loop", "tools", "skills", "hook.pre", "hook.post", "hook.stop", "subagent", "permissions", "memory", "transcript", "evals"];
const STUDIO = ["art-feedback", "painting-to-animation", "sketch-to-3d", "drawings-to-storybook", "painting-to-figure"];
const THREE_D = ["model-anatomy", "joint-reveal", "structure-tour", "raise-the-hall", "load-path", "hall-carpenter"];

test("the board is the twelve harness parts, each with its general term", () => {
  assert.deepEqual(roster.stations.map((s) => s.id).sort(), [...PARTS].sort());
  for (const s of roster.stations) {
    assert.ok(typeof s.name === "string" && /^[A-Za-z0-9 :,()-]+$/.test(s.name), `${s.id} has one English name`);
    assert.ok(s.common.term.length > 2, `${s.id} names the general term`);
    for (const lang of ["zh", "en"]) {
      assert.ok(s.common.what[lang].length > 8, `${s.id} says what the term means, ${lang}`);
      assert.ok(s.here.what[lang].length > 8, `${s.id} says what we have, ${lang}`);
      assert.ok(s.gap[lang].length > 4, `${s.id} states the gap, ${lang}`);
    }
  }
});

test("every part names code in this repository that plays its role", () => {
  for (const s of roster.stations) {
    assert.ok(s.here.code.length >= 1, `${s.id} has a code path`);
    for (const path of s.here.code) assert.ok(existsSync(join(root, path)), `${s.id}: ${path} exists`);
  }
});

test("the skills on the shelf are the folders under skills/, counted from the folders both ways", () => {
  // This used to run one way only: a tile had to have a folder, but a folder needed no
  // tile, and the count was the written number 12. hall-carpenter shipped with SKILL.md, evals,
  // benchmark and signature, and the board went on showing twelve skills with a straight face.
  const folders = readdirSync(join(root, "skills"), { withFileTypes: true })
    .filter((e) => e.isDirectory() && existsSync(join(root, "skills", e.name, "SKILL.md")))
    .map((e) => e.name).sort();
  assert.deepEqual(roster.skills.map((k) => k.id).sort(), folders);
  for (const k of roster.skills) assert.ok(["studio", "3d"].includes(k.group), `${k.id} sits in no drawn group`);
});

test("the tall board names exactly the parts, tiles and wires of the wide one", () => {
  const ids = (list) => list.map((x) => x.id).sort();
  assert.deepEqual(Object.keys(roster.tall.boxes).sort(), ids(roster.stations));
  assert.deepEqual(Object.keys(roster.tall.tiles).sort(), ids(roster.skills));
  assert.deepEqual(Object.keys(roster.tall.wires).sort(), ids(roster.wires));
});

// Where a wire starts and where it ends; the wires are drawn with M, H and V only.
function ends(d) {
  let x = 0, y = 0, start = null;
  for (const [, c, a, b] of d.matchAll(/([MHV])\s*(-?[\d.]+)(?:\s+(-?[\d.]+))?/g)) {
    if (c === "M") { x = +a; y = +b; start = [x, y]; } else if (c === "H") x = +a; else y = +a;
  }
  return [start, [x, y]];
}
const onEdge = ([x, y], b) => (x >= b.x && x <= b.x + b.w && (y === b.y || y === b.y + b.h))
  || (y >= b.y && y <= b.y + b.h && (x === b.x || x === b.x + b.w));

// The board is wide on a laptop and an iPad, and tall on an upright phone, where the wide one was a strip that
// swiped with half of it off the screen. Either way a mistyped number should fail here, not leave a wire
// ending in the air or one part drawn over another.
for (const [shape, board] of [["wide", roster], ["tall", arranged(roster, true)]]) {
  test(`the ${shape} board: every part and tile lies inside it, no part on another, every wire from one part's edge to the other's`, () => {
    const [, , W, H] = board.view.split(" ").map(Number);
    const inside = ({ x, y, w, h }, o) => x >= o.x && y >= o.y && x + w <= o.x + o.w && y + h <= o.y + o.h;
    const box = Object.fromEntries(board.stations.map((s) => [s.id, s.box]));
    for (const s of board.stations) assert.ok(inside(s.box, { x: 0, y: 0, w: W, h: H }), s.id);
    for (const k of board.skills) assert.ok(inside(k.tile, box.skills), `${k.id} sits on the shelf`);
    const apart = (a, b) => a.x + a.w <= b.x || b.x + b.w <= a.x || a.y + a.h <= b.y || b.y + b.h <= a.y;
    board.stations.forEach((a, i) => board.stations.slice(i + 1).forEach((b) => assert.ok(apart(a.box, b.box), `${a.id} on ${b.id}`)));
    for (const w of board.wires) {
      assert.ok(box[w.from] && box[w.to], w.id);
      assert.match(w.d, /^M[\d. HV]*$/, `${w.id} is drawn with M, H and V only`);
      const [start, end] = ends(w.d);
      assert.ok(onEdge(start, box[w.from]), `${w.id} starts on the edge of ${w.from}`);
      assert.ok(onEdge(end, box[w.to]), `${w.id} ends on the edge of ${w.to}`);
    }
  });
}

test("the board fills the stage's height only where the part's card sits beside it", () => {
  // Under 1400px the card sits under the board. Filling the height there gave the card all of it, and the board
  // went to nothing or a thumbnail the moment a skill played: an iPad on its side, a laptop under 1400px.
  const css = readFileSync(join(page, "harness.css"), "utf8");
  const fill = css.indexOf(".hv-board { height: 100%; }");
  assert.ok(fill > 0, "the board still fills a one-screen stage");
  const block = css.lastIndexOf("@media", fill);
  assert.match(css.slice(block, css.indexOf("{", block)), /min-width: 1400px/);
  assert.match(css, /@media \(min-width: 1400px\) \{ \.hv-boardwrap \{ grid-template-columns: minmax\(0, 1fr\) 320px; \} \}/,
    "from 1400px the card has a column of its own");
});

const skillOf = (j) => j.skill || j.id;   // 松开手 (collapse) runs load-path, beside 看载荷

test("every skill a user can start has a journey, each journey its own button, labelled in both languages, and each step stands on a real part", () => {
  assert.deepEqual([...new Set(journeys.map(skillOf))].sort(), [...STUDIO, ...THREE_D].sort());
  assert.equal(new Set(journeys.map((j) => j.id)).size, journeys.length, "each journey has a button of its own");
  const ids = new Set(roster.stations.map((s) => s.id));
  const skills = new Set(roster.skills.map((k) => k.id));
  const wires = new Set(roster.wires.map((w) => w.id));
  for (const j of journeys) {
    for (const lang of ["zh", "en"]) assert.ok(j.label[lang] && j.request[lang].length > 6, `${j.id} label and request ${lang}`);
    assert.ok(j.steps.length >= 6, `${j.id} has a journey`);
    for (const st of j.steps) {
      assert.ok(ids.has(st.station), `${j.id}: ${st.station}`);
      if (st.skill) assert.ok(skills.has(st.skill), `${j.id}: ${st.skill}`);
      if (st.wire) assert.ok(wires.has(st.wire), `${j.id}: ${st.wire}`);
      for (const lang of ["zh", "en"]) assert.ok(st.caption[lang].length > 8, `${j.id} caption ${lang}`);
      if (st.line) for (const lang of ["zh", "en"]) assert.ok(st.line[lang], `${j.id} line ${lang}`);
      if (st.log) assert.ok(!/[一-鿿]/.test(st.log), `${j.id}: the console speaks English`);
    }
  }
});

test("the journeys stay honest: a hook before a tool fires before the first tool, every journey ends in the transcript, the studio screens drawings and the 3D runs are judged", () => {
  for (const j of journeys) {
    const firstTool = j.steps.findIndex((st) => st.station === "tools");
    const pre = j.steps.findIndex((st) => st.station === "hook.pre");
    assert.ok(firstTool > 0 && pre >= 0 && pre < firstTool, `${j.id}: a hook before the first tool`);
    assert.ok(j.steps.some((st) => st.station === "transcript"), `${j.id} reaches the transcript`);
    if (STUDIO.includes(skillOf(j))) assert.ok(j.steps.some((st) => st.station === "hook.pre" && st.skill === "studio-safety"), `${j.id} is screened`);
    if (THREE_D.includes(skillOf(j))) assert.ok(j.steps.some((st) => st.station === "subagent" && st.skill === "shot-judge"), `${j.id} is judged`);
  }
});

test("the page's words are Chinese only, the footnote admits what is not drawn, and nothing on the board links away", () => {
  // Both languages until the CN/EN button went and the English table with it: the
  // choice was kept in the browser, so one press left this page in English on every later visit.
  // The journeys keep their own zh/en pairs, which can no longer be reached -- the page reads them
  // by a language that is now a constant -- so only the button labels are checked here.
  assert.deepEqual(Object.keys(strings), ["zh"]);
  assert.match(strings.zh.honest, /sandbox|沙箱/);
  for (const j of journeys) assert.ok(j.label.zh, `${j.id} button label`);
  // Every card used to link one vendor's documentation and the footnote listed its pages.
  // The parts carry their general terms now, so neither the board nor its words point anywhere.
  for (const [name, table] of [["harness-roster.json", roster], ["harness-strings.json", strings]]) {
    assert.doesNotMatch(JSON.stringify(table), /https?:\/\//, `${name} holds a web address`);
  }
});

// The play module: a journey and a clock in, what is lit and what is said out. Pure, so it is tested here.
const first = journeys.find((j) => j.id === "art-feedback");

test("the timeline lays the steps end to end, two seconds each unless a step says otherwise", () => {
  const tl = timeline(first);
  assert.equal(tl[0].at, 0);
  assert.equal(tl[1].at, tl[0].ms);
  assert.equal(tl[tl.length - 1].at, tl.slice(0, -1).reduce((n, s) => n + s.ms, 0));
  assert.ok(tl.every((s) => s.ms === STEP_MS || s.ms > 0));
});

test("the clock finds the step and how far through it we are, and wraps at the end", () => {
  const total = timeline(first).reduce((n, s) => n + s.ms, 0);
  assert.deepEqual(stateAt(first, 0), { index: 0, progress: 0, total, lap: 0 });
  const half = timeline(first)[1].at + timeline(first)[1].ms / 2;
  assert.equal(stateAt(first, half).index, 1);
  assert.ok(Math.abs(stateAt(first, half).progress - 0.5) < 1e-9);
  assert.equal(stateAt(first, total + 10).index, 0);
  assert.equal(stateAt(first, total + 10).lap, 1, "the second time round is lap one, so the console can clear");
});

test("what is lit at a step is its part, its skill, its wire and its verdict", () => {
  const lit = litOf(first, 0);
  assert.deepEqual(Object.keys(lit).sort(), ["skill", "station", "verdict", "wire"]);
  assert.equal(lit.station, first.steps[0].station);
  assert.equal(litOf(first, 999).station, null);
});

test("the transcript lines grow with the steps and speak the chosen language; the console gets only the steps that carry a log line", () => {
  const all = linesUpTo(first, first.steps.length - 1, "en");
  assert.equal(all.length, first.steps.filter((s) => s.line).length);
  assert.deepEqual(linesUpTo(first, -1, "en"), []);
  const logs = logUpTo(first, first.steps.length - 1);
  assert.equal(logs.length, first.steps.filter((s) => s.log).length);
  assert.ok(logs.every((l) => typeof l === "string"));
});

test("a part's card carries the general term, what we have, the gap, and what it did most recently in this journey", () => {
  const card = cardFor(roster, first, "hook.pre", first.steps.length - 1, "en");
  assert.equal(card.title, roster.stations.find((s) => s.id === "hook.pre").name);
  assert.deepEqual(Object.keys(card).sort(), ["code", "gap", "here", "now", "term", "title", "what"], "the card carries no link");
  assert.ok(card.term && card.what && card.here && card.gap && card.code.length >= 1);
  assert.ok(card.now, "the safety hook fired in this journey");
  assert.equal(cardFor(roster, first, "nowhere", 0, "zh"), null);
  const zh = cardFor(roster, first, "skills", 0, "zh");
  assert.equal(zh.title, roster.stations.find((s) => s.id === "skills").name, "the diagram's names stay English whatever the language");
  assert.ok(/[一-鿿]/.test(zh.here), "the description follows the language");
});

test("captions fall back to Chinese", () => {
  assert.equal(captionOf(first, 0, "fr"), first.steps[0].caption.zh);
});

test("on a one-screen stage the wrapper has a row each for the header, the buttons and the stage, and the stage is the one that flexes", () => {
  // The demo's stylesheet gives the wrapper two rows on that breakpoint, header and stage. This page adds a
  // third block, the button row, which without its own row landed in the flexible one and collapsed to
  // nothing on a short window, the stage drawn over it. Seen in use.
  const js = readFileSync(join(page, "harness.js"), "utf8");
  const css = readFileSync(join(page, "harness.css"), "utf8");
  const demo = readFileSync(join(page, "style.css"), "utf8");
  assert.match(js, /class: "wrap hv-wrap"/, "the page's wrapper carries its own class");
  // The breakpoint itself is read from the demo's stylesheet rather than written here: the two pages
  // have to answer the same one, and pinning the number meant tuning it broke this test rather than
  // the thing it guards. It moved from 760 to 640 because a maximised window on a
  // 1080p display reports between 700 and 800 and the page flipped layouts across that line.
  const gate = demo.match(/@media \(min-width: 1100px\) and \(min-height: \d+px\)/);
  assert.ok(gate, "the demo stylesheet still has a one-screen block");
  const start = css.indexOf(gate[0]);
  assert.ok(start >= 0, `the harness answers the demo's one-screen breakpoint, ${gate[0]}`);
  const oneScreen = css.slice(start, css.indexOf("\n}", start));   // that block only, up to its own closing brace
  assert.match(oneScreen, /\.wrap\.hv-wrap \{ grid-template-rows: auto auto minmax\(0, 1fr\);/, "three rows, the last flexible");
});
