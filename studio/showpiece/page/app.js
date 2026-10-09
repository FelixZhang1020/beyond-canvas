import { makePlayer } from "./player.mjs";
import { makeScreen } from "./screen.mjs";
import { makeConsole } from "./console.mjs";
import { PACES, FILM_FINALES } from "./stream.mjs";

// All words the page shows come from strings.json, which holds Chinese only; nothing is hard-coded here.
// The runs are fetched for the buttons and the chips; a demonstration lists no history and keeps no gallery.
// A demonstration in three parts: one-press buttons that play a recorded temple run step by step,
// briskly, ending on its 3D showpiece; prompt chips that replay a recorded run as if live, ending
// on its film; and the backend console, always on.
// The conversation on the left and the agent's screen on the right serve all three; typing a
// prompt of your own still runs the agent for real.
let T = { zh: {} };
// `lang` stays as the constant "zh" because the words are looked up by it and the document is
// labelled with it. Nothing can change it: this page used to carry a CN/EN button, and
// what it chose was kept in this browser, so one press left the page in English on every later
// visit until somebody pressed it back. Chinese everywhere is the operator's decision.
const state = { lang: "zh", run: null, source: null, started: null, runs: [], kind: "demo", request: "" };
const KINDS = ["demo", "prompts", "live", "rebuild"];   // the kinds of control above the conversation, one on show at a time
const DEMOS = ["raise", "tour", "explode", "load", "settle"];
const t = (key, n) => {
  const text = (T[state.lang] && T[state.lang][key]) || key;
  return n === undefined ? text : String(text).replace("{n}", n);
};
const $ = (id) => document.getElementById(id);
// A model's readable name for the header, from strings.json; a name it does not list is shown as it is.
const named = (kind, raw) => ((T[state.lang] || {})[`${kind}.names`] || {})[raw] || raw;

function el(tag, attrs = {}, ...children) {
  const node = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs)) {
    if (k === "class") node.className = v; else node.setAttribute(k, v);
  }
  for (const c of children) node.append(c instanceof Node ? c : document.createTextNode(String(c)));
  return node;
}

// The switch above the conversation: which kind of control is on show, and what pressing one does.
function setKind(kind) {
  state.kind = kind;                               // not remembered: the stage always opens on the one-press buttons
  for (const k of KINDS) {
    if ($(`row-${k}`)) $(`row-${k}`).hidden = k !== kind;
    $(`seg-${k}`).classList.toggle("on", k === kind);
    $(`seg-${k}`).setAttribute("aria-pressed", k === kind ? "true" : "false");
  }
  $("ask-hint").textContent = t(`${kind}.hint`);
  showReplay(kind === "rebuild");
}

// The from-nothing kind: the replay of the from-nothing build (rebuild.html), a page of its own, shown in place of the
// console, the conversation and the screen (operator). Left, it is unloaded, so its 3D and its
// playback never run behind the other kinds; its URL stays relative, as every URL on this page must.
function showReplay(on) {
  document.querySelector(".stage").classList.toggle("replaying", on);
  const frame = $("replay-frame"), now = frame.getAttribute("src") || "";
  if (on && !now.startsWith("rebuild.html")) frame.setAttribute("src", "rebuild.html");
  if (!on && now !== "about:blank") frame.setAttribute("src", "about:blank");
  fitReplay();
}

// Where the replay is one column (a phone, an iPad either way: its frame 1,100 px or narrower) it is one long page,
// and in a frame of the screen's height it scrolled apart from this one, its hall below the frame's fold (operator:
// "从零盖殿 still bad in iPad and iPhone"). There the frame takes the replay's whole height and the page scrolls as one.
// Wider, the replay is one screen and fills the stage as before.
// The height is the replay's body, which grows as its attempts load after the page does; the document's own height
// never reads less than the frame, so the frame could grow and never shrink back. The body is watched from the
// replay's own window: an observer made here never saw layout inside the frame.
let replayWatch = null;
function fitReplay() {
  const frame = $("replay-frame"), body = frame.contentDocument?.body;
  const tall = document.querySelector(".stage").classList.contains("replaying") && frame.clientWidth <= 1100 && !!body;
  document.documentElement.classList.toggle("replay-tall", tall);
  frame.style.height = tall ? `${Math.ceil(body.getBoundingClientRect().height)}px` : "";
}
function watchReplay() {
  replayWatch?.disconnect();
  const win = $("replay-frame").contentWindow, body = win?.document?.body;
  if (body && win.ResizeObserver) { replayWatch = new win.ResizeObserver(fitReplay); replayWatch.observe(body); }
  fitReplay();
}

