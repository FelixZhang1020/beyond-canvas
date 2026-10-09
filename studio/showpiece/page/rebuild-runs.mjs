// Which rebuild the page plays: ?run=1, 2 or 3 for the three earlier attempts, none for
// the adopted fourth, ?design=N for the Nth hall designed from a written brief (rebuild_designs.py).
// The earlier runs were never rebuilt stage by stage: their hall is the run's own final model, and each
// family of pieces appears at the step that placed it. A family placed again later keeps its final
// shape throughout, which the page says, because nothing kept the rest. A design run kept its hall
// after every placing call, so it plays on those stages.
const FAMILY = {
  platform: ["stone"], columns: ["columns"], ties: ["tie"], walls: ["walls"], brackets: ["brackets"],
  frames: ["frame"], purlins: ["purlins"], rafters: ["rafters"], roof: ["roof_tiles", "ridges"],
};

// A page file that stops coming for eight seconds is asked for once more past the browser's own copy. A transfer the
// link left hanging kept its hold on the browser's copy of rebuild-hall.json, and every later request for that file
// waited behind it, the hall's picture with them, for minutes; the same file asked for afresh came in under a second.
// A slow link still sends something every few seconds, so only a stall is asked for again.
export async function steadyFetch(name, idle = 8000) {
  for (const cache of ["default", "no-store"]) {
    const stop = new AbortController();
    let timer = setTimeout(() => stop.abort(), idle);
    try {
      const answer = await fetch(name, { cache, signal: stop.signal });
      if (!answer.body?.getReader) return answer;
      const reader = answer.body.getReader(), parts = [];
      for (;;) {
        clearTimeout(timer);
        timer = setTimeout(() => stop.abort(), idle);
        const { done, value } = await reader.read();
        if (done) break;
        parts.push(value);
      }
      return new Response(new Blob(parts), { status: answer.status, statusText: answer.statusText, headers: answer.headers });
    } catch (error) {
      if (cache === "no-store" || error.name !== "AbortError") throw error;
    } finally {
      clearTimeout(timer);
    }
  }
}

// A page file, asked for again when it does not come. The studio is restarted often while sessions send their
// work, and one failed request left the page half-built — no design chips, no run marked as playing — with
// nothing said (the operator saw it). Four more tries over about eight seconds cover a restart.
export async function getJson(name, waits = [500, 1000, 2000, 4000]) {
  for (let i = 0; ; i++) {
    try {
      const answer = await steadyFetch(name);
      if (answer.ok) return await answer.json();
      if (i >= waits.length) throw new Error(`${name} HTTP ${answer.status}`);
    } catch (error) {
      if (i >= waits.length) throw error;
    }
    await new Promise((done) => setTimeout(done, waits[i]));
  }
}

export function whichRun(search) {
  const query = new URLSearchParams(search), design = Number(query.get("design"));
  if (Number.isInteger(design) && design > 0) return `design${design}`;
  const n = Number(query.get("run"));
  return [1, 2, 3].includes(n) ? n : 4;
}

export const isDesign = (run) => /^design\d+$/.test(String(run));
export const runOf = (key) => (isDesign(key) ? key : Number(key));      // a data-run attribute back to its run

export function filesOf(run) {
  const at = run === 4 ? "rebuild-" : isDesign(run) ? `rebuild-${run}-` : `rebuild-run${run}-`;
  return { record: `${at}record.json`, hall: `${at}hall` };
}

export const make = (tag, props = {}, ...children) => { const node = Object.assign(document.createElement(tag), props); node.append(...children); return node; };

// The designs rebuild-designs.json lists: a button each in the top bar's second group and a card each
// below, with the success path above the cards. Their results and numbers are filled from each run's
// record (rebuild-compare.mjs).
export function listDesigns({ $, t, designs, path = [] }) {
  for (const { n, run } of designs) {
    const key = `design${n}`, href = `rebuild.html?design=${n}`;
    // A numbered chip in the top bar, the same as the four rebuilds' beside it: its result colours it, and its
    // words (result, time, steps) are its tooltip. rebuild.html writes the chips so the bar is whole at once; one
    // it does not have yet is made here.
    const tab = $("design-runs").querySelector(`[data-run="${key}"]`)
      || make("a", { href, className: "run-chip" }, make("b", {}, String(n)), make("em"), make("i", { className: "run-meta" }));
    const card = make("li", {}, make("a", { href }, make("b", { textContent: t("design.card", { n }) }),
      make("strong"), make("span")));
    tab.dataset.run = card.dataset.run = key;
    $("design-runs").append(tab);
    $("design-cards").append(card);
  }
  $("designs-section").hidden = !designs.length;
  $("design-runs").hidden = !$("design-runs").querySelector(".run-chip");      // the written chips stay if the list never came
  listPath({ $, t, path });
}

