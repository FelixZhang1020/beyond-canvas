// What the picture does at each recorded step. The record says what the agent did; this file only
// chooses how the Spark's 3D hall shows it, how long that takes to watch, and what the panels read.
// Every number and word shown comes from the record, the Spark's re-run files or the protocol. The
// run's dirty work is shown as it happened: each refused call, each failed check and each repair
// round, because the harness catching them is what the page is here to prove.
import { faultIds, familiesOf } from "./rebuild-runs.mjs";
import { ending, gloss } from "./rebuild-gloss.mjs";

const RED = [.9, .12, .08], ORANGE = [1, .56, .1], GREEN = [.2, .8, .45], GLOW = [1, .86, .55];
export const BRACKET_PHASE_MS = 6000, BRACKET_WHOLE_MS = 8000;

// A call that changed nothing: the tool refused it, could not read it, or (a design's evidence) stopped
// with an error before it finished.
export const refused = (ch) => /^REFUSED|^exit \d+:|: error: /.test(ch.evidence || "");
export const crashed = (ch) => /^exit \d+:/.test(ch.evidence || "");
// A check that ran and found a fault: the likeness or brief check or the eyes saying no, anything
// hanging, anything that fell or shifted when let go, and anything that came down when shaken. The shake
// fails only on what came down, as the gate reads it: its own "fell … shifted …" is not a fault, and design
// run 5 passed one with a piece shifted and nothing down.
export function failedCheck(ch) {
  const text = ch.evidence || "", count = (re) => Number(text.match(re)?.[1] || 0);
  if (ch.kind !== "act") return false;
  const letGo = !/^SHAKE/.test(text) && (count(/fell (\d+)/) > 0 || count(/shifted (\d+)/) > 0);
  return /NOT alike|does NOT meet the brief|^JUDGE fail/.test(text) || count(/(\d+) floating/) > 0 || letGo
    || count(/(\d+) came down/) > 0;
}
export const passedCheck = (ch) => ch.kind === "act" && ((ch.tool === "likeness" && /\| alike( \||$)/.test(ch.evidence || ""))
  || (ch.tool === "brief" && /\| meets the brief( \||$)/.test(ch.evidence || "")));
// The harness stopped something: a refused or broken call, a failed check, or a hand-over sent back.
export const caught = (ch) => refused(ch) || failedCheck(ch) || ch.kind === "bounce";

// The pieces a failed likeness or brief check names. Their names hold " | " themselves ("Frame -12.49 |
// king post"), so the list runs to the check's next field: likeness's picture, or the brief's next remedy.
export function culpritNames(evidence) {
  const text = evidence || "";
  const found = text.match(/through the roof: (.+?) \| likeness/)
    || (/^BRIEF /.test(text) ? text.match(/through the roof: (.+?)(?:; | \| brief\.png|$)/) : null);
  return found?.[1]?.split(", ") || [];
}

// Every step's scene is decided once from the whole run, because what came after a step matters:
// once the last likeness check has passed, the rest is hand-over; the first and last tested
// rounds play their tests in full.
export function prepare(chapters) {
  let lastPass = -1;
  chapters.forEach((ch, i) => { if (passedCheck(ch)) lastPass = i; });
  const tested = chapters.filter((ch) => ch.physics || ch.tool === "weights").map((ch) => ch.frame);
  const full = new Set([tested[0], tested.at(-1)]);
  chapters.forEach((ch, i) => { ch.scene = sceneFor(ch, i, lastPass); ch.full = full.has(ch.frame); ch.handedOver = lastPass >= 0 && i >= lastPass; });
  return chapters;
}

function sceneFor(ch, i, lastPass) {
  if (ch.frame === "temple") return "temple";
  if (refused(ch)) return "refused";
  if (ch.chapter === "brackets") return "brackets";
  if (ch.kind === "final" || ch.kind === "stop" || (lastPass >= 0 && i > lastPass)) return "final";
  if (i === lastPass) return "passed";
  if (ch.physics) return ch.physics;
  if (ch.tool === "weights") return "weights";
  if (ch.tool === "likeness" || ch.tool === "brief") return "likeness";      // a design's brief is its likeness
  if (ch.kind === "act" && ch.frame === `step-${ch.step}`) return ch.repair ? "repair" : "build";
  return "stage";
}

