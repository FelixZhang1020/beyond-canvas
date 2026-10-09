// What the harness view shows at a moment in a journey: which step, how far through it, which lap
// round, what is lit, the transcript so far, the console's lines, and the card for a part. Pure,
// so the page can be tested without a DOM.
export const STEP_MS = 2000;   // two seconds a step (operator: four was too slow); space pauses

export function timeline(journey) {
  let at = 0;
  return journey.steps.map((step) => {
    const ms = step.ms || STEP_MS;
    const row = { at, ms };
    at += ms;
    return row;
  });
}

export function stateAt(journey, elapsedMs) {
  const tl = timeline(journey);
  const total = tl.reduce((n, s) => n + s.ms, 0);
  const t = total ? ((elapsedMs % total) + total) % total : 0;
  const lap = total ? Math.floor(Math.max(0, elapsedMs) / total) : 0;
  let index = tl.findIndex((s) => t < s.at + s.ms);
  if (index < 0) index = tl.length - 1;
  return { index, progress: tl.length ? (t - tl[index].at) / tl[index].ms : 0, total, lap };
}

export function litOf(journey, index) {
  const step = journey.steps[index] || {};
  return { station: step.station || null, skill: step.skill || null, wire: step.wire || null, verdict: step.verdict || null };
}

const say = (words, lang) => (words && (words[lang] || words.zh)) || "";

export function linesUpTo(journey, index, lang) {
  return journey.steps.slice(0, index + 1).filter((s) => s.line).map((s) => say(s.line, lang));
}

export function logUpTo(journey, index) {
  return journey.steps.slice(0, index + 1).filter((s) => s.log).map((s) => s.log);
}

export function captionOf(journey, index, lang) { return say((journey.steps[index] || {}).caption, lang); }

// The diagram speaks English whatever the page's language; only the descriptions follow it.
export function cardFor(roster, journey, stationId, index, lang) {
  const station = roster.stations.find((s) => s.id === stationId);
  if (!station) return null;
  const latest = journey.steps.slice(0, index + 1).reverse().find((s) => s.station === stationId);
  return { title: station.name, term: station.common.term, what: say(station.common.what, lang),
    here: say(station.here.what, lang), code: station.here.code.slice(), gap: say(station.gap, lang),
    now: latest ? say(latest.caption, lang) : null };
}