// The success path: stage by stage, the runs as chips, what they exposed and the harness fix that followed,
// in the order rebuild-designs.json's path gives. Each chip takes its result the way its button does.
function listPath({ $, t, path }) {
  for (const stage of path) {
    const chips = make("div", { className: "chips" }, ...stage.runs.map((n) => {
      const chip = make("a", { className: "chip", href: `rebuild.html?design=${n}` }, make("b", { textContent: t("design.tab", { n }) }), make("em"));
      chip.dataset.run = `design${n}`;
      return chip;
    }));
    const said = ["found", "fixed", "end"].filter((part) => stage[part])
      .map((part) => make("p", { className: part }, make("b", { textContent: t(`path.${part}.label`) }), t(stage[part])));
    $("path-stages").append(make("div", { className: "stage" }, chips, ...said));
  }
  $("path-title").textContent = t("path.title");
  $("design-path").hidden = !path.length;
}

export const familiesOf = (tool) => FAMILY[tool] || [];

// Stage by stage for a run kept only as its final hall: every family placed so far, at each placing step.
export function familyStages(chapters, pieces) {
  const placed = new Set(), stages = {};
  for (const ch of chapters) {
    if (ch.frame !== `step-${ch.step}`) continue;
    for (const family of familiesOf(ch.tool)) placed.add(family);
    stages[ch.frame] = pieces.flatMap(([, family], id) => (placed.has(family) ? [id] : []));
  }
  return stages;
}

// The pieces an earlier run's own checks, or today's check afterwards, found wrong; a design's brief
// check also names timber standing past the edge of the roof.
export function faultIds(faults, pieces) {
  const ids = (names) => pieces.flatMap(([name], id) => ((names || []).includes(name) ? [id] : []));
  return { fell: ids(faults?.fell), hanging: ids(faults?.hanging), roof: ids(faults?.through_the_roof), eaves: ids(faults?.beyond_the_eaves) };
}

// The page's own words for the run it plays: header numbers, heading, the attempt cards, the source note.
export function dressPage({ $, t, run, files, record, chapters, total }) {
  const m = record.measured, design = isDesign(run), n = design ? record.run : run;
  const kicker = t(design ? "design.kicker" : "kicker", { n });
  $("fig-time").textContent = total;
  $("fig-actions").textContent = String(m.actions);
  $("fig-tokens").textContent = t("fig.tokens", { n: (m.tokens / 10000).toFixed(1) });
  $("kicker").textContent = kicker;
  for (const card of document.querySelectorAll(".attempts li[data-run]")) {
    const here = card.dataset.run === String(run);
    card.classList.toggle("current", here);
    if (here) card.querySelector("b").append(Object.assign(document.createElement("em"), { textContent: t("attempt.current") }));
  }
  for (const tab of document.querySelectorAll(".runs a[data-run]")) {       // the switch in the top bar
    const here = tab.dataset.run === String(run);
    tab.classList.toggle("current", here);
    if (here) tab.setAttribute("aria-current", "page");
  }
  $("prov-link").href = files.record;
  $("story-head").textContent = t(run === 4 ? "head.rebuilt" : !design ? "head.old" : record.stages_kept ? "head.design" : "head.design.single");
  $("timeline-title").textContent = t("timeline.title", { n: chapters.length });
  if (run === 4) return;
  $("how-section").hidden = true;                  // it describes the fourth run's harness
  if (design) {
    $("frame").alt = t("design.photo.alt");
    $("prov-1").textContent = t("design.provenance.1", { n, time: total, steps: chapters.length });
    $("prov-2").textContent = t(record.stages_kept ? "design.provenance.2" : "design.provenance.2.single");
  } else {
    $("prov-1").textContent = t("provenance.old.1", { n: run, time: total, steps: chapters.length });
    $("prov-2").textContent = t("provenance.old.2");
  }
  document.title = `${document.title} · ${kicker}`;
}