export const sceneOf = (ch) => ch.scene;

export function durationOf(ch) {
  const own = {
    brackets: 8 * BRACKET_PHASE_MS + BRACKET_WHOLE_MS, build: 3500, repair: 7000, likeness: 5000, refused: 5000, passed: 5000,
    weights: ch.full ? 9000 : 5000, settle: ch.full ? 7000 : 4000, shake: ch.full ? 10000 : 6000,
  }[ch.scene] || ch.duration_ms;
  return ch.media ? Math.max(own, ch.media.video ? 7000 : 5000) : own;      // a run's own picture is given time to be read
}

// Repair laps as the harness counts them (adoption.py laps_used): a lap opens with the first placing
// call after a check that ran; the inventory reads the hall and finds no fault, so it opens none.
const LAP_CHECKS = new Set(["bearing", "weights", "settle", "shake", "likeness", "brief"]);
export function repairRounds(chapters) {
  let round = 0, checked = false;
  return chapters.map((ch) => {
    if (ch.kind === "act" && ch.frame === `step-${ch.step}` && !refused(ch)) { if (checked) round += 1; checked = false; }
    else if (ch.kind === "act" && LAP_CHECKS.has(ch.tool) && !refused(ch)) checked = true;
    return round;
  });
}

export function captionOf(scene, t, ch) {
  if (ch?.media) return t(ch.media.video ? "caption.original.video" : "caption.original.image");
  const magnified = { settle: 50, shake: 20 }[scene];
  return ["temple", "build", "brackets", "weights", "settle", "shake", "likeness", "repair", "passed", "final", "refused"].includes(scene)
    ? t(`caption.${scene}`, { x: magnified }) : t("caption.stage");
}

function stageBefore(hall, key) {
  const keys = Object.keys(hall.record.stages);
  return keys[keys.indexOf(key) - 1];
}

