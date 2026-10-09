// The conversation pane and the clock of a run, laid out as a chat: the request as the reader's
// bubble, then the agent's turn under its avatar: thoughts in a quiet voice, each tool call a
// compact card that opens on a click, the answer as its bubble, and a typing indicator while it
// thinks or a tool runs. Words type out; a recorded run replays as if live. Live steps arrive the
// same way, typed at reading speed.
import { typeMs, typedLength, cardLine, outputTail, replayPlan, PACES } from "./stream.mjs";
import { fold, unjudgedPicture } from "./timeline.mjs";

export function makePlayer({ el, t, $, fileUrl, onChange, onDraw }) {
  const st = { events: [], shown: 0, timers: [], typers: new Set(), playing: false, following: true, beat: null, done: false, replayed: false,
    glued: true,     // glued: the box stays at its bottom through typing and pictures loading, until the reader scrolls up
    pace: PACES.replay,   // how a recording plays, and what its finale is: the film large, or the 3D showpiece moving
    request: "", typingRow: null };

  function cancel() {
    for (const x of st.timers) clearTimeout(x);
    st.timers = [];
    for (const typer of st.typers) { typer.node.textContent = typer.full; typer.node.classList.remove("typing"); }
    st.typers.clear();
  }

  function reset(events, done, request = st.request) {
    cancel();
    Object.assign(st, { events, shown: 0, done, beat: null, playing: false, following: true, replayed: false, request, typingRow: null, pace: PACES.replay });
    opening();
  }

  // The chat's opening: the reader's request as a bubble, then the agent's turn begins.
  function opening() {
    const box = $("timeline");
    box.replaceChildren();
    if (!st.request) { box.append(el("p", { class: "empty" }, t("empty"))); return; }
    box.append(el("div", { class: "msg user" }, el("div", { class: "bubble" }, st.request), el("span", { class: "avatar you" }, t("you"))),
      el("div", { class: "turn" }, el("span", { class: "avatar agent" }, "S"), el("b", {}, t("agentName"))));
  }

  const blank = (event) => (event.kind === "think" || event.kind === "final") && !(event.text || "").trim();

  // The conversation scrolls in its own box, never the page: the screen beside it stays put.
  function atBottom() {
    const box = $("timeline");
    return box.scrollHeight - box.scrollTop - box.clientHeight < 160;
  }

  function toBottom() {
    const box = $("timeline");
    st.glued = true;
    box.scrollTop = box.scrollHeight;
  }

  function typed(text, ms) {
    const node = el("div", { class: "text" });
    if (!ms) { node.textContent = text; return node; }
    node.classList.add("typing");
    const typer = { node, full: text };
    st.typers.add(typer);
    const started = performance.now();
    const tick = () => {
      if (!st.typers.has(typer)) return;
      const n = typedLength(text.length, performance.now() - started, ms);
      node.textContent = text.slice(0, n);
      if (st.glued) { const box = $("timeline"); box.scrollTop = box.scrollHeight; }   // the row grows as it types; stay with it
      if (n < text.length) requestAnimationFrame(tick);
      else { node.classList.remove("typing"); st.typers.delete(typer); }
    };
    requestAnimationFrame(tick);
    return node;
  }

  function printout(event) {
    const { shown, hidden } = fold(event.text || "", 8);
    const pre = el("div", { class: "printout", hidden: "" }, shown);
    const open = el("button", { class: "ghost more" }, t("open"));
    open.onclick = () => {
      pre.hidden = !pre.hidden;
      if (!pre.hidden && hidden) pre.textContent = event.text;
      open.textContent = pre.hidden ? t("open") : t("close");
    };
    return [open, pre];
  }

  function body(event, ms) {
    const box = el("div", { class: "body" });
    if (event.kind === "act") {
      const failed = /^exit \d+:/.test(event.text || "") || /^no such|^tool .* takes no/.test(event.text || "");
      const name = event.tool === "read" ? t("kind.read") : `${event.skill} / ${event.tool}`;
      box.append(el("div", { class: "tool" }, el("span", { class: `mark ${failed ? "bad" : "ok"}` }, failed ? "\u2717" : "\u2713"), name));
      if (event.command) box.append(el("div", { class: "cmd" }, el("span", { class: "prompt" }, "$ "), event.command));   // exactly what ran
      if (event.tool === "read") box.append(el("div", { class: "line" }, cardLine(event)));
      else {
        const lines = outputTail(event.text, 4);
        const summary = cardLine(event);
        if (lines.length) box.append(el("div", { class: "out" }, ...lines.map((l) => el("div", { class: l === summary ? "hi" : "" }, l))));
        else if (summary) box.append(el("div", { class: "line" }, summary));
      }
      if (event.picture) box.append(el("div", { class: "shot" }, el("img", { src: fileUrl(event.picture), alt: event.picture, loading: "lazy" })));
      if ((event.files || []).length) box.append(el("div", { class: "seen files" }, `${t("wrote")} `, ...event.files.map((f) => fileButton(f))));
      if (event.text) box.append(...printout(event));
    } else if (event.kind === "look") {
      const ok = event.verdict && event.verdict.verdict === "pass";
      box.append(el("div", { class: "seen" }, el("span", { class: `stamp ${ok ? "pass" : "fail"}` }, ok ? t("pass") : t("fail")), " ",
        event.verdict && event.verdict.seen ? event.verdict.seen : event.text || ""));
    } else {
      const node = typed(event.text || "", ms);
      if (event.kind === "final") node.classList.add("final");
      box.append(node);
    }
    return box;
  }

  // A file the tool wrote: a name to click; text files open under the card with their real contents.
  function fileButton(name) {
    if (!/\.(json|jsonl|txt|md|csv)$/i.test(name)) return el("span", { class: "file" }, name);
    const b = el("button", { class: "ghost file" }, name);
    let fold = null;
    b.onclick = async () => {
      if (fold) { fold.remove(); fold = null; return; }
      fold = el("pre", { class: "filefold" }, "\u2026");
      b.closest(".body").append(fold);
      try {
        const text = await (await fetch(fileUrl(name))).text();
        let shown = text;
        try { shown = JSON.stringify(JSON.parse(text), null, 2); } catch (e) { /* not JSON: as is */ }
        const cut = shown.split("\n");
        fold.textContent = cut.slice(0, 60).join("\n") + (cut.length > 60 ? `\n\u2026 (${cut.length} lines, ${Math.round(text.length / 1024)} KB)` : "");
      } catch (e) { fold.textContent = name; }
    };
    return b;
  }

  function rowFor(event, ms) {
    const exit = event.kind === "act" && event.tool !== "read" ? ((/^exit (\d+):/.exec(event.text || "") || [0, "0"])[1]) : null;
    const meta = [`#${event.step}`, event.seconds ? `${event.seconds}s` : "", exit === null ? "" : `exit ${exit}`, event.tokens ? `${event.tokens} tok` : ""].filter(Boolean).join(" \u00b7 ");
    return el("div", { class: `row is-${event.kind}`, "data-step": event.step }, body(event, ms), el("span", { class: "meta" }, meta));
  }

  // While the agent thinks or a tool runs, the chat shows it at the foot of the turn.
  function indicator(beat) {
    if (st.typingRow) { st.typingRow.remove(); st.typingRow = null; }
    if (!beat) return;
    const text = beat.phase === "tool" ? t("typing.tool").replace("{tool}", beat.tool || "") : t("typing.thinking");
    st.typingRow = el("div", { class: "row is-typing" }, el("span", { class: "dots" }, el("i"), el("i"), el("i")), el("span", { class: "text" }, text));
    $("timeline").append(st.typingRow);
    if (st.glued) toBottom();
  }

  function stampPrevious(event) {
    if (!event.verdict) return;
    const step = unjudgedPicture(st.events.slice(0, st.shown));
    const shot = step === null ? null : $("timeline").querySelector(`.row[data-step="${step}"] .shot`);
    if (!shot) return;
    const ok = event.verdict.verdict === "pass";
    shot.querySelectorAll(".stamp").forEach((s) => s.remove());
    shot.append(el("span", { class: `stamp ${ok ? "pass" : "fail"}` }, ok ? t("pass") : t("fail")));
  }

  function draw(event, ms, animate) {
    const box = $("timeline");
    if (box.firstElementChild && box.firstElementChild.classList.contains("empty")) box.replaceChildren();
    const near = atBottom();
    stampPrevious(event);
    if (st.typingRow) { st.typingRow.remove(); st.typingRow = null; }
    st.shown += 1;
    onDraw(event);
    if (blank(event)) return;                      // an empty thought is nothing to show
    const row = rowFor(event, ms);
    if (animate) row.classList.add("arrive");
    box.append(row);
    for (const img of row.querySelectorAll("img")) img.addEventListener("load", () => { if (st.glued) toBottom(); }, { once: true });
    if (near || st.playing) toBottom();              // a replay follows its own steps
    else if (!st.done) $("newer").hidden = false;    // a live run calls the reader who scrolled up
  }

  // A live step: drawn at once, typed at reading speed, unless the reader has scrubbed back.
  function push(event) {
    st.events.push(event);
    if (st.following && st.shown === st.events.length - 1) draw(event, typeMs(event, 1), true);
    onChange();
  }

  function showUpTo(n) {
    cancel();
    st.playing = false;
    st.beat = null;
    st.replayed = false;                             // the finale is not on, until a replay ends again
    opening();
    st.shown = 0;
    for (const event of st.events.slice(0, n)) { stampPrevious(event); if (!blank(event)) $("timeline").append(rowFor(event, 0)); st.shown += 1; onDraw(event); }
    st.following = st.shown >= st.events.length;
    toBottom();
    onChange();
  }

  // A recorded run step by step: heartbeats between the steps (frames counting up, the newest
  // painting), each step typed at reading speed; half a minute at the live pace for a run that took
  // an hour, a quarter of that at the brisk one. The pace stays for "watch again".
  function replay(events, pace = st.pace) {
    cancel();
    Object.assign(st, { events, shown: 0, done: false, beat: null, playing: true, following: true, replayed: false, pace });
    opening();
    replayFrom(0);
  }

  // The plan from this step on: heartbeats and steps at their times.
  function replayFrom(from) {
    st.playing = true; st.done = false; st.beat = null; st.replayed = false;
    for (const item of replayPlan(st.events.slice(from), st.pace)) {
      st.timers.push(setTimeout(() => {
        if (item.beat) { st.beat = item.beat; onChange(); return; }
        st.beat = null;
        draw(item.event, typeMs(item.event, 1), true);
        if (st.shown >= st.events.length) { st.playing = false; st.done = true; st.replayed = st.pace.finale === "film"; }   // the finale: the film goes large, or the 3D showpiece stays
        onChange();
      }, item.at_ms));
    }
    onChange();
  }

  function beat(b) { st.beat = b; onChange(); }

  return { st, reset, push, showUpTo, beat, replay, atBottom, toBottom, indicator };
}