function fileUrl(name) { return `api/runs/${state.run}/files/${name.split("/").map(encodeURIComponent).join("/")}`; }

const screen = makeScreen({ el, t, $, fileUrl, onView: () => refresh() });
const ops = makeConsole({ el, t, $ });
const elapsed = () => (state.started ? (Date.now() - state.started) / 1000 : 0);
const player = makePlayer({ el, t, $, fileUrl, onChange: refresh, onDraw: (event) => ops.note(event, elapsed()) });

function refresh() {
  const { events, shown, beat, following, replayed, done } = player.st;
  const seen = events.slice(0, shown);
  if (window.Backstage) window.Backstage.activity = state.run ? {label: state.recorded ? t("recorded") : t("seg.live"), detail: `${shown} ${t("steps")}`} : null;
  screen.update(seen, following ? beat : null, replayed);
  player.indicator(following ? beat : null);
  $("replay-btn").hidden = !(done && events.length);   // a finished run can be watched again, at no cost
  ops.update({ beat: following ? beat : null, events: seen, elapsed: elapsed() });
  window.Backstage?.context({label:state.recorded ? t('recorded') : t('seg.live'), skill:'showpiece',
    status:following && beat ? beat.phase : done ? 'done' : 'idle', done:!following || done,
    parts:{request:state.run ? 'received' : '—', loop:following && beat ? beat.phase : 'idle',
      tools:String(seen.filter(e => e.kind === 'act').length),
      skills:[...new Set(seen.map(e => e.skill).filter(Boolean))].join(', ') || '—',
      evals:String(seen.filter(e => e.kind === 'look').length)}});
  $("count").textContent = `${shown} ${t("steps")}`;
}

function renderShell() {
  document.documentElement.lang = state.lang;
  $("app").replaceChildren(
    el("div", { class: "wrap" },
      el("header", { class: "head" },
        el("div", { class: "head-top" },                   // one row (operator): the title, the switch in the middle, the links
          el("div", { class: "head-title" }, el("h1", {}, t("title"))),
          el("div", { class: "seg", role: "group" }, ...KINDS.map((k) => el("button", { class: "ghost", id: `seg-${k}`, "aria-pressed": "false" }, t(k === "live" ? "seg.live" : k)))),
          el("nav", { class: "head-links" },
            el("a", { class: "ghost", href: "/" }, t("studio.link")),
            el("button", { class: "ghost", id: "harness" }, t("harness.link"))),   // the standalone page that explains the harness
          el("p", { class: "who" }, el("b", { id: "agent" }, t("agent.default")), ` ${t("sub")} · `,   // one short line under the row
            el("b", { id: "model" }, "-")))),
      el("div", { class: "stage" },
        el("aside", { class: "rail" }, ops.build()),         // the backend: the console
        el("div", { class: "centre" },                       // what to press, and the conversation under it
          el("section", { class: "ask" },
            el("div", { class: "demos", id: "row-demo" }, el("div", { class: "demos", id: "demos" })),
            el("div", { class: "presets", id: "row-prompts" }, el("div", { class: "presets", id: "presets" })),
            el("div", { class: "presets", id: "row-live" }),
            el("p", { class: "hint", id: "ask-hint" }, "")),
          el("section", { class: "panel talk" },
            el("div", { class: "controls" }, el("h2", {}, t("conversation")), el("span", { id: "count", class: "meta" }, "")),
            el("div", { class: "timeline", id: "timeline" }, el("p", { class: "empty" }, t("empty"))),
            el("button", { class: "newer", id: "newer", hidden: "" }, t("newer"))),
          el("iframe", { class: "replay-frame", id: "replay-frame", title: t("rebuild") })),
        screen.build())));                                   // the agent's screen: the output
  $("replay-frame").addEventListener("load", watchReplay);
  window.addEventListener("resize", fitReplay);
  window.Backstage?.attach(document.querySelector(".rail .console"));
  for (const item of t("live.items") || []) {          // real runs on the hall, marked live, one chip each
    const chip = el("button", { class: "live", title: item.note ? `${item.request}\n${item.note}` : item.request },
      el("i", { class: "live-dot" }), el("span", { class: "live-word" }, t("live")), item.label, el("small", {}, t("live.minutes", item.minutes)));
    chip.onclick = () => startRun(item.request);
    $("row-live").append(chip);
  }
  for (const k of KINDS) $(`seg-${k}`).onclick = () => setKind(k);
  setKind(state.kind);
  $("harness").onclick = () => { location.href = "/harness"; };
  screen.wire();
  $("replay-btn").onclick = () => player.replay(player.st.events);
  $("newer").onclick = () => { player.toBottom(); $("newer").hidden = true; };
  $("timeline").addEventListener("scroll", () => {
    player.st.glued = player.atBottom();             // scrolling up unglues the box; reaching the bottom glues it again
    if (player.st.glued) $("newer").hidden = true;
  }, { passive: true });
}

