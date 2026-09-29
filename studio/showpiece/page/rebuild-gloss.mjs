// One plain line of Chinese for what the harness answered at a step, read from the answer itself: the
// line a tool printed, a tool's own refusal, or an argument it could not read. The English stays on
// the page as the evidence; this only says what it means. A shape not listed here gets no line.
const num = (v) => Number(v).toLocaleString("en-US");
const parts = (list, t) => list.split(/, | and /).map((p) => t(`part.${p.trim()}`)).join(t("part.sep"));

const SHAPES = [
  [/^REFUSED there is no standing temple/, "bad", () => ["gloss.no.temple", {}]],
  [/^REFUSED spacing ([\d.]+) is out of range; give between ([\d.]+) and ([\d.]+)/, "bad", (m) => ["gloss.refused.spacing", { x: m[1], a: m[2], b: m[3] }]],
  [/^REFUSED (\w+) ([\d.]+) is not a timber's size in metres; give between ([\d.]+) and ([\d.]+)/, "bad",
    (m, t) => ["gloss.refused.size", { what: t(`param.${m[1]}`) === `param.${m[1]}` ? m[1] : t(`param.${m[1]}`), x: m[2], a: m[3], b: m[4] }]],
  [/error: the following arguments are required: (\S+)/, "bad", (m) => ["gloss.required", { flag: m[1] }]],
  [/error: argument (\S+): invalid int value: '([^']*)'/, "bad", (m) => ["gloss.int", { flag: m[1], v: m[2] }]],
  [/error: argument (\S+): invalid choice: '([^']*)' \(choose from ([^)]*)\)/, "bad", (m) => ["gloss.choice", { flag: m[1], v: m[2], options: m[3] }]],
  [/^SURVEY (\d+) columns.*?\| (\d+) roof rings, ridge underside ([\d.]+)/, "info", (m) => ["gloss.survey", { n: m[1], r: m[2], ridge: m[3] }]],
  // A part placed again names the later parts still standing on the old one (design runs 7 and 8).
  [/^PLACED \w+: (\d+) pieces.*\| the ([\w ,]+?) stands? on the old (\w+): place/, "info",
    (m, t) => ["gloss.stale", { n: num(m[1]), parts: parts(m[2], t), base: t(`part.${m[3]}`) }]],
  [/^PLACED \w+: (\d+) pieces/, "info", (m) => ["gloss.placed", { n: num(m[1]) }]],
  [/^ANATOMY (\d+) pieces/, "info", (m) => ["gloss.anatomy", { n: num(m[1]) }]],
  [/^BEARING (\d+) pieces ([1-9]\d*) floating/, "bad", (m) => ["gloss.bearing.bad", { f: m[2] }]],
  [/^BEARING (\d+) pieces 0 floating/, "good", (m) => ["gloss.bearing.ok", { n: num(m[1]) }]],
  [/^LOADS .*?total ([\d.]+) MN.*?every column within ([\d.]+) MPa/, "good", (m) => ["gloss.loads", { mn: m[1], mpa: m[2] }]],
  [/^SHAKE .*?\| ([1-9]\d*) came down/, "bad", (m) => ["gloss.shake.bad", { n: m[1] }]],
  [/^SHAKE .*?\| 0 came down/, "good", () => ["gloss.shake.ok", {}]],
  [/^SETTLE (\d+) pieces fell (\d+) shifted (\d+)/, null, (m) => (Number(m[2]) + Number(m[3])
    ? ["gloss.settle.bad", { f: m[2], s: m[3] }] : ["gloss.settle.ok", { n: num(m[1]) }])],
  [/NOT alike: (\d+) timber pieces stand out through the roof/, "bad", (m) => ["gloss.likeness.roof", { n: m[1] }]],
  [/NOT alike/, "bad", () => ["gloss.likeness.bad", {}]],
  [/^LIKENESS front ([\d.]+) side ([\d.]+) above ([\d.]+).*\| alike/, "good", (m) => ["gloss.likeness.ok", { f: m[1], s: m[2], a: m[3] }]],
  // A design's brief check, with its own numbers: bays, the corner columns' span, rings, the bracket share.
  [/^BRIEF (\d+) by (\d+) bays \| corner columns \[([\d.]+), ([\d.]+)\] m apart \| (\d+) rings of columns \| bracket sets (\d+)% of the column \| (meets|does NOT meet)/,
    null, (m) => [m[7] === "meets" ? "gloss.brief.ok" : "gloss.brief.bad", { x: m[1], y: m[2], w: m[3], d: m[4], r: m[5], p: m[6] }]],
  [/^BRIEF .*does NOT meet the brief/, "bad", () => ["gloss.brief.plain", {}]],
  // The checks added by the design runs, as a hand-over sent back reads them.
  [/(\d+) timber pieces stand past the edge of the roof/, "bad", (m) => ["gloss.eaves", { n: m[1] }]],
  [/the roof is open at the hips: ([\d.]+) m2/, "bad", (m) => ["gloss.open.roof", { a: m[1] }]],
  [/the roof is open/, "bad", () => ["gloss.open.roof.plain", {}]],
  [/^exit \d+: ([\w.]+(?:Error|Exception)):/, "bad", (m) => ["gloss.crashed", { err: m[1] }]],
  [/^exit \d+:/, "bad", () => ["gloss.crashed.plain", {}]],
  [/^JUDGE pass/, "good", () => ["gloss.judge.ok", {}]],
  [/^JUDGE fail \| (.*)/, "bad", (m) => ["gloss.judge.bad", { change: m[1] }]],
  [/^returned no text/, "bad", () => ["gloss.silent", {}]],
  [/^REVIEW not available/, "info", () => ["gloss.review", {}]],
  [/^FAULTS hanging (\d+)/, "info", (m) => ["gloss.faults", { n: m[1] }]],
  [/the hall changed after the last (\S+), or it never ran/, "bad", (m) => ["gloss.owed", { check: m[1] }]],
  [/^REFUSED argument (\S+): invalid (?:float|int) value: '([^']*)'/, "bad", (m) => ["gloss.number", { flag: m[1], v: m[2] }]],
  [/^REFUSED /, "bad", () => ["gloss.refused.other", {}]],            // any other refusal, in the tool's own words below
];

