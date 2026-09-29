// Pure helpers for the streaming dashboard: when each step appears and how long it types, what the
// big screen shows, what the status line says, which skills have been used. No DOM, so node tests them.

export const SKILLS = ["model-anatomy", "shot-judge", "joint-reveal", "structure-tour", "raise-the-hall", "load-path"];
const TYPED = new Set(["think", "final", "stop"]);
const MS_PER_CHAR = 22;
const MAX_TYPE_MS = 3000;

// How long a step's words take to type at this speed; tool cards appear whole.
export function typeMs(event, speed) {
  if (!speed || !TYPED.has(event.kind)) return 0;
  return Math.min(MAX_TYPE_MS, (event.text || "").length * MS_PER_CHAR) / speed;
}

// How many characters are on screen this many milliseconds into a typing of this length.
export function typedLength(total, elapsed_ms, type_ms) {
  if (!type_ms || elapsed_ms >= type_ms) return total;
  return Math.max(0, Math.floor((elapsed_ms / type_ms) * total));
}

const NOISE = /^(Blender \d|Blender quit|\d\d:\d\d\.\d+\s)/;

// The last lines a tool printed, Blender's own chatter and its per-frame save lines dropped: what
// the card shows as its output; the whole transcript stays behind the card's open button.
const CHATTER = /^(Saved: '|Fra:|Time: |Append frame|Blender \d|Blender quit|Error: Not freed memory|\d\d:\d\d\.\d+\s)|\.png'$/;   // and a save line cut mid-way
export function outputTail(text, n = 4) {
  return String(text || "").split("\n").map((l) => l.trim()).filter((l) => l && !CHATTER.test(l)).slice(-n);
}

// One line for a tool card: the tool's own summary line (ANATOMY 11 pieces ...), else the last
// thing it printed that is not Blender's own chatter, or the error.
export function cardLine(event) {
  const text = String(event.text || "").trim();
  if (event.tool === "read") return `${(event.args || {}).file || ""} \u00b7 ${Math.max(1, Math.round(text.length / 1024))} KB`;   // a file read, not its contents
  const lines = text.split("\n").map((l) => l.trim()).filter((l) => l && !NOISE.test(l));
  const summary = [...lines].reverse().find((l) => /^[A-Z]{3,}\b/.test(l));
  const line = /^exit \d+:/.test(text) ? text.split("\n")[0] : summary || (lines.length ? lines[lines.length - 1] : "");
  return line.length > 96 ? `${line.slice(0, 95)}…` : line;
}

// What the header above the big screen says, from the latest heartbeat and the events so far.
export function statusOf(beat, events) {
  const last = events.length ? events[events.length - 1] : null;
  if (!beat) {
    if (last && (last.kind === "final" || last.kind === "stop")) return { key: last.kind === "final" ? "finished" : "stopped", pct: 100 };
    return { key: events.length ? "thinking" : "idle", pct: null };
  }
  if (beat.phase !== "tool") return { key: "thinking", seconds: beat.seconds, pct: null };
  if (beat.tool === "judge") return { key: "judging", seconds: beat.seconds, pct: null };
  if (beat.expected && beat.frames !== undefined) {
    return { key: "rendering", tool: beat.tool, frames: beat.frames, expected: beat.expected, seconds: beat.seconds,
      pct: Math.min(100, Math.round((beat.frames / beat.expected) * 100)) };
  }
  return { key: "running", tool: beat.tool, seconds: beat.seconds, pct: null };
}

// The six skills with what they have done: done once an act of theirs has run, active while one runs.
export function skillsUsed(events, beat) {
  const done = new Set(events.filter((e) => e.kind === "act" && SKILLS.includes(e.skill)).map((e) => e.skill));
  const active = beat && beat.phase === "tool" ? beat.skill : null;
  return SKILLS.map((skill) => ({ skill, state: skill === active ? "active" : done.has(skill) ? "done" : "todo" }));
}

// What the big screen shows: the frame being painted, else the newest judged picture, else the newest video.
export function bigPicture(events, beat) {
  if (beat && beat.newest) return { src: beat.newest, live: true, verdict: null };
  for (let i = events.length - 1; i >= 0; i -= 1) {
    const e = events[i];
    if (e.kind === "act" && e.picture) {
      const look = events.slice(i + 1).find((r) => r.verdict && (r.kind === "look" || r.tool === "judge"));
      return { src: e.picture, live: false, verdict: look ? look.verdict : null };
    }
  }
  for (let i = events.length - 1; i >= 0; i -= 1) {
    const video = (events[i].files || []).find((n) => /\.mp4$/i.test(n));
    if (video) return { src: video, video: true, live: false, verdict: null };
  }
  return null;
}

// The newest film a run has written, or null: the thing to put large on the screen at the end.
export function newestFilm(events) {
  for (let i = events.length - 1; i >= 0; i -= 1) {
    const video = (events[i].files || []).find((n) => /\.mp4$/i.test(n));
    if (video) return video;
  }
  return null;
}

// A recorded run replayed as if live: each act's tool time shrinks to a few seconds of heartbeats
// (frames counting up, the newest frame painting), each think gets a moment of "thinking…" first.
const FRAMES_IN = /(\d+) frames/;
const REPLAY = { minMs: 2500, maxMs: 20000, divisor: 40, thinkMs: 1800, frameStep: 3 };

// Two paces for a recording. The prompt chips replay it as if live and end on its film; the
// one-press buttons play the same steps briskly, a quarter of a minute for the longest run, and end
// on their film too (FILM_FINALES) or, for a run with none, on the 3D showpiece moving.
export const PACES = {
  replay: { finale: "film" },
  brisk: { minMs: 1500, maxMs: 8000, thinkMs: 1200, finale: "3d" },
  briskFilm: { minMs: 1500, maxMs: 8000, thinkMs: 1200, finale: "film" },
};

// The one-press buttons that end on their film, which loops and stays until another button is pressed.
// Only 拆开来 and 松开手 did at first; the others showed their pictures and then fell back to the
// hall turning in 3D, and the operator wanted the panel to keep what the demonstration made.
export const FILM_FINALES = new Set(["raise", "tour", "explode", "load", "settle"]);

export function replayPlan(events, opts = {}) {
  const o = { ...REPLAY, ...opts };
  const plan = [];
  let at = 0;
  for (const event of events) {
    if (event.kind === "think" || event.kind === "final") {
      plan.push({ at_ms: Math.round(at), beat: { phase: "thinking", seconds: 0 } });
      at += o.thinkMs;
      plan.push({ at_ms: Math.round(at), event });
      at += typeMs(event, 1) + 400;
    } else if (event.kind === "act") {
      const total = (event.seconds || 0) * 1000;
      const span = Math.min(o.maxMs, Math.max(o.minMs, total / o.divisor));
      const found = FRAMES_IN.exec(event.text || "");
      const frames = found ? Number(found[1]) : 0;
      const beats = Math.max(1, Math.round(span / 500));
      for (let i = 0; i < beats; i += 1) {
        const k = i / beats;
        const n = frames ? 1 + Math.floor((k * (frames - 1)) / o.frameStep) * o.frameStep : 0;
        plan.push({ at_ms: Math.round(at + k * span), beat: {
          phase: "tool", skill: event.skill, tool: event.tool, seconds: Math.round(k * (event.seconds || 0)),
          ...(frames ? { frames: n, expected: frames, newest: `${event.tool}/f${String(n).padStart(4, "0")}.png` } : {}) } });
      }
      at += span;
      plan.push({ at_ms: Math.round(at), event });
      at += 600;
    } else {
      plan.push({ at_ms: Math.round(at), event });
      at += 300;
    }
  }
  return plan;
}
