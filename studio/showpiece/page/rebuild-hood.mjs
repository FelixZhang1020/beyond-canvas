// Under the hood: how each recorded step travelled from the model through the harness to Blender
// and back, and how the harness stopped, calibrated and accepted the hall. Every number comes from
// the record: the run's own log per step, and the harness facts rebuild_facts.py read from the run
// folder and the harness code. Nothing here is typed in.
import { caught, failedCheck, refused, repairRounds, sceneOf } from "./rebuild-scenes.mjs";
import { reply } from "./rebuild-gloss.mjs";

const ALL_CHECKS = ["inventory", "bearing", "weights", "settle", "shake", "likeness", "brief", "judge"];   // a design has brief, not likeness
const PLACING = new Set(["platform", "columns", "ties", "walls", "brackets", "frames", "purlins", "rafters", "roof"]);
const esc = (text) => String(text ?? "").replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" })[c]);
const num = (n) => Number(n).toLocaleString("en-US");
const clock = (s) => `${String(Math.floor(s / 60)).padStart(2, "0")}:${String(s % 60).padStart(2, "0")}`;

function node(id, x, y, w, h, title, sub) {
  return `<g class="node" id="${id}"><rect x="${x}" y="${y}" width="${w}" height="${h}" rx="14"/>
    <text class="title" x="${x + w / 2}" y="${y + 25}" id="${id}-title">${esc(title)}</text>
    <text class="sub" x="${x + w / 2}" y="${y + 42}" id="${id}-sub">${esc(sub)}</text>
    <text class="dyn" x="${x + w / 2}" y="${y + 57}" id="${id}-dyn"></text></g>`;
}

function edge(id, d, label, lx, ly) {
  return `<g class="edge" id="${id}"><path d="${d}"/><text x="${lx}" y="${ly}">${esc(label)}</text></g>`;
}

