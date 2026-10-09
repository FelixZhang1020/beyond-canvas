// The agent's screen: the big picture being painted or judged, or the live 3D model moving the
// way the agent's plan says, with the status line and its bar. Built once; updated in place.
import { statusOf, bigPicture, newestFilm } from "./stream.mjs";
import { showpieceOf } from "./plans.mjs";

const PAINTS = ["coral", "tangerine", "sunflower", "leaf", "sky", "violet"];
const PLAN_FILES = { explode: "explode.json", raise: "scenes.json", load: "loads.json", tour: "tour.json", settle: "settle.json" };

export function makeScreen({ el, t, $, fileUrl, onView }) {
  let shownSrc = null;
  const celebrated = new Set();
  const three = { run: null, view: "picture", chosen: false, viewer: null, making: null, loaded: null, loading: null, plans: new Map(), roles: null, shown: null, retry: 0, note: "", theatre: false, hint: "idle" };
  const rolesByModel = new Map();   // piece -> role, per model: the same for every run on that model, 6 MB a time for the hall

  function build() {
    const views = el("button", { class: "toggle3d", id: "view-3d", "aria-pressed": "false" }, t("view.3d"));
    const film = el("button", { class: "toggle3d", id: "view-film", "aria-pressed": "false", hidden: "" }, t("view.film"));
    const full = el("button", { class: "toggle3d", id: "view-full", "aria-pressed": "false", title: t("view.full") }, "\u2922");
    const again = el("button", { class: "toggle3d", id: "replay-btn", hidden: "" }, t("replay"));
    return el("aside", { class: "side" },
      el("div", { class: "panel screen", id: "screen-panel" },
        el("div", { class: "status" },
          el("span", { class: "dot", id: "dot" }), el("span", { class: "line", id: "status" }, t("idle")),
          el("span", { class: "badge", id: "recorded", hidden: "" }, t("recorded")), again, film, views, full,
          el("span", { class: "clock", id: "clock" }, "0:00")),
        el("div", { class: "track slim" }, el("div", { class: "fill", id: "bar" })),
        el("div", { class: "big", id: "big" }, el("p", { class: "empty" }, t("empty")),
          el("div", { class: "stage3d", id: "stage3d", hidden: "" }), el("span", { class: "hint", id: "hint", hidden: "" }, t("drag"))),
        el("div", { class: "caption", id: "caption" })));
  }

  function wire() {
    $("view-3d").onclick = () => { three.chosen = true; setView(three.view === "3d" ? "picture" : "3d"); if (onView) onView(); };
    $("view-film").onclick = () => { three.chosen = true; setView(three.view === "film" ? "picture" : "film"); if (onView) onView(); };
    $("view-full").onclick = () => setTheatre(!three.theatre);
    document.addEventListener("fullscreenchange", () => { if (!document.fullscreenElement && three.theatre) setTheatre(false); });
  }

  // Theatre: the screen panel over the whole window, and the browser's own full screen on top of
  // that where it is allowed (a projector); Escape leaves both.
  function setTheatre(on) {
    three.theatre = on;
    $("screen-panel").classList.toggle("theatre", on);
    $("view-full").classList.toggle("on", on);
    $("view-full").setAttribute("aria-pressed", on ? "true" : "false");
    if (on && document.fullscreenEnabled && !document.fullscreenElement) $("screen-panel").requestFullscreen().catch(() => {});
    if (!on && document.fullscreenElement) document.exitFullscreen().catch(() => {});
  }

  function statusText(s) {
    return t(s.key).replace("{tool}", s.tool || "").replace("{n}", s.frames ?? "").replace("{m}", s.expected ?? "");
  }

  // A live frame swaps in place, so the screen paints like a film; any other picture eases in large.
  function showPicture(pic) {
    const big = $("big");
    big.classList.toggle("live", Boolean(pic && pic.live));
    const media = [...big.children].find((c) => c.tagName === "IMG" || c.tagName === "VIDEO" || c.classList.contains("empty"));
    if (!pic) {
      if (shownSrc !== null) { media.replaceWith(el("p", { class: "empty" }, t("empty"))); shownSrc = null; }
      return;
    }
    if (pic.src === shownSrc) return;
    shownSrc = pic.src;
    if (pic.live && media && media.tagName === "IMG") { media.src = fileUrl(pic.src); media.classList.add("live"); return; }
    const next = pic.video
      ? el("video", { src: fileUrl(pic.src), controls: "", muted: "", autoplay: "", playsinline: "", loop: "", class: "arrive" })
      : el("img", { src: fileUrl(pic.src), alt: pic.src, class: pic.live ? "live" : "arrive" });
    if (pic.video) next.muted = true;                // the films are silent; muted is what lets them start by themselves
    media.replaceWith(next);
  }

  // Paint flies out from the stamp when a shot passes; once per picture.
  function celebrate(pic) {
    if (!pic || !pic.verdict || pic.verdict.verdict !== "pass" || celebrated.has(pic.src)) return;
    celebrated.add(pic.src);
    const burst = el("div", { class: "burst" });
    for (let i = 0; i < 14; i += 1) {
      const angle = (i / 14) * Math.PI * 2 + (Math.random() - 0.5) * 0.5;
      const reach = 90 + Math.random() * 70;
      burst.append(el("i", { style: `--dx:${Math.cos(angle) * reach}px;--dy:${Math.sin(angle) * reach}px;--paint:var(--${PAINTS[i % PAINTS.length]})` }));
    }
    burst.addEventListener("animationend", () => burst.remove(), { once: true });
    $("big").append(burst);
  }

  function caption(pic, note) {
    const box = $("caption");
    box.replaceChildren();
    if (note) box.append(note);
    else if (pic && pic.verdict) {
      const ok = pic.verdict.verdict === "pass";
      box.append(el("span", { class: `stamp ${ok ? "pass" : "fail"}` }, ok ? t("pass") : t("fail")), " ", pic.verdict.seen || "");
    } else if (pic && pic.live) box.append(el("span", { class: "stamp live" }, t("live")), " ", pic.src);
    else if (pic) box.append(pic.src);
    box.append(el("small", { class: "what" }, t(`view.hint.${three.hint}`)));   // what kind of thing this is
  }

  // The 3D view: the model's GLB copy, loaded once per run, moved by the run's latest plan file.
  function setRun(run) {
    three.run = run;
    $("recorded").hidden = !run.recorded;
    three.view = "picture"; three.chosen = false; three.plans = new Map(); three.roles = null; three.shown = null;
    if (three.viewer) three.viewer.clear();
    setView("picture");
  }

  // The page rebuilds its DOM on a language switch: the viewer's canvas goes with the old DOM, so the
  // viewer is let go here and made again on the new host by the next update.
  function detach() {
    if (three.viewer) three.viewer.dispose();
    three.viewer = null; three.making = null; three.loaded = null; three.loading = null; three.shown = null;
    if (three.retry) { clearTimeout(three.retry); three.retry = 0; }
  }

  function reattach() {
    if (three.run) setRun(three.run);
  }

  function setView(view) {
    three.view = view;
    $("big").classList.toggle("is3d", view === "3d");
    $("stage3d").hidden = view !== "3d";
    $("hint").hidden = view !== "3d";
    $("view-3d").classList.toggle("on", view === "3d");
    $("view-3d").setAttribute("aria-pressed", view === "3d" ? "true" : "false");
    $("view-film").classList.toggle("on", view === "film");
    $("view-film").setAttribute("aria-pressed", view === "film" ? "true" : "false");
    if (view === "3d" && three.viewer) three.viewer.start();
    if (view !== "3d" && three.viewer) three.viewer.stop();
  }

  async function fetchJson(name) {
    if (!three.plans.has(name)) {
      three.plans.set(name, fetch(fileUrl(name)).then((r) => (r.ok ? r.json() : null)).catch(() => null));
    }
    return three.plans.get(name);
  }

  // Piece -> role for the run's model, from its anatomy file; a run that has not counted its pieces yet
  // (a live run just started) leaves the map for the next run on the same model to fill.
  function rolesFor(run) {
    if (!rolesByModel.has(run.model)) {
      const p = fetchJson("anatomy.json").then((anatomy) => {
        if (!anatomy) { rolesByModel.delete(run.model); return {}; }
        return Object.fromEntries(Object.entries(anatomy.pieces || {}).map(([n, pc]) => [n, pc.role]));
      });
      rolesByModel.set(run.model, p);
    }
    return rolesByModel.get(run.model);
  }

  async function ensure3d(kind) {
    const run = three.run;
    if (!run || !run.model) return;
    const url = `api/models/${run.model}.glb`;
    if (three.loaded !== url) caption(null, t("model.loading"));   // on every update until it is in, or the last picture's name stays under an empty stage
    if (!three.viewer) {                             // one viewer, however many updates arrive while the module loads
      if (!three.making) three.making = import("./viewer.mjs").then(({ makeViewer }) => { if (!three.viewer) three.viewer = makeViewer($("stage3d")); });
      await three.making;
      if (!three.viewer) return;
    }
    if (three.loaded !== url) {
      if (!three.loading) {                          // one fetch, however many updates arrive while it is in flight
        const viewer = three.viewer;
        three.loading = viewer.load(url).then(() => { if (three.viewer === viewer) three.loaded = url; }, () => {
          caption(null, t("model.none"));
          if (!three.retry) three.retry = setTimeout(() => { three.retry = 0; if (three.view === "3d") ensure3d(kind); }, 4000);
        }).finally(() => { three.loading = null; });
      }
      await three.loading;
      if (three.loaded !== url || three.run !== run) return;
    }
    if (!kind) {
      if (three.shown !== `${run.id}:idle`) {
        three.viewer.clear(); three.shown = `${run.id}:idle`; three.note = `${t("view.3d")} · ${three.viewer.pieces}`;
        rolesFor(run).then((roles) => { if (three.run === run && three.viewer) three.viewer.setRoles(roles); });   // colour, once the anatomy is known
      }
      caption(null, three.note); return;
    }
    if (three.shown === `${run.id}:${kind}`) { caption(null, three.note); return; }
    const [plan, roles] = await Promise.all([fetchJson(PLAN_FILES[kind]), rolesFor(run)]);
    if (!plan || three.run !== run) return;
    three.roles = roles;
    three.viewer.setShowpiece(kind, plan, three.roles);
    three.shown = `${run.id}:${kind}`;
    three.note = `${t("view.3d")} · ${kind} · ${three.viewer.pieces} / ${three.viewer.meshes}`;
    caption(null, three.note);
  }

  // Three views of the big screen: the picture being painted or judged, the 3D model, or the finished
  // film. The film goes large by itself when a replay reaches its end; a view the viewer chose stays.
  function update(events, beat, replayed) {
    const s = statusOf(beat, events);
    $("status").textContent = statusText(s);
    $("dot").className = `dot ${beat ? "on" : s.key === "finished" ? "done" : ""}`;
    const bar = $("bar");
    bar.classList.toggle("busy", Boolean(beat) && s.pct === null);
    bar.classList.toggle("done", s.key === "finished");
    bar.style.width = s.pct === null ? (beat ? "35%" : "0%") : `${s.pct}%`;
    $("big").classList.toggle("finished", s.key === "finished");
    const pic = bigPicture(events, beat);
    const film = newestFilm(events);
    $("view-film").hidden = !film;
    const kind = showpieceOf(events.flatMap((e) => e.files || []));
    const live = Boolean(beat && beat.newest);
    const idle = !pic && !live && !kind;   // nothing to show yet: the model itself, turning, fills the screen
    if (three.view === "film" && (!film || (!replayed && !three.chosen))) setView("picture");   // the finale is over, or there is no film to show
    if (replayed && film && !three.chosen && three.view !== "film") setView("film");
    else if ((kind || idle) && three.run && three.run.model && !three.chosen && !live && three.view === "picture") setView("3d");
    if (live && three.view !== "picture" && !three.chosen) setView("picture");
    const finished = s.key === "finished" || s.key === "stopped";
    const turning = kind ? "3d" : finished ? "plain" : events.length ? "working" : "idle";   // the 3D view before, during and after a run's plan
    three.hint = three.view === "film" && film ? "film" : three.view === "3d" ? turning : pic && pic.live ? "live" : pic ? "picture" : "idle";
    if (three.view === "3d") { showPicture(pic); ensure3d(kind); }
    else if (three.view === "film" && film) { const shot = { src: film, video: true, live: false, verdict: null }; showPicture(shot); caption(shot); }
    else { showPicture(pic); caption(pic); }
    celebrate(pic);
  }

  return { build, wire, update, setRun, detach, reattach, setTheatre };
}
