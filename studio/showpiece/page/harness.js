import { buildBoard, lightBoard, moveDot } from "./harnessboard.mjs";
import { STEP_MS, timeline, stateAt, litOf, linesUpTo, logUpTo, cardFor, captionOf } from "./harnessplay.mjs";

// The harness view: one board of the harness's parts, named by their general terms; a
// button per skill this system can run; press one and its request travels the board, a caption
// explaining each stop, a card for any part. Nothing here runs a model: the journeys are checked
// data, and the page says so in its footnote. The rail is a console of the journey's own log.
let T = { zh: {} }, roster = null, journeys = [];
// `lang` stays as the constant "zh": the words are looked up by it and the document is labelled
// with it. Nothing can change it -- this page used to carry a CN/EN button, and what it
// chose was kept in this browser, so one press left the page in English on every later visit.
const state = { lang: "zh", journey: null, playing: false, t0: 0, paused: 0, index: -1, pinned: null };
const t = (key, n, m) => String((T[state.lang] && T[state.lang][key]) || key).replace("{n}", n).replace("{m}", m);
const $ = (id) => document.getElementById(id);
const still = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
const say = (words) => (words && (words[state.lang] || words.zh)) || "";
const journey = () => journeys.find((j) => j.id === state.journey) || null;
const skillOf = (j) => j.skill || j.id;          // a journey is its skill's, unless it names one (collapse runs load-path)
const elapsed = () => (state.playing ? performance.now() - state.t0 : state.paused);

function el(tag, attrs = {}, ...children) {
  const node = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs)) { if (k === "class") node.className = v; else node.setAttribute(k, v); }
  for (const c of children) node.append(c instanceof Node ? c : document.createTextNode(String(c)));
  return node;
}
const clock = (ms) => { const s = Math.max(0, Math.floor(ms / 1000)); return `${Math.floor(s / 60)}:${String(s % 60).padStart(2, "0")}`; };

function rail() {
  return el("section", { class: "panel console hv-console" },
    el("div", { class: "chead" }, el("b", {}, t("console")), el("span", { class: "clock", id: "console-clock" }, "0:00")),
    el("div", { class: "cbody" },
      el("div", { class: "part" }, el("div", { class: "sect" }, "parts"), el("div", { class: "hv-parts", id: "parts" })),
      el("div", { class: "part" }, el("div", { class: "sect" }, "log"), el("div", { class: "log", id: "log" }))));
}

function shell() {
  $("app").replaceChildren(
    el("div", { class: "wrap hv-wrap" },
      el("header", { class: "head" },
        el("h1", {}, t("title"), el("small", {}, t("sub"))),
        el("div", { class: "hv-links" }, el("button", { class: "ghost", id: "play", disabled: "" }, t("play")),
          el("span", { class: "meta", id: "stepno" }, ""))),
      el("section", { class: "hv-buttons" },
        el("div", { class: "hv-row", role: "group" }, ...journeys.map((j) => el("button", { class: `ghost${j.id === state.journey ? " on" : ""}`, id: `go-${j.id}` }, say(j.label), el("small", {}, skillOf(j))))),
        el("p", { class: "hint" }, t("hint"))),
      el("div", { class: "stage hv-stage" },
        el("aside", { class: "rail" }, rail()),
        el("section", { class: "panel hv-panel" },
          el("div", { class: "hv-boardwrap" },
            el("div", { class: "hv-boardcol" },
              buildBoard(roster, { onPin: pin, tooltip: (s) => say(s.here.what), label: t("title") }),
              el("p", { class: "hv-caption", id: "caption" }, ""), el("div", { class: "hv-ledger", id: "lines" })),
            el("div", { class: "hv-card", id: "card" })),
          el("p", { class: "hv-honest" }, t("honest"))))));
  window.Backstage?.attach(document.querySelector(".rail .console"));
  for (const j of journeys) $(`go-${j.id}`).onclick = () => start(j.id);
  $("play").onclick = toggle;
}

function start(id) {                                  // pressing the running journey's button starts it over
  state.journey = id; state.pinned = null; state.t0 = performance.now(); state.paused = 0; state.index = -1; state.playing = true;
  for (const j of journeys) $(`go-${j.id}`).classList.toggle("on", j.id === id);
  $("play").disabled = false;
  $("play").textContent = t("pause");
  paint(true);
}
function pin(id) { state.pinned = state.pinned === id ? null : id; paint(true); }
function toggle() {
  if (!journey()) return;
  if (state.playing) state.paused = performance.now() - state.t0; else state.t0 = performance.now() - state.paused;
  state.playing = !state.playing;
  $("play").textContent = t(state.playing ? "pause" : "play");
  paint(true);
}
function seek(ms) { state.playing = false; state.paused = ms; $("play").textContent = t("play"); paint(true); }