export function makeHood({ $, t, record, chapters }) {
  const facts = record.harness, rounds = repairRounds(chapters), limits = facts.limits || null;
  // The checks this run's gate had: the fourth run's code lists them; an earlier run's are the ones it ran.
  const CHECKS = (facts.checks || ALL_CHECKS).map((c) => c.split("/").pop()).filter((c) => ALL_CHECKS.includes(c));
  const total = clock(Math.round(record.measured.wall_seconds));
  const acted = [], tokens = [], tools = [], gate = [];
  let a = 0, tk = 0, ts = 0, state = Object.fromEntries(CHECKS.map((c) => [c, "stale"]));
  for (const ch of chapters) {       // running totals and the gate's view of every check, step by step
    if (ch.kind === "act") a += 1;
    tk += ch.tokens || 0;
    ts += ch.seconds || 0;
    if (PLACING.has(ch.tool) && !refused(ch)) state = Object.fromEntries(CHECKS.map((c) => [c, "stale"]));
    if (CHECKS.includes(ch.tool) && !refused(ch)) state = { ...state, [ch.tool]: failedCheck(ch) ? "bad" : "good" };   // a call that errored ran no check
    acted.push(a); tokens.push(tk); tools.push(ts); gate.push(state);
  }

  // A square loop for the page's right column: model → Harness, down to the skill, across to where it
  // runs, and the result back up to the model; the gate below, reached from the Harness on hand-over.
  function loop() {
    const left = 230 - (CHECKS.length * 40 - 4) / 2;
    const pills = CHECKS.map((c, i) => `<g class="pill" id="pill-${c}"><rect x="${left + i * 40}" y="266" width="36" height="24" rx="12"/>
      <text x="${left + 18 + i * 40}" y="282">${esc(t(`pill.${c}`))}</text></g>`).join("");
    $("loop").innerHTML = `
      ${edge("e-back", "M106 136 L106 94", t("edge.back"), 54, 119)}
      ${edge("e-action", "M196 62 L264 62", t("edge.action"), 230, 54)}
      ${edge("e-argv", "M354 94 L354 136", t("edge.argv"), 398, 119)}
      ${edge("e-run", "M264 168 L196 168", t("edge.run"), 230, 160)}
      ${edge("e-gate", "M444 62 C458 62 458 267 444 267", t("edge.handover"), 418, 222)}
      ${node("n-model", 16, 30, 180, 64, facts.model.name, facts.model.reasoning ? t("node.model.sub", { r: facts.model.reasoning }) : facts.model.id)}
      ${node("n-harness", 264, 30, 180, 64, "Harness", t("node.harness.sub"))}
      ${node("n-skill", 264, 136, 180, 64, t("node.skill"), "")}
      ${node("n-run", 16, 136, 180, 64, t("run.idle"), "")}
      <g class="node gate" id="n-gate"><rect x="16" y="236" width="428" height="62" rx="14"/>
        <text class="sub" x="230" y="256">${esc(t("node.gate", { n: CHECKS.length }))}</text>${pills}</g>
      <g class="counts"><text id="c-actions" x="16" y="320"></text><text id="c-laps" x="16" y="338"></text>
        <text id="c-caught" x="16" y="356"></text><text id="c-tokens" x="444" y="320"></text><text id="c-tools" x="444" y="338"></text></g>`;
  }

  function set(id, cls) { $(id).setAttribute("class", `${$(id).getAttribute("class").split(" ")[0]} ${cls || ""}`.trim()); }
  function text(id, value) { $(id).textContent = value; }

  function flow(ch, i) {
    const act = ch.kind === "act", bad = refused(ch) || failedCheck(ch), read = ch.tool === "read";
    const runtime = read ? t("run.read") : (ch.command || "").startsWith("blender") ? t("run.blender") : act ? t("run.python") : t("run.idle");
    set("n-model", ch.kind === "act" ? "" : "on");
    set("n-harness", act ? (bad ? "bad" : "on") : "");
    set("n-skill", act ? (refused(ch) ? "bad" : "on") : "");
    set("n-run", act && !read ? (refused(ch) ? "bad" : "on") : "");
    set("e-action", act ? "on" : "");
    set("e-argv", act ? "on" : "");
    set("e-run", act && !read ? "on" : "");
    set("e-back", ch.kind === "think" || ch.kind === "look" ? "on" : bad ? "bad" : "");
    const handOver = ch.kind === "final" || ch.kind === "bounce";          // a bounce is a hand-over the gate sent back
    set("e-gate", handOver ? "on" : "");
    set("n-gate", ch.kind === "final" || sceneOf(ch) === "passed" ? "good" : failedCheck(ch) || ch.kind === "bounce" ? "bad" : "");
    text("n-model-dyn", ch.kind === "think" ? t("model.thinking", { n: num(ch.tokens || 0) }) : ch.kind === "look" ? t("model.looking")
      : handOver ? t("model.final") : t("model.acting"));
    text("n-harness-dyn", !act ? (handOver ? t("harness.gate") : "") : refused(ch) ? t("harness.refused")
      : failedCheck(ch) ? t("harness.failed") : read ? t("harness.read") : t("harness.parse"));
    text("n-skill-title", act ? ch.skill : t("node.skill"));
    text("n-skill-sub", act ? ch.tool : "");
    text("n-run-title", runtime);
    text("n-run-sub", act && !read ? t("run.seconds", { s: ch.seconds }) : "");
    text("n-run-dyn", refused(ch) ? t("run.refused") : "");
    for (const c of CHECKS) set(`pill-${c}`, gate[i][c]);
    const counts = [
      limits ? t("count.actions", { n: acted[i], cap: limits.actions }) : t("count.actions.bare", { n: acted[i] }),
      limits ? t("count.laps", { n: rounds[i], laps: limits.laps }) : t("count.laps.bare", { n: rounds[i] }),
      t("count.caught", { n: chapters.slice(0, i + 1).filter(caught).length }),
      t("count.tokens", { n: num(tokens[i]) }),
    ];
    ["c-actions", "c-laps", "c-caught", "c-tokens"].forEach((id, k) => text(id, counts[k]));
    text("c-tools", t("count.tools", { s: num(Math.round(tools[i])) }));
    mini(ch);
  }

  // What the harness said back, in words, beside the controls.
  function mini(ch) {
    const said = reply(ch, record, t);
    $("mini-dot").className = said.tone;
    $("mini-text").textContent = said.text;
  }

  function block(label, body, cls = "") {
    return `<div class="call-block ${cls}"><label>${esc(label)}</label><pre>${esc(body)}</pre></div>`;
  }

  function card(ch, i) {
    const head = `<div class="call-head"><b>${esc(t("call.step", { n: ch.step }))}</b><span>${esc(t("time", { at: clock(ch.elapsed), total }))}</span></div>`;
    let body = "";
    if (ch.kind === "think") body = block(t("call.think", { n: num(ch.tokens || 0) }), ch.evidence, "model");
    else if (ch.kind === "look") body = block(t("call.look"), ch.evidence, "model");
    else if (ch.kind === "final") {
      const wrong = record.faults?.found_later || record.faults?.through_the_roof?.length;   // a later check found it
      body = block(t("call.final", { v: t(wrong ? "call.wrongly" : "call.adopted") }), ch.evidence, wrong ? "bad" : "good");
    }
    else if (ch.kind === "stop") body = block(t("call.stop"), ch.evidence, "bad");
    else if (ch.kind === "bounce") body = block(t("call.bounce"), ch.evidence, "bad");
    else {
      const thought = chapters[i - 1]?.kind === "think" ? chapters[i - 1].evidence : "";
      const action = { think: thought.length > 96 ? `${thought.slice(0, 96)}…` : thought, skill: ch.skill, tool: ch.tool, args: ch.args || {} };
      const back = ch.evidence || "";
      body = block(t("call.action"), JSON.stringify(action, null, 1), "model")
        + block(t("call.run", { s: ch.seconds }), `$ ${ch.command}`, "run")
        + block(t("call.back"), back, refused(ch) || failedCheck(ch) ? "bad" : /alike$|\| alike|pass/.test(back) ? "good" : "");
    }
    $("call").innerHTML = head + body;
  }

  function how() {
    const f = facts.found, s = facts.survey, g = facts.guards, lim = facts.limits, like = f.likeness;
    const refusedSteps = chapters.filter(refused).map((ch) => ch.step);
    const rule = (line, run) => `<li><span>${esc(line)}</span>${run ? `<b>${esc(run)}</b>` : ""}</li>`;
    $("how-guard").innerHTML = `<h3>${esc(t("guard.title"))}</h3><ul>
      ${rule(t("guard.json"))}
      ${rule(t("guard.allowed", { skills: facts.skills.join(" · ") }))}
      ${rule(t("guard.args", { s0: g.section_m[0], s1: g.section_m[1], p0: g.spacing_m[0], p1: g.spacing_m[1] }),
        t("guard.args.run", { n: refusedSteps.length, steps: refusedSteps.join(t("list.sep")) }))}
      ${rule(t("guard.cap", { cap: lim.actions }), t("guard.cap.run", { n: facts.turns.actions }))}
      ${rule(t("guard.laps", { laps: lim.laps }), t("guard.laps.run", { n: facts.turns.repair_laps }))}
      ${rule(t("guard.handover", { n: lim.hand_overs }), t("guard.handover.run", { n: facts.turns.hand_overs_refused }))}</ul>`;
    const row = (what, temple, hall, note = "") => `<tr><th>${esc(what)}</th><td>${esc(temple)}</td><td>${esc(hall)}${note ? `<small>${esc(note)}</small>` : ""}</td></tr>`;
    const fr = like.frame;
    $("how-calibrate").innerHTML = `<h3>${esc(t("cal.title"))}</h3><p>${esc(t("cal.lede"))}</p><table>
      <thead><tr><th>${esc(t("cal.what"))}</th><th>${esc(t("cal.temple"))}</th><th>${esc(t("cal.hall"))}</th></tr></thead><tbody>
      ${row(t("cal.size"), like.size.temple.join(" × "), like.size.hall.join(" × "))}
      ${row(t("cal.top"), like.top.temple, like.top.hall)}
      ${row(t("cal.columns"), t("cal.columns.temple", { n: s.columns.count, top: s.columns.top, d: s.columns.diameter }), t("cal.matched", { m: like.columns.matched, n: like.columns.wanted }))}
      ${row(t("cal.ties"), fr.tie_spans.spans, t("cal.matched", { m: fr.tie_spans.tied, n: fr.tie_spans.spans }))}
      ${row(t("cal.brackets"), fr.bracket_sets.columns, t("cal.matched", { m: fr.bracket_sets.with_a_set, n: fr.bracket_sets.columns }))}
      ${row(t("cal.rings"), s.roof_rings, fr.roof_rings)}
      ${row(t("cal.ridge"), s.ridge.underside, fr.ridge.underside)}
      ${row(t("cal.rafters"), `${s.rafters.size} @ ${s.rafters.spacing}`, `${fr.rafters.size} @ ${fr.rafters.spacing}`,
        s.rafters.spacing < g.spacing_m[0] ? t("cal.rafters.note", { a: s.rafters.spacing, b: fr.rafters.spacing }) : "")}
      ${row(t("cal.outline"), t("cal.outline.need", { x: like.enough }), `${like.outline.front} / ${like.outline.side} / ${like.outline.above}`)}
      </tbody></table>`;
    const w = f.weights, sh = f.shake;
    const vals = {
      inventory: [{}, { n: num(f.inventory.pieces) }],
      bearing: [{}, { n: f.bearing.hanging }],
      weights: [{ mpa: w.allowed_MPa, snow: w.snow.per_m2_kN }, { v: w.heaviest.design_MPa, name: w.heaviest.name, kn: num(w.heaviest.carries_kN), mn: w.total_MN }],
      settle: [{ s: lim.let_go_seconds }, { n: num(f.settle.pieces), sec: f.settle.seconds, fell: f.settle.fell, shifted: f.settle.shifted }],
      shake: [{ g: sh.peak_g, hz: sh.hz, pull: sh.pull_g }, { n: sh.came_down, drift: sh.drift_m }],
      likeness: [{ x: like.enough }, { f: like.outline.front, s: like.outline.side, a: like.outline.above }],
      judge: [{}, { v: f.eyes.verdict }],
    };
    $("how-checks").innerHTML = `<h3>${esc(t("check.title"))}</h3><p>${esc(t("check.lede"))}</p><ol>${facts.checks.map((id, i) => {
      const tool = id.split("/")[1], [line, got] = vals[tool];
      return `<li><i>${i + 1}</i><div><b>${esc(t(`check.${tool}`))}</b><code>${esc(id)}</code><span>${esc(t(`check.${tool}.line`, line))}</span></div>
        <em>${esc(t(`check.${tool}.found`, got))}</em></li>`;
    }).join("")}</ol><small class="sources">${esc(t("check.sources", { snow: w.snow.source.split(",")[0], quake: sh.source.split(":")[0] }))}</small>`;
  }

  return { build: () => { loop(); if (facts.found) how(); }, show: (i) => { flow(chapters[i], i); card(chapters[i], i); } };
}