export function gloss(text, t) {
  for (const [shape, tone, words] of SHAPES) {
    const found = (text || "").match(shape);
    if (!found) continue;
    const [key, vars] = words(found, t);
    return { text: t(key, vars), tone: tone || (key.endsWith(".bad") ? "bad" : "good") };
  }
  return null;
}

// What today's brief check found on the hall an adopted design ended with, in one line: how many pieces
// stand past the eaves or through the roof, and in how many other ways the hall falls short of the brief.
export function laterFinding(faults, t) {
  const eaves = faults?.beyond_the_eaves?.length || 0, roof = faults?.through_the_roof?.length || 0;
  const open = (faults?.later?.new_checks || []).includes("open_roof");        // the roof tool's open hips, run 6
  const other = Math.max(0, (faults?.later?.short_of_the_brief || []).length - (eaves ? 1 : 0) - (roof ? 1 : 0) - (open ? 1 : 0));
  return [eaves && t("later.eaves", { n: eaves }), roof && t("later.roof", { n: roof }), open && t("later.open"),
    other && t("later.other", { n: other })]
    .filter(Boolean).join(t("later.sep"));
}

// How a run ended, in its own words and in one line: stopped with checks still owed, handed over with
// what a later check found on its final hall (timber through the roof in rebuild run 2, a design that no
// longer meets today's brief), or adopted.
export function ending(ch, record, t) {
  if (ch.kind === "stop") {
    const owed = (record.harness.still_owed || [])[0] || ch.evidence;
    return { kind: "ended.no", words: owed, line: gloss(owed, t) || { text: t("gloss.silent"), tone: "bad" } };
  }
  const later = record.design && record.faults?.found_later ? record.faults.later : null;
  if (later) {
    const what = laterFinding(record.faults, t), checks = later.new_checks.join(t("list.sep"));
    return { kind: "ended.wrong", words: later.short_of_the_brief.join("; "), line: { text: t("gloss.wrong.design", { what }), tone: "bad" },
      note: t(checks ? "catch.ended.later.note" : "catch.ended.later.note.stricter", { checks, what }) };
  }
  const roof = record.faults?.through_the_roof || [];
  if (roof.length) {
    return { kind: "ended.wrong", words: `NOT alike: ${roof.length} timber pieces stand out through the roof: ${roof.join(", ")}`,
      line: { text: t("gloss.wrong", { n: roof.length }), tone: "bad" } };
  }
  const brief = record.design ? record.harness.brief : null;          // a design says what its brief check measured
  const line = brief?.span ? t("gloss.adopted.design", { x: brief.bays[0], y: brief.bays[1], w: brief.span[0], d: brief.span[1],
    r: brief.column_rings, p: Math.round(brief.brackets.of_column * 100) }) : t("gloss.adopted");
  return { kind: "ended.yes", words: (ch.evidence || "").split(". ")[0], line: { text: line, tone: "good" } };
}

// What the harness said at any step, as the strip beside the controls shows it.
export function reply(ch, record, t) {
  if (ch.kind === "think") return { text: t("gloss.think", { n: num(ch.tokens || 0) }), tone: "info" };
  if (ch.kind === "look") return { text: t("gloss.look"), tone: "info" };
  if (ch.kind === "final" || ch.kind === "stop") return ending(ch, record, t).line;
  if (ch.tool === "read") return { text: t("gloss.read", { file: ch.args?.file || "" }), tone: "info" };
  return gloss(ch.evidence, t) || { text: ch.title, tone: "info" };
}
