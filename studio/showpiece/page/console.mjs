// The console on the rail: the machine as block bars with a history, the components and the six
// skills as a process table, the pipeline as a tree with the working branch lit, and a log tail
// with a line per step and a live line for the heartbeat. Built once; updated in place.
import { push, frameRate } from "./flow.mjs";
import { blockBar, sparkBlocks, clock, processRows, treeLines, logLine, beatLine } from "./ops.mjs";

const KEEP = 14;

export function makeConsole({ el, t, $ }) {
  const hist = { cpu: [], mem: [], gpu: [], fps: [] };
  const lines = [];            // the log tail: { at, who, text, tone }
  const logged = new Set();    // steps already in the log, so a scrub does not repeat them
  let prevBeat = null, request = "";

  function res(id, label) {
    return el("div", { class: "res", id: `res-${id}` }, el("span", { class: "k" }, label), el("span", { class: "bar", id: `bar-${id}` }, blockBar(null)),
      el("span", { class: "hist", id: `hist-${id}` }, ""), el("span", { class: "v", id: `val-${id}` }, "–"));
  }

  function part(label, ...children) { return el("div", { class: "part" }, el("div", { class: "sect" }, label), ...children); }

  function build() {
    return el("section", { class: "panel console" },
      el("div", { class: "chead" }, el("b", {}, t("console")), el("span", { class: "host", id: "console-host" }, ""), el("span", { class: "clock", id: "console-clock" }, "0:00")),
      el("div", { class: "cbody" },
        part("resources", el("div", { class: "resources" }, res("cpu", "cpu"), res("mem", "mem"), res("gpu", "gpu"), res("fps", "fps"))),
        part("processes", el("table", { class: "ps" },
          el("thead", {}, el("tr", {}, el("th", {}, "name"), el("th", {}, "state"), el("th", { class: "r" }, "time"), el("th", { class: "r" }, "calls"))),
          el("tbody", { id: "ps" }))),
        part("pipeline", el("div", { class: "tree", id: "tree" })),
        part("log", el("div", { class: "log", id: "log" }))));
  }

  function setRun(run) {
    request = run.request || "";
    lines.length = 0;
    logged.clear();
  }

  function note(event, elapsed) {
    if (logged.has(event.step) || (event.kind === "think" && !(event.text || "").trim())) return;
    logged.add(event.step);
    lines.push({ at: elapsed, ...logLine(event) });
    if (lines.length > KEEP) lines.splice(0, lines.length - KEEP);
  }

  function update({ beat, events, elapsed }) {
    $("console-clock").textContent = clock(elapsed);
    $("ps").replaceChildren(...processRows(events, beat, elapsed).map((r) =>
      el("tr", { class: r.busy ? "busy" : r.state === "–" ? "off" : "" },
        el("td", { class: "n" }, r.name, el("small", {}, r.skill ? t(`skill.${r.name}`) : r.sub)),
        el("td", {}, r.state), el("td", { class: "r" }, r.time), el("td", { class: "r" }, String(r.calls)))));
    $("tree").replaceChildren(...treeLines(events, beat, request).map((l) => el("p", { class: l.lit ? "lit" : "" }, l.text)));
    const rate = frameRate(prevBeat, beat);
    if (rate !== null || !beat) { hist.fps = push(hist.fps, rate); paint("fps", rate === null ? null : Math.min(100, rate * 20), rate === null ? "–" : rate.toFixed(1)); }
    prevBeat = beat;
    const live = beatLine(beat);
    const box = $("log");
    box.replaceChildren(...lines.map((l) => line(l.at, l.who, l.text, l.tone)),
      live ? line(elapsed, live.who, live.text, "live cur") : line(elapsed, "exhibit", t("idleflow"), "cur"));
    box.scrollTop = box.scrollHeight;
  }

  function line(at, who, text, tone) {
    return el("p", { class: tone || "" }, el("span", { class: "t" }, `+${clock(at)}`), " ", el("span", { class: "k" }, who), " ", text);
  }

  function paint(id, pct, text) {
    $(`bar-${id}`).textContent = blockBar(pct);
    $(`hist-${id}`).textContent = sparkBlocks(hist[id]);
    $(`val-${id}`).textContent = text;
    $(`res-${id}`).classList.toggle("hot", (pct || 0) > 70);
    $(`res-${id}`).classList.toggle("absent", pct === null);
  }

  function stats(s) {
    $("console-host").textContent = s.host || "";
    const cpu = Number.isFinite(s.cpu_percent) ? s.cpu_percent : null;
    hist.cpu = push(hist.cpu, cpu); paint("cpu", cpu, cpu === null ? "–" : `${cpu.toFixed(0)} %`);
    const mem = s.memory_total_gb ? (s.memory_used_gb / s.memory_total_gb) * 100 : null;
    hist.mem = push(hist.mem, mem); paint("mem", mem, mem === null ? "–" : `${s.memory_used_gb.toFixed(1)} / ${s.memory_total_gb.toFixed(0)} G`);
    const gpu = s.gpu ? s.gpu.util_percent : null;
    hist.gpu = push(hist.gpu, gpu); paint("gpu", gpu, s.gpu ? (gpu === null ? "–" : `${gpu.toFixed(0)} %`) : t("gpu.spark"));
  }

  return { build, update, stats, note, setRun };
}
