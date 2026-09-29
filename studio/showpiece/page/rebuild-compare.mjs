// The attempts side by side, in numbers: each card gets its run's own time, actions, tokens, what
// the harness stopped and the repair rounds, counted from that run's record with the same rules the
// replay uses, so a card can never disagree with the run it opens. A design's card and button also
// take their result, how the run ended and what its last brief check measured from the record.
import { caught, prepare, repairRounds } from "./rebuild-scenes.mjs";
import { filesOf, getJson, make, runOf } from "./rebuild-runs.mjs";
import { laterFinding } from "./rebuild-gloss.mjs";

const clock = (s) => `${String(Math.floor(s / 60)).padStart(2, "0")}:${String(Math.round(s % 60)).padStart(2, "0")}`;

// What the brief check measured on the hall the design ended with, or that the last hall was never measured;
// `later` when today's check found the adopted hall short of the brief.
export function briefLine(brief, t, later = false) {
  if (!brief?.current || !brief.bays) return t("compare.brief.none");
  return t(later ? "compare.brief.later" : brief.meets ? "compare.brief.meets" : "compare.brief.short", { x: brief.bays[0], y: brief.bays[1] });
}

// A design's result: not adopted, adopted, or adopted wrongly, when a check added since fails its final hall.
export const resultOf = (record) => (!record.measured.adopted ? "no" : record.faults?.found_later ? "wrong" : "yes");

// A design's card, and its button and chip on the success path, which read its result the same way.
function dressDesign(card, record, t) {
  const result = resultOf(record);
  card.dataset.result = result;
  card.querySelector("strong").textContent = t(`result.${result}`);
  card.querySelector("span").textContent = result === "wrong" ? t("design.card.later", { what: laterFinding(record.faults, t) })
    : result === "yes" ? t("design.card.adopted") : record.steps.at(-1)?.detail || "";
  for (const node of document.querySelectorAll(`.runs a[data-run="${card.dataset.run}"], .path a[data-run="${card.dataset.run}"]`)) {
    node.dataset.result = result;
    node.querySelector("em").textContent = t(`result.${result}`);
  }
}

// Beside the real hall. A design is adopted when it answers the brief and stands; the brief never described the
// look, so a design's final hall is set beside the real one by the five numbers hall-carpenter measures of both
// (rebuild_designs.py), the design's first. Which designs appear, and every number, come from the records.
const one = (v) => (v == null ? "–" : Number(v).toFixed(1));
const SHOWN = {
  rings: (v) => (v.roof_rings == null ? "–" : String(v.roof_rings)), ridge: (v) => one(v.ridge_m),
  eaves: (v) => v.eaves_m.map(one).join(" / "), outline: (v) => v.outline_m.map(one).join(" × "), top: (v) => one(v.top_m),
};
// One line per number: a design's beside the real hall's, or, with no design, the real hall's alone.
export const versusLines = (real, design, t) => Object.entries(SHOWN).map(([key, show]) => (design
  ? t("versus.line", { what: t(`versus.${key}`), d: show(design), r: show(real) }) : t("versus.own", { what: t(`versus.${key}`), v: show(real) })));
// The same numbers, short, for a design's card.
export const versusShort = (real, design, t) => Object.entries(SHOWN)
  .map(([key, show]) => t("versus.pair", { what: t(`versus.short.${key}`), d: show(design), r: show(real) })).join(" · ");

// The adopted designs' final halls beside the real one: the lower half of the picture each design's last brief
// check made is its hall, as the real hall's picture is our measured model's render.
function showVersus($, t, records, real) {
  const adopted = records.filter((r) => r?.design && resultOf(r) === "yes" && r.versus_real);
  if (!real || !adopted.length) return;
  const hall = (src, caption, lines, kind) => make("figure", { className: `versus-hall ${kind}` }, make("img", { src, alt: caption, loading: "lazy" }),
    make("figcaption", { textContent: caption }), make("ul", {}, ...lines.map((line) => make("li", { textContent: line }))));
  $("versus-halls").append(hall("rebuild-temple.jpg", t("versus.real.caption"), versusLines(real, null, t), "real"),
    ...adopted.map((r) => hall(r.steps.findLast((s) => s.tool === "brief" && s.media?.image)?.media.image || "",
      t("versus.design.caption", { n: r.run }), versusLines(real, r.versus_real, t), "design")));
  $("versus-title").textContent = t("versus.title");
  $("versus-lede").textContent = t("versus.lede");
  $("design-versus").hidden = false;
}

export async function compareRuns($, t) {
  const cards = [...document.querySelectorAll(".attempts li[data-run]")];
  const reading = getJson("rebuild-real-hall.json").catch(() => null);
  const records = await Promise.all(cards.map((card) => getJson(filesOf(runOf(card.dataset.run)).record).catch(() => null)));
  const real = await reading;
  cards.forEach((card, i) => {
    const record = records[i];
    if (!record) return;
    const steps = prepare(record.steps), m = record.measured, laps = record.harness.limits.laps;
    const rows = [
      [t("compare.time"), clock(m.wall_seconds)],
      [t("compare.actions"), String(m.actions)],
      [t("compare.tokens"), t("fig.tokens", { n: (m.tokens / 10000).toFixed(1) })],
      [t("compare.caught"), String(steps.filter(caught).length)],
      [t("compare.rounds"), `${Math.max(0, ...repairRounds(steps))} / ${laps}`],
      ...(record.design ? [[t("compare.brief"), briefLine(record.harness.brief, t, !!record.faults?.found_later)]] : []),
      ...(record.design && record.versus_real && real ? [[t("compare.real"), versusShort(real, record.versus_real, t)]] : []),
    ];
    const list = document.createElement("dl");
    list.className = "nums";
    for (const [label, value] of rows) {
      const row = document.createElement("div");
      row.append(Object.assign(document.createElement("dt"), { textContent: label }), Object.assign(document.createElement("dd"), { textContent: value }));
      list.append(row);
    }
    card.querySelector("a").append(list);
    const tab = document.querySelector(`.runs a[data-run="${card.dataset.run}"]`);   // and the top bar's switch
    if (tab) tab.querySelector(".run-meta").textContent = t("run.meta", { time: clock(m.wall_seconds), n: steps.length });
    if (record.design) dressDesign(card, record, t);
    if (/\brun-chip\b/.test(tab?.className || "")) {                  // a rebuild's or a design's: which, which run, how it ended
      tab.title = [t(record.design ? "design.group" : "rebuild.group"), t("design.tab", { n: record.design ? record.run : card.dataset.run }),
        tab.querySelector("em").textContent, tab.querySelector(".run-meta").textContent].join(" · ");
    }
  });
  showVersus($, t, records, real);
}