function paint(force) {
  const j = journey();
  if (!j) { if (force) idle(); return; } // Idle DOM changes only on boot, language or pin changes.
  const { index, progress, total, lap } = stateAt(j, elapsed());
  const lit = litOf(j, index);
  if (!lit.skill) lit.skill = skillOf(j);           // the journey's own skill stays lit unless a step names another
  moveDot(lit.wire, progress, still);
  if (index === state.index && !force) return;
  state.index = index;
  if (window.Backstage) window.Backstage.activity = {label: "Harness · 演示", detail: `${say(j.label)} · ${index + 1}/${j.steps.length} · ${captionOf(j, index, state.lang)}`};
  lightBoard(roster, lit, state.pinned);
  $("caption").replaceChildren(el("b", {}, t("now")), captionOf(j, index, state.lang));
  $("lines").replaceChildren(...linesUpTo(j, index, state.lang).map((line) => el("p", {}, line)));
  $("stepno").textContent = t("step", index + 1, j.steps.length);
  card(j, lit, index);
  const tl = timeline(j);
  $("console-clock").textContent = clock(elapsed() - lap * total);   // the clock restarts with every lap, so the log and the board agree
  const touched = new Set(j.steps.slice(0, index + 1).map((s) => s.station));
  window.Backstage?.context({label:'Harness · 演示', skill:skillOf(j),
    status:state.playing ? 'playing' : 'paused', done:true, mode:'simulation',
    parts:Object.fromEntries(roster.stations.map(s => [s.id, s.id === lit.station ? 'current' : touched.has(s.id) ? 'visited' : 'not_started'])),
    processes:[...touched].map(id => roster.stations.find(s => s.id === id)).map(s => ({name:s.name,
      status:s.id === lit.station ? 'current' : 'visited', seconds:null,
      events:j.steps.slice(0,index+1).filter(step => step.station === s.id).length}))});
  $("parts").replaceChildren(...roster.stations.map((s) => el("p", { class: s.id === lit.station ? "lit" : touched.has(s.id) ? "done" : "" }, s.name)));
  const logs = j.steps.slice(0, index + 1).filter((s) => s.log).map((s, i, all) => ({ at: tl[j.steps.indexOf(s)].at, text: s.log, cur: i === all.length - 1 }));
  $("log").replaceChildren(...logs.map((l) => el("p", { class: l.cur ? "cur" : "" }, el("span", { class: "t" }, `+${clock(l.at)}`), " ", l.text)));
  $("log").scrollTop = $("log").scrollHeight;
}

function idle() {
  window.Backstage?.context({label:'Harness · 演示', status:'idle', done:true, mode:'simulation',
    parts:Object.fromEntries(roster.stations.map(s => [s.id, 'not_started']))});
  lightBoard(roster, {}, state.pinned);
  $("caption").replaceChildren(el("b", {}, t("now")), t("idle"));
  $("lines").replaceChildren(); $("stepno").textContent = "";
  $("parts").replaceChildren(...roster.stations.map((s) => el("p", {}, s.name)));
  $("log").replaceChildren(el("p", { class: "cur" }, el("span", { class: "t" }, "+0:00"), " ", t("idle")));
  card(null, { station: state.pinned }, -1);
}

function card(j, lit, index) {
  const id = state.pinned || lit.station;
  const c = id && j ? cardFor(roster, j, id, index, state.lang) : id ? cardFor(roster, { steps: [] }, id, -1, state.lang) : null;
  const box = $("card");
  box.className = `hv-card${state.pinned ? " pinned" : ""}`;
  if (!c) { box.replaceChildren(el("p", { class: "hint" }, t("card.hint"))); return; }
  box.replaceChildren(el("h3", {}, c.title),
    el("p", { class: "k" }, t("card.common")), el("p", { class: "idea" }, el("b", {}, c.term), " · ", c.what),
    el("p", { class: "k" }, t("card.here")), el("p", { class: "idea" }, c.here), ...c.code.map((path) => el("code", {}, path)),
    el("p", { class: "k" }, t("card.gap")), el("p", { class: "gap" }, c.gap),
    el("p", { class: "now" }, el("b", {}, `${t("card.now")} `), c.now || "–"), el("p", { class: "hint" }, t("card.hint")));
}

// Keys: 1 to 9 start a journey, space plays or pauses, the arrows step, Escape releases a pinned card.
function keys(e) {
  if (["BUTTON", "A", "TEXTAREA", "INPUT"].includes(e.target.tagName) || (e.target.closest && e.target.closest(".station"))) return;
  const n = Number(e.key);
  if (n >= 1 && n <= journeys.length) { start(journeys[n - 1].id); return; }
  const j = journey();
  if (!j) return;
  if (e.key === " ") { e.preventDefault(); toggle(); }
  else if (e.key === "Escape") { state.pinned = null; paint(true); }
  else if (e.key === "ArrowRight" || e.key === "ArrowLeft") {
    const count = j.steps.length, { index } = stateAt(j, elapsed());
    const next = (index + (e.key === "ArrowRight" ? 1 : count - 1)) % count;
    seek(j.steps.slice(0, next).reduce((ms, st) => ms + (st.ms || STEP_MS), 0));
  }
}
function tick() { paint(false); requestAnimationFrame(tick); }
async function boot() {
  const names = ["harness-strings.json", "harness-roster.json", "harness-journeys.json"];
  [T, roster, journeys] = await Promise.all(names.map((n) => fetch(n).then((r) => r.json())));
  document.documentElement.lang = state.lang;
  shell(); paint(true);
  document.addEventListener("keydown", keys);
  if (still) setInterval(() => paint(false), 500); else tick();   // reduced motion: the steps still change, nothing glides
}
boot();
