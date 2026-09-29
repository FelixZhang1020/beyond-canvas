// Pure helpers behind the console on the rail: block bars for the machine, the components and
// the six skills as a process table, the pipeline as a tree, and one log line per step or
// heartbeat. No DOM, so node tests them.
import { SKILLS, cardLine } from "./stream.mjs";
import { activity, tallies, RENDERS } from "./flow.mjs";

const BLOCKS = "▁▂▃▄▅▆▇█";

export function blockBar(pct, width = 20) {
  const n = pct === null || pct === undefined ? 0 : Math.round((Math.min(100, Math.max(0, pct)) / 100) * width);
  return "█".repeat(n) + "░".repeat(width - n);
}

export function sparkBlocks(values, width = 16) {
  const known = values.filter((v) => typeof v === "number").slice(-width);
  if (!known.length) return "";
  const max = Math.max(1e-9, ...known);
  return known.map((v) => BLOCKS[Math.min(7, Math.floor((v / max) * 7.999))]).join("");
}

export function clock(seconds) {
  const s = Math.max(0, Math.floor(seconds || 0));
  return `${Math.floor(s / 60)}:${String(s % 60).padStart(2, "0")}`;
}

export function tokensText(n) { return !n ? "\u2013" : n >= 1000 ? `${(n / 1000).toFixed(1)}k tok` : `${n} tok`; }   // a recording carries no token count

const cut = (s, n) => (s && s.length > n ? `${s.slice(0, n - 1)}…` : s || "");
const secondsOf = (list) => Math.round(list.reduce((s, e) => s + (e.seconds || 0), 0));

// The components and the six skills, one row each: name, state, time, calls; a busy row lights.
export function processRows(events, beat, elapsed) {
  const acts = events.filter((e) => e.kind === "act");
  const last = events[events.length - 1];
  const finished = Boolean(last && (last.kind === "final" || last.kind === "stop"));
  const thinking = Boolean(beat && beat.phase === "thinking");
  const tooling = Boolean(beat && beat.phase === "tool" && beat.tool !== "judge");
  const rendering = Boolean(tooling && beat.expected && beat.frames !== undefined);
  const renders = acts.filter((e) => RENDERS.has(e.tool));
  const c = tallies(events);
  const rows = [
    { name: "driver", sub: "studio.showpiece", state: beat ? "busy" : finished ? "done" : "idle", time: clock(elapsed), calls: acts.length, busy: Boolean(beat) },
    { name: "step-3.7-flash", sub: "stepfun", state: thinking ? "thinking" : "idle", time: tokensText(c.tokens),
      calls: events.filter((e) => e.kind === "think" || e.kind === "final").length, busy: thinking },
    { name: "blender", sub: "5.2 · eevee", state: rendering ? `${beat.frames}/${beat.expected}` : tooling ? "running" : "idle",
      time: tooling ? `${Math.round(beat.seconds || 0)} s` : `${secondsOf(renders)} s`, calls: renders.length, busy: tooling },
    { name: "ffmpeg", sub: "encode", state: "idle", time: "–", calls: acts.filter((e) => (e.files || []).some((f) => /\.mp4$/i.test(f))).length, busy: false },
  ];
  for (const skill of SKILLS) {
    const mine = acts.filter((e) => e.skill === skill);
    const active = Boolean(beat && beat.phase === "tool" && beat.skill === skill);
    rows.push({ name: skill, skill: true, state: active ? `▶ ${beat.tool}` : mine.length ? "done" : "–",
      time: active ? `${Math.round(beat.seconds || 0)} s` : mine.length ? `${secondsOf(mine)} s` : "–", calls: mine.length, busy: active });
  }
  return rows;
}

// The pipeline as a tree, the branch the work is on lit.
export function treeLines(events, beat, request) {
  const a = activity(beat, events);
  const lit = new Set(a.lit);
  const c = tallies(events);
  const acts = events.filter((e) => e.kind === "act");
  const newest = acts.length ? acts[acts.length - 1] : null;
  const skill = a.skill || (newest ? newest.skill : null);
  const tool = beat && beat.phase === "tool" ? beat.tool : newest ? newest.tool : null;
  const frames = beat && beat.frames !== undefined ? `${beat.frames}/${beat.expected}` : c.frames ? `${c.frames} frames` : "";
  const video = [...acts].reverse().flatMap((e) => e.files || []).find((f) => /\.mp4$/i.test(f)) || "…";
  const frame = beat && beat.newest ? beat.newest.split("/").pop() : ([...acts].reverse().find((e) => e.picture) || {}).picture || "…";
  return [
    { text: `prompt  ${cut(request, 20)}`, lit: lit.has("prompt") },
    { text: "└─ driver", lit: lit.has("driver") },
    { text: `   ├─ step-3.7-flash  ${tokensText(c.tokens)}`, lit: lit.has("model") },
    { text: `   ├─ skill/${skill || "…"}`, lit: lit.has("skill") },
    { text: `   │  └─ blender ${tool || ""}  ${frames}`.replace(/\s+$/, ""), lit: lit.has("blender") },
    { text: `   │     └─ ffmpeg → ${video}`, lit: lit.has("ffmpeg") },
    { text: `   ├─ shot-judge  ${c.passed}/${c.judged}`, lit: lit.has("judge") },
    { text: `   └─ screen  ${frame}`, lit: lit.has("screen") },
  ];
}

// One log line for a step, and the live line for a heartbeat.
export function logLine(event) {
  if (event.kind === "think") return { who: "model", text: cut(event.text, 72), tone: "" };
  if (event.kind === "act") {
    if (event.tool === "read") return { who: "driver", text: `read ${(event.args || {}).file || ""}`, tone: "" };
    return { who: event.skill || event.tool, text: `${event.tool}  ${cardLine(event)}${event.seconds ? ` · ${event.seconds} s` : ""}`,
      tone: /^exit \d/.test(event.text || "") ? "warn" : "ok" };
  }
  if (event.kind === "look") {
    const v = event.verdict;
    return { who: "judge", text: v ? `${v.verdict}  ${cut(v.seen, 60)}` : cut(event.text, 60), tone: v && v.verdict === "pass" ? "ok" : "warn" };
  }
  if (event.kind === "final") return { who: "answer", text: cut(event.text, 72), tone: "ok" };
  if (event.kind === "stop") return { who: "driver", text: `stop  ${cut(event.text, 60)}`, tone: "warn" };
  return { who: event.kind, text: cut(event.text, 72), tone: "" };
}

export function beatLine(beat) {
  if (!beat) return null;
  const s = Math.round(beat.seconds || 0);
  if (beat.phase === "thinking") return { who: "model", text: `thinking · ${s} s` };
  if (beat.tool === "judge") return { who: "judge", text: `looking at the picture · ${s} s` };
  if (beat.expected && beat.frames !== undefined) return { who: "blender", text: `${beat.tool} frame ${beat.frames}/${beat.expected} · ${s} s` };
  return { who: beat.skill || "tool", text: `${beat.tool} running · ${s} s` };
}