export function makeScenes({ hall, t, $, protocol, chapters, record }) {
  const rounds = repairRounds(chapters), loads = !!hall.record.rounds;     // a design kept no load colours
  const firstChecked = chapters.find((ch) => ["inventory", "bearing", "settle", "likeness"].includes(ch.tool))?.frame;   // green: changed since
  let current = null, track = null, phase = 0;

  function culprits(ch) {
    const names = culpritNames(ch.evidence), stage = new Set(hall.record.stages[ch.frame] || []);
    return hall.record.pieces.flatMap(([name], id) => (stage.has(id) && names.includes(name) ? [id] : []));
  }
  function lastFailure(index) {
    for (let i = index; i >= 0; i--) if (failedCheck(chapters[i])) return chapters[i];
    return null;
  }

  // The harness's own words over the model when it stopped something, or when it let the hall through.
  function stamp(ch, scene) {
    const box = $("catch");
    const end = ch.kind === "final" || ch.kind === "stop" ? ending(ch, record, t) : null;
    const kind = end ? end.kind : crashed(ch) ? "crashed" : refused(ch) ? "refused" : failedCheck(ch) ? "failed"
      : ch.kind === "bounce" ? "bounced" : scene === "passed" ? "passed" : /not available/.test(ch.evidence || "") ? "advice" : null;
    box.hidden = !kind;
    if (!kind) return;
    box.dataset.kind = kind;
    $("catch-title").textContent = t(`catch.${kind}`);
    const words = end ? end.words : kind === "failed" ? (ch.evidence.match(/NOT alike: .+? \| likeness/)?.[0].replace(/ \| likeness$/, "") || ch.evidence)
      : kind === "passed" ? ch.evidence.split(" | likeness")[0]
        : kind === "advice" ? ch.evidence.split(";")[0] : ch.evidence;
    $("catch-words").textContent = words;
    $("catch-gloss").textContent = end ? end.line.text : gloss(ch.evidence, t)?.text || "";   // what it means, in one line
    $("catch-note").textContent = end?.note || t(kind === "failed" && ch.tool !== "likeness" ? "catch.failed.note.plain" : `catch.${kind}.note`);
  }

  function roundBadge(index) {
    const n = rounds[index], badge = $("round");
    badge.hidden = !n && !failedCheck(chapters[index]);
    const laps = record.harness.limits.laps;               // the harness code's limit, carried in the record
    badge.textContent = chapters[index].handedOver && n ? t("round.passed", { n, laps })
      : t(n ? "round" : "round.start", { n, laps });
    badge.classList.toggle("last", n === laps);
  }

  function panels(scene, ch) {
    $("load-legend").hidden = scene !== "weights" || !loads;
    $("physics-panel").hidden = scene !== "settle" && scene !== "shake";
    if (scene === "weights") $("load-source").textContent = t("legend.source", { n: ch.frame.slice(5) });
    if (scene === "settle" || scene === "shake") physicsPanel(scene, ch);
  }

  function physicsPanel(scene, ch) {
    const shake = scene === "shake";
    const spark = hall.record.rounds?.[ch.frame]?.[scene];
    const curve = (values, scale, base) => values.map((v, i) => `${i ? "L" : "M"}${(i / (values.length - 1) * 240).toFixed(1)} ${(base - v * scale).toFixed(1)}`).join(" ");
    $("physics-title").textContent = t(`physics.${scene}`);
    $("physics-ground-curve").setAttribute("d", shake ? curve(protocol.shake_path_mm, 2.6, 33) : "M0 38 L240 38");
    $("physics-pull-curve").setAttribute("d", shake ? curve(protocol.pull_g, 390, 68) : "M0 68 L240 68");
    const log = ch.evidence || "";
    $("physics-result").textContent = shake
      ? t("physics.original.shake", { down: log.match(/(\d+) came down/)?.[1] || "0", drift: log.match(/drifted at most ([\d.]+) m/)?.[1] || "?" })
      : t("physics.original.settle", { fell: log.match(/fell (\d+)/)?.[1] || "0", shifted: log.match(/shifted (\d+)/)?.[1] || "0" });
    $("physics-spark").textContent = spark ? t("physics.spark", { fell: spark.shake?.came_down ?? spark.fell, shifted: spark.shifted, max: spark.max_moved_mm }) : "";
    $("physics-source").textContent = t("physics.source", { n: ch.frame.slice(5) });
    $("physics-ground").textContent = shake ? t("physics.ground", { mm: "0.0" }) : t("physics.gravity");
    const released = (spark?.ids || []).filter((id) => hall.record.pieces[id][1] !== "stone").length;   // the ground is held
    $("physics-pull").textContent = shake ? t("physics.pull", { g: "0.00" }) : t("physics.released", { n: released });
    if (!hall.record.rounds) {                     // an earlier run: its own video, never re-run on the Spark
      $("physics-source").textContent = t(record.design ? "physics.source.design" : "physics.source.old");
      $("physics-time").textContent = "";
      if (!shake) $("physics-pull").textContent = "";
    }
  }

  function enter(ch, index) {
    const scene = sceneOf(ch);
    current = { ch, scene, index };
    track = null;
    phase = 0;
    hall.finishEffects();
    hall.clearColour();
    // The record's cutaway opens the roof so a repair can be seen. The tests hide their own covering,
    // and the likeness check keeps the roof on: what it found is timber standing out through it.
    const cutaway = !!ch.cutaway && (scene === "stage" || scene === "refused");
    if (scene === "build") {
      hall.setStage(stageBefore(hall, ch.frame));             // the platform's "before" is an empty site
      hall.look(ch.tool === "platform" || ch.tool === "columns" ? "low" : "whole");
    } else if (scene === "repair") {
      hall.setStage(stageBefore(hall, ch.frame), { cutaway: true });
      const failure = lastFailure(index);
      if (failure) hall.mark(culprits(failure), RED);
      hall.look("ends");
    } else {
      hall.setStage(ch.frame, { cutaway });
      if (scene === "likeness") { hall.mark(culprits(ch), RED); hall.look("ends"); }
      else if (scene === "passed") { hall.mark(hall.changed(firstChecked, ch.frame).added, GREEN); hall.look("ends"); }
      else if (scene === "final" && record.faults) {
        const found = faultIds(record.faults, hall.record.pieces);
        if (found.fell.length || found.hanging.length) hall.setStage(ch.frame, { cutaway: true });   // they are inside: open the roof
        hall.mark([...found.fell, ...found.roof, ...found.eaves], RED);
        hall.mark(found.hanging, ORANGE);
        hall.look(found.roof.length || found.eaves.length ? "ends" : "whole");
      }
      else if (scene === "weights" && loads) { hall.hideFamilies(["roof_tiles", "ridges"]); hall.look("frame"); }
      else if (scene === "settle" || scene === "shake") {
        hall.hideFamilies(["roof_tiles", "ridges", "walls"]);
        hall.look(scene === "shake" ? "frame" : "low");
        if (!hall.record.rounds) track = "missing";              // an earlier run was not re-run on the Spark
        else hall.motion(ch.frame, scene).then((loaded) => { if (current?.ch === ch) track = loaded; })
          .catch(() => { if (current?.ch === ch) track = "missing"; });   // the panel still reads; the hall stands still
      } else if (scene !== "refused") hall.look("whole");
    }
    stamp(ch, scene);
    roundBadge(index);
    panels(scene, ch);
    return scene;
  }

  // The tool's own moment: the whole family appears at once. A repair takes the whole roof frame
  // down and puts a whole new one up, because that is what the frames tool did every time.
  function act(ch, scene, progress) {
    const before = stageBefore(hall, ch.frame);
    if (scene === "build" && phase === 0 && progress > .15) {
      phase = 1;
      hall.setStage(ch.frame);
      hall.flash(hall.changed(before, ch.frame).added, GLOW, 1600);
    }
    if (scene === "repair" && phase === 0 && progress > .3) {
      phase = 1;
      hall.clearColour();
      hall.flash(hall.piecesOf(before, familiesOf(ch.tool)), RED, 1100, "gone");
    }
    if (scene === "repair" && phase === 1 && progress > .55) {
      phase = 2;
      hall.finishEffects();
      hall.setStage(ch.frame, { cutaway: true });
      hall.flash(hall.piecesOf(ch.frame, familiesOf(ch.tool)), GLOW, 1400);
      hall.flash(hall.changed(before, ch.frame).added, ORANGE, 1400, ORANGE);
    }
  }

  // Called every frame with how far through its time the step is; returns false while waiting on data.
  function update(progress) {
    if (!current) return true;
    const { ch, scene } = current;
    act(ch, scene, progress);
    if (scene === "weights" && loads) {
      hall.paintLoads(ch.frame, Math.min(1, progress / .8));
      // The colour starts in the roof timbers, seen from above; once it is on its way down, the camera
      // follows it under the eaves, where the brackets and columns carry the heaviest loads.
      if (progress > .45 && phase === 0) { phase = 1; hall.look("low"); }
    }
    if (scene === "settle" || scene === "shake") {
      if (!track) return false;
      if (track === "missing") return true;
      const shake = scene === "shake", seconds = track.head.frames / track.head.fps;   // as long as the run's own call asked
      const p = Math.min(1, progress / .85);
      hall.pose(track, p, shake ? 20 : 50);
      $("physics-time").textContent = t("physics.time", { t: (p * seconds).toFixed(1), total: seconds.toFixed(1) });
      const x = (p * 240).toFixed(1);
      $("physics-cursor").setAttribute("x1", x);
      $("physics-cursor").setAttribute("x2", x);
      if (shake) {
        const i = Math.min(protocol.shake_path_mm.length - 1, Math.floor(p * (protocol.shake_path_mm.length - 1)));
        $("physics-ground").textContent = t("physics.ground", { mm: protocol.shake_path_mm[i].toFixed(1) });
        $("physics-pull").textContent = t("physics.pull", { g: protocol.pull_g[i].toFixed(2) });
      }
    }
    return true;
  }

  return { enter, update };
}