// The one-press demonstrations, a recorded temple run played step by step at the brisk pace, by their short
// names; and the same five in the prompt row by the whole sentence each was asked in, replayed as if live.
// Each row shows its own thing (operator: three rows of the same five names read as one).
function renderDemos() {
  const box = $("demos"), prompts = $("presets");
  box.replaceChildren(); prompts.replaceChildren();
  for (const kind of DEMOS) {
    const run = state.runs.find((r) => r.recorded && r.showpiece === kind);
    if (!run) continue;
    const b = el("button", {}, t(`demo.${kind}`));
    b.onclick = () => follow(run.id, true, run.model, FILM_FINALES.has(kind) ? "briskFilm" : "brisk");
    box.append(b);
    const p = el("button", { class: "prompt" }, `「${run.request}」`);
    p.onclick = () => follow(run.id, true, run.model, "replay");
    prompts.append(p);
  }
}

async function pollStats() {
  try { ops.stats(await (await fetch("api/stats")).json()); } catch (e) { /* the exhibit may be busy */ }
}

function tickClock() {
  if (!state.started || !$("clock") || player.st.done) return;
  const s = Math.floor((Date.now() - state.started) / 1000);
  $("clock").textContent = `${Math.floor(s / 60)}:${String(s % 60).padStart(2, "0")}`;
}

// How a finished run is shown: "instant" all at once, else played step by step at a pace of
// stream.mjs, "brisk" for the buttons and "replay" for the chips.
function follow(runId, finished, model, how) {
  if (state.source) state.source.close();
  state.run = runId; state.started = Date.now();
  const known = state.runs.find((r) => r.id === runId) || {};
  screen.setRun({ id: runId, model: model || known.model || "", recorded: Boolean(known.recorded) });
  state.request = known.request || state.request;
  ops.setRun({ request: state.request });
  $("model").textContent = named("model", model || known.model) || "-";
  $("newer").hidden = true;
  player.reset([], finished, state.request);
  refresh();
  const buffered = [];
  const source = new EventSource(`api/runs/${runId}/events`);
  state.source = source;
  source.addEventListener("step", (m) => {
    const event = JSON.parse(m.data);
    if (finished) buffered.push(event); else player.push(event);
  });
  source.addEventListener("busy", (m) => { if (!finished) player.beat(JSON.parse(m.data)); });
  source.addEventListener("done", () => {
    source.close();
    if (finished) {
      player.reset(buffered, true, state.request);
      if (how === "instant") player.showUpTo(buffered.length);
      else player.replay(buffered, PACES[how] || PACES.replay);
    } else {
      player.st.done = true;
      player.st.replayed = true;                     // a live run's finale: its film goes large, as a replay's does
      player.beat(null);
    }
    loadRuns();
  });
}

// A showpiece, not a prompt box (operator): a live run starts only from one of the chips.
async function startRun(request) {
  const r = await fetch("api/runs", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ request }) });
  const answer = await r.json();
  if (!r.ok) {                                       // a machine with no Blender plays demos only
    $("ask-hint").textContent = t(answer.code === "no_blender" ? "live.elsewhere" : "live.failed");
    return;
  }
  const { id, model } = answer;
  state.request = request;
  follow(id, false, model);
  loadRuns();
}

async function loadRuns() {
  const { runs } = await (await fetch("api/runs")).json();
  state.runs = runs;
  renderDemos();
  if (runs.length && !state.run) follow(runs[0].id, runs[0].done, runs[0].model, runs[0].recorded ? "instant" : undefined);
  const live = runs.find((r) => !r.recorded);
  if (live) $("agent").textContent = named("agent", live.agent) || "-";
}

// Escape leaves the theatre.
function keys(e) {
  if (e.key === "Escape") screen.setTheatre(false);
}

async function boot() {
  try { T = await (await fetch("strings.json")).json(); } catch (e) { /* the page still works with keys as labels */ }
  renderShell();
  renderDemos();                 // the static rebuild replay is ready even if the runs API is busy
  window.addEventListener("keydown", keys);
  await loadRuns();
  pollStats();
  setInterval(pollStats, 2000);
  setInterval(tickClock, 1000);
}

boot();
