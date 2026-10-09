// Pure helpers for the showpiece dashboard: no DOM, so node can test them.

export function chip(kind, verdict) {
  const tone = kind === "act" ? "clay"
    : kind === "look" ? (verdict && verdict.verdict === "pass" ? "olive" : "rust")
    : kind === "final" ? "olive"
    : kind === "stop" ? "rust"
    : "slate";
  return { label: kind, tone };
}

function judges(e) {
  return Boolean(e.verdict) && (e.kind === "look" || (e.kind === "act" && e.tool === "judge"));
}

// The act whose picture the next verdict belongs to: the latest act with a picture that no
// judge has looked at yet. Null when every picture so far has its verdict.
export function unjudgedPicture(events) {
  let step = null;
  for (const e of events) {
    if (e.kind === "act" && e.picture) step = e.step;
    else if (judges(e)) step = null;
  }
  return step;
}

export function reduce(events) {
  const rows = events.map((e) => ({ ...e, verdict: e.verdict || null }));
  let pending = null;
  for (const r of rows) {
    if (r.kind === "act" && r.picture) { r.verdict = null; pending = r; }
    else if (judges(r) && pending) { pending.verdict = r.verdict; pending = null; }
  }
  const seen = new Set();
  const gallery = [];
  for (const e of events) {
    for (const name of e.files || []) {
      if (/\.(png|jpe?g|mp4)$/i.test(name) && !seen.has(name)) {
        seen.add(name);
        gallery.push({ name, video: /\.mp4$/i.test(name), step: e.step });
      }
    }
  }
  gallery.sort((a, b) => b.step - a.step || a.name.localeCompare(b.name));
  return { rows, gallery, verdicts: rows.filter((r) => r.kind === "look").map((r) => r.verdict) };
}

// A long tool printout keeps its last lines; the rest waits behind a "show all" button.
export function fold(text, keep = 6) {
  const whole = String(text || "");
  const lines = whole.split("\n");
  if (lines.length <= keep + 2) return { shown: whole, hidden: 0 };
  return { shown: lines.slice(-keep).join("\n"), hidden: lines.length - keep };
}

