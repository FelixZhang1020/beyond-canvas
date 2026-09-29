// The backend monitor's pure state: which component is working now, which link carries the
// hand-off, and the running counts. Nodes and links are fixed; what lights up comes from the
// latest heartbeat and the events so far. No DOM, so node tests it.

export const NODES = ["prompt", "driver", "model", "skill", "blender", "ffmpeg", "judge", "screen"];
export const LINKS = [["prompt", "driver"], ["driver", "model"], ["model", "driver"], ["driver", "skill"], ["skill", "blender"],
  ["blender", "ffmpeg"], ["ffmpeg", "screen"], ["blender", "screen"], ["driver", "judge"], ["judge", "screen"], ["skill", "screen"]];
export const RENDERS = new Set(["explode", "tour", "raise", "flow", "settle", "closeup"]);
const VIDEOS = new Set(["explode", "tour", "raise", "flow", "settle"]);

// The lit nodes and the active link for a heartbeat, or for the last event when there is none.
export function activity(beat, events) {
  const last = events.length ? events[events.length - 1] : null;
  if (beat && beat.phase === "thinking") return { lit: ["driver", "model"], link: ["driver", "model"], label: "model" };
  if (beat && beat.phase === "tool") {
    if (beat.tool === "judge") return { lit: ["driver", "judge"], link: ["driver", "judge"], label: "judge" };
    if (RENDERS.has(beat.tool)) return { lit: ["skill", "blender", "screen"], link: ["blender", "screen"], label: beat.tool, skill: beat.skill };
    return { lit: ["driver", "skill", "blender"], link: ["skill", "blender"], label: beat.tool, skill: beat.skill };
  }
  if (!last) return { lit: [], link: null, label: null };
  if (last.kind === "act" && VIDEOS.has(last.tool)) return { lit: ["ffmpeg", "screen"], link: ["ffmpeg", "screen"], label: "ffmpeg" };
  if (last.kind === "act") return { lit: ["skill", "screen"], link: ["skill", "screen"], label: last.tool, skill: last.skill };
  if (last.kind === "look") return { lit: ["judge", "screen"], link: ["judge", "screen"], label: "judge" };
  if (last.kind === "final" || last.kind === "stop") return { lit: ["screen"], link: null, label: last.kind };
  return { lit: ["model", "driver"], link: ["model", "driver"], label: "model" };
}

// Running totals a visitor can read at a glance.
export function tallies(events) {
  let tokens = 0, toolSeconds = 0, acts = 0, judged = 0, passed = 0, frames = 0;
  for (const e of events) {
    tokens += e.tokens || 0;
    if (e.kind === "act") { acts += 1; toolSeconds += e.seconds || 0; const m = /(\d+) frames/.exec(e.text || ""); if (m) frames += Number(m[1]); }
    if (e.kind === "look") { judged += 1; if (e.verdict && e.verdict.verdict === "pass") passed += 1; }
  }
  return { tokens, toolSeconds: Math.round(toolSeconds), acts, judged, passed, frames };
}

// Frames rendered per second right now, from two heartbeats of the same tool.
export function frameRate(prev, beat) {
  if (!prev || !beat || prev.tool !== beat.tool || beat.frames === undefined || prev.frames === undefined) return null;
  const dt = (beat.seconds || 0) - (prev.seconds || 0);
  return dt > 0 ? Math.max(0, (beat.frames - prev.frames) / dt) : null;
}

// A short history for a sparkline: the last `keep` samples, newest last.
export function push(history, value, keep = 90) {
  const out = history.concat([value === null || value === undefined ? null : value]);
  return out.length > keep ? out.slice(out.length - keep) : out;
}

export function sparkPath(values, width, height) {
  const known = values.filter((v) => typeof v === "number");
  if (known.length < 2) return "";
  const max = Math.max(1e-9, ...known);
  const step = width / Math.max(1, values.length - 1);
  return values.map((v, i) => (typeof v === "number" ? `${i ? "L" : "M"}${(i * step).toFixed(1)},${(height - (v / max) * height).toFixed(1)}` : ""))
    .filter(Boolean).join(" ").replace(/^L/, "M");
}
