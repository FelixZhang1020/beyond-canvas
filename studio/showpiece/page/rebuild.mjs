// The replay of a from-nothing hall build: the adopted run, played on the Spark's 3D hall
// (rebuild-hall.mjs) with the bracket close-up (rebuild-model.mjs), one of the three earlier runs
// (?run=1..3, rebuild-runs.mjs) on its own final hall and its own pictures, or a hall designed from a
// written brief (?design=N) on the stages that run kept and the pictures it took. One clock runs
// every step's picture whether or not the replay is playing, so a step you jump to still plays out;
// playing only decides whether the next step follows when this one is done.
import { makeRebuildModel } from "./rebuild-model.mjs";
import { makeHall } from "./rebuild-hall.mjs";
import { makeHood } from "./rebuild-hood.mjs";
import { dressPage, familyStages, filesOf, getJson, isDesign, listDesigns, whichRun } from "./rebuild-runs.mjs";
import { drawMarks, keySeconds, nextKey } from "./rebuild-marks.mjs";
import { compareRuns } from "./rebuild-compare.mjs";
import { fetchAhead, nextStop, tourFrom, tourHref, tourOrder } from "./rebuild-tour.mjs";
import { BRACKET_PHASE_MS, captionOf, caught, durationOf, makeScenes, prepare, refused, repairRounds, sceneOf } from "./rebuild-scenes.mjs";


const $ = (id) => document.getElementById(id);
let words = {};
const t = (key, vars = {}) => (words[key] || key).replace(/\{(\w+)\}/g, (_, k) => String(vars[k] ?? ""));
const clockText = (s) => `${String(Math.floor(s / 60)).padStart(2, "0")}:${String(s % 60).padStart(2, "0")}`;
const run = whichRun(location.search), files = filesOf(run), design = isDesign(run);
const VERIFY = ["inventory", "bearing", "weights", "likeness", "brief", "judge"];
const tour = tourFrom(location.search);

let chapters = [], index = 0, playing = false, elapsed = 0, duration = 1, last = null;
let hall = null, hallState = "loading", scenes = null, protocol = null, total = "";
let bracket = null, bracketReady = false, bracketManual = false, hood = null, laps = 0, keyOnly = false;
let counted = { sets: "–", pieces: "–" }, heights = {}, opening = "rebuild-temple.jpg", bracketError = "";
let touring = tour.on, order = tourOrder();

const scene = () => sceneOf(chapters[index]);
const onHall = (s) => s !== "temple" && s !== "brackets";

// A run's own picture or video, where its tool made one, wins over the 3D: it is the original.
function picture(s) {
  const ch = chapters[index], media = ch.media || null, clip = $("clip");
  const fallback = onHall(s) && hallState === "failed" && run === 4 && !media;
  $("frame").hidden = !(s === "temple" || fallback || (media?.image && !media.video));
  if (media?.image && !media.video) $("frame").src = media.image;
  else if (fallback) $("frame").src = ch.cutaway ? `rebuild-cutaway-${ch.frame}.jpg` : `rebuild-${ch.frame}.jpg`;
  else if (s === "temple") $("frame").src = opening;          // a design opens on its brief's photograph
  clip.hidden = !media?.video;
  if (media?.video) {
    if (!clip.src.endsWith(media.video)) { clip.src = media.video; clip.poster = media.image || ""; }
    clip.currentTime = 0;
    clip.playbackRate = Number($("speed").value);
    clip.play().catch(() => {});
  } else clip.pause();
  const own = !!media || s === "temple";
  $("hall-view").hidden = !onHall(s) || hallState !== "ready" || own;
  $("model-view").hidden = s !== "brackets";
  $("bracket-detail").hidden = s !== "brackets";
  $("player").classList.toggle("has-brackets", s === "brackets");
  if (onHall(s) && hallState === "ready" && !own) hall.start(); else hall?.stop();
  if (s !== "brackets") bracket?.hide();
  const waiting = (onHall(s) && hallState === "loading" && !own) || (s === "brackets" && !bracketReady);
  const failed = s === "brackets" && bracketError;
  $("model-status").hidden = !waiting && !failed;                   // never an empty picture while a model comes
  $("model-status").textContent = failed || t("loading.hall");
}

function bracketPhase(value) {
  bracket.setPhase(value);
  $("bracket-stage-title").textContent = t("bracket.phase", { n: value + 1, title: t(`bracket.p${value}.title`) });
  $("bracket-stage-detail").textContent = t(`bracket.p${value}.detail`, heights);
  for (const [i, button] of Array.from($("bracket-steps").children).entries()) {
    button.classList.toggle("selected", i === value);
    button.setAttribute("aria-current", i === value ? "step" : "false");
  }
}

function enterBrackets() {
  bracketManual = false;
  bracket ||= makeRebuildModel($("model-view"));
  bracket.setScope("single");
  $("bracket-scope").textContent = t("bracket.all", counted);
  bracketPhase(0);
  bracket.show("brackets").then((result) => {
    if (!result) return;
    counted = { sets: result.sets, pieces: result.count.toLocaleString("en-US") };   // counted in the model, not typed
    $("bracket-count").textContent = t("bracket.count", counted);
    if (bracket.scope !== "all") $("bracket-scope").textContent = t("bracket.all", counted);
    bracketError = "";
    if (scene() === "brackets") { bracketReady = true; $("model-status").hidden = true; }
  })
    .catch((error) => {
      bracketError = t("failed", { why: error.message });
      $("model-status").textContent = bracketError;
      $("model-status").hidden = false;
      bracketReady = true;
    });
}

function driveBrackets() {
  if (bracketManual || !bracketReady) return;
  const phase = Math.min(7, Math.floor(elapsed / BRACKET_PHASE_MS));
  if (phase !== bracket.phase) bracketPhase(phase);
  const whole = elapsed >= 8 * BRACKET_PHASE_MS;
  if (whole !== (bracket.scope === "all")) {
    bracket.setScope(whole ? "all" : "single");
    $("bracket-scope").textContent = t(whole ? "bracket.one" : "bracket.all", counted);
    if (whole) $("bracket-stage-detail").textContent = t("bracket.whole", counted);
  }
}

// What the loop is doing at a step. The rebuilds keep the words they were first shown with; a design is
// read from its own record: a refused, broken or sent-back call is the guard, a placing call after a check a repair.
function phaseOf(ch) {
  if (ch.physics || VERIFY.includes(ch.tool)) return "VERIFY";
  if (ch.kind === "think" || ch.kind === "look" || ch.kind === "final") return { think: "PLAN", look: "LOOK", final: "STOP" }[ch.kind];
  if (design) return ch.kind === "stop" ? "STOP" : refused(ch) || ch.kind === "bounce" ? "GUARD" : ch.repair ? "REPAIR" : "ACT";
  return ch.tool === "frames" && ch.step > 44 ? "REPAIR" : [26, 48, 50].includes(ch.step) ? "GUARD" : "ACT";
}

function texts(ch, s) {
  $("kind").textContent = t(`kind.${ch.kind}`) === `kind.${ch.kind}` ? ch.kind : t(`kind.${ch.kind}`);
  $("kind").dataset.kind = ch.kind;
  $("picture-caption").textContent = design && !ch.media && words[`caption.design.${s}`] ? t(`caption.design.${s}`) : captionOf(s, t, ch);
  $("actual-time").textContent = t("time", { at: clockText(ch.elapsed), total });
  $("step").textContent = t("step", { n: ch.step });
  $("chapter-count").textContent = t("count", { n: index + 1, total: chapters.length });
  $("chapter-title").textContent = ch.title;
  $("chapter-detail").textContent = ch.detail;
  $("loop-phase").textContent = phaseOf(ch);
  hood?.show(index);
  $("seek").value = String(index);
  const timeline = $("timeline");
  for (const [i, button] of Array.from(timeline.children).entries()) {
    button.classList.toggle("selected", i === index);
    button.setAttribute("aria-current", i === index ? "step" : "false");
    if (i === index) timeline.scrollTo({ left: button.offsetLeft - timeline.offsetLeft - timeline.clientWidth / 2 + button.clientWidth / 2, behavior: "smooth" });
  }
}

function show(at) {
  index = Math.min(Math.max(at, 0), chapters.length - 1);
  const ch = chapters[index], s = sceneOf(ch);
  elapsed = 0;
  duration = durationOf(ch);
  picture(s);
  if (s === "brackets") enterBrackets();
  if (onHall(s) && hallState === "ready") scenes.enter(ch, index);
  else for (const id of ["load-legend", "physics-panel", "catch", "round"]) $(id).hidden = true;
  texts(ch, s);
}

function tick(now) {
  const dt = last === null ? 0 : Math.min(100, now - last);
  last = now;
  const s = scene();
  let ready = true;
  if (onHall(s) && hallState === "ready") {
    ready = scenes.update(Math.min(1, elapsed / duration));
    $("model-status").hidden = ready;
    if (!ready) $("model-status").textContent = t("loading.motion");
  } else if (onHall(s) && hallState === "loading") ready = false;
  if (s === "brackets") { ready = bracketReady; driveBrackets(); }
  if (ready) elapsed += dt * Number($("speed").value);
  if (playing && ready && elapsed >= duration) {
    const next = keyOnly ? nextKey(chapters, index) : index + 1;       // key moments only skips the rest
    if (next === null || next >= chapters.length) { if (touring) travel(); else pause(); } else show(next);
  }
  requestAnimationFrame(tick);
}

function pause() {
  playing = false;
  $("play").textContent = t("play");
  $("play").setAttribute("aria-label", t("play.label"));
}

function play() {
  if (index === chapters.length - 1) show(0);
  playing = true;
  $("play").textContent = t("pause");
  $("play").setAttribute("aria-label", t("pause.label"));
}

// On to the next attempt of the tour, or to the one named, at the speed and key-moments choice playing now.
function travel(to = nextStop(order, run)) {
  playing = false;
  location.replace(tourHref(to, { speed: $("speed").value, keys: keyOnly }));
}

function tourButton() {
  $("tour").setAttribute("aria-pressed", String(touring));
  if (!words["tour.start"]) return;                   // pressed before the page's words came: boot labels it then
  $("tour").textContent = t(touring ? "tour.stop" : "tour.start");
  $("tour").title = t("tour.title", { n: order.length });
}

// The button after the attempts: every attempt from the first, one after another, round again after the last.
function toggleTour() {
  if (touring) {
    touring = false;
    if (playing) pause();
    const query = new URLSearchParams(location.search);
    query.delete("tour");
    history.replaceState(null, "", `${location.pathname}?${query}`);    // a reload no longer carries on touring
  } else if (String(run) !== String(order[0]) || !chapters.length) return travel(order[0]);
  else { touring = true; show(0); play(); fetchAhead(nextStop(order, run)); }
  tourButton();
}

function toggleKeys() {
  keyOnly = !keyOnly;
  $("keys").setAttribute("aria-pressed", String(keyOnly));
  $("keys").textContent = keyOnly ? t("keys.on") : t("keys.off", { min: Math.max(1, Math.round(keySeconds(chapters, durationOf) / 60)) });
}

function makeTimeline() {
  for (const [i, ch] of chapters.entries()) {
    const button = document.createElement("button");
    button.type = "button";
    button.className = "moment";
    const time = document.createElement("time");
    time.textContent = clockText(ch.elapsed);
    const title = document.createElement("span");
    title.textContent = ch.title;
    button.append(time, title);
    button.dataset.kind = ch.kind;
    if (ch.tool) button.dataset.tool = ch.tool;
    button.classList.toggle("caught", caught(ch));          // the harness stopped something here
    button.onclick = () => show(i);
    $("timeline").append(button);
  }
}

function controls() {
  $("play").onclick = () => (playing ? pause() : play());
  $("previous").onclick = () => show(index - 1);
  $("next").onclick = () => show(index + 1);
  $("seek").oninput = (event) => show(Number(event.target.value));
  for (let i = 0; i < 8; i++) {
    const button = document.createElement("button");
    button.type = "button";
    button.textContent = String(i + 1);
    button.setAttribute("aria-label", t("bracket.button", { n: i + 1 }));
    button.onclick = () => { if (scene() === "brackets" && bracket) { bracketManual = true; pause(); bracketPhase(i); } };
    $("bracket-steps").append(button);
  }
  $("bracket-scope").onclick = () => {
    if (!bracket) return;
    bracketManual = true;
    const all = bracket.scope !== "all";
    bracket.setScope(all ? "all" : "single");
    $("bracket-scope").textContent = t(all ? "bracket.one" : "bracket.all", counted);
  };
  document.addEventListener("keydown", (event) => {
    const focus = document.activeElement?.tagName;
    if (focus === "INPUT" || focus === "SELECT") return;                // the slider and the speed take their own keys
    if (event.code === "Space" && focus !== "BUTTON") { event.preventDefault(); playing ? pause() : play(); }
    if (event.code === "ArrowRight") show(index + 1);
    if (event.code === "ArrowLeft") show(index - 1);
    if (event.code === "BracketRight" || event.code === "BracketLeft") {
      const to = nextKey(chapters, index, event.code === "BracketRight" ? 1 : -1);
      if (to !== null) show(to);
    }
    if (event.code === "KeyK") toggleKeys();
    if (event.code === "KeyH") {                                        // to the details below the player, and back
      if (window.scrollY > 40) window.scrollTo({ top: 0, behavior: "smooth" });
      else $("below").scrollIntoView({ behavior: "smooth" });
    }
    if (/^Digit[1-4]$/.test(event.code)) location.href = event.code === "Digit4" ? "rebuild.html" : `rebuild.html?run=${event.code.slice(5)}`;
  });
  $("keys").onclick = toggleKeys;
}

async function boot() {
  $("tour").onclick = toggleTour;                     // a running tour can be stopped before its attempt has loaded
  try {
    words = await getJson("rebuild-strings.json");
    const listed = await getJson("rebuild-designs.json").catch(() => ({}));
    listDesigns({ $, t, designs: listed.designs || [], path: listed.path || [] });
    order = tourOrder(listed.designs || []);
    const record = await getJson(files.record);
    chapters = prepare(record.steps || []);
    protocol = record.physics_protocol;
    if (!chapters.length || !protocol) throw new Error(`${files.record} incomplete`);
    total = clockText(Math.round(record.measured.wall_seconds));
    opening = record.opening || opening;
    dressPage({ $, t, run, files, record, chapters, total });
    $("seek").max = String(chapters.length - 1);
    $("fig-caught").textContent = String(chapters.filter(caught).length);
    laps = record.harness.limits.laps;
    $("fig-rounds").textContent = `${Math.max(...repairRounds(chapters))} / ${laps}`;
    const placed = chapters.find((ch) => ch.chapter === "brackets");      // the heights the bracket call printed and was given
    if (placed) heights = { top: placed.evidence.match(/bracket top ([\d.]+)/)?.[1] ?? "?",
      a: placed.args?.outrigger?.[0]?.split(",")[1] ?? "?", b: placed.args?.outrigger?.[1]?.split(",")[1] ?? "?" };
    makeTimeline();
    controls();
    drawMarks($("seek-marks"), chapters, t, show);
    toggleKeys(); toggleKeys();                       // sets the button's label with this run's key-moment time
    if (tour.keys) toggleKeys();
    $("speed").value = tour.speed;
    tourButton();
    $("keys-hint").textContent = t("keys.hint");
    compareRuns($, t);
    $("hood-lede").textContent = t("hood.lede");
    hood = makeHood({ $, t, record, chapters });
    hood.build();
    makeHall($("hall-view"), files.hall).then((made) => {
      hall = made;
      hall.record.stages ||= familyStages(chapters, hall.record.pieces);   // an earlier run: families as placed
      scenes = makeScenes({ hall, t, $, protocol, chapters, record });
      hallState = "ready";
      show(index);
      const brackets = chapters.some((ch) => ch.chapter === "brackets");   // next on the link, there by its step
      if (brackets) (bracket ||= makeRebuildModel($("model-view"))).preload().catch(() => {});
      if (touring) fetchAhead(nextStop(order, run));
    }).catch((error) => {
      hallState = "failed";
      $("model-status").textContent = t("failed", { why: error.message });
      $("model-status").hidden = false;
      show(index);
    });
    show(0);
    pause();
    requestAnimationFrame(tick);
    if (touring || new URLSearchParams(location.search).get("autoplay") === "1") play();
  } catch (error) {
    $("chapter-title").textContent = t("failed.page");
    $("chapter-detail").textContent = String(error);
    $("play").disabled = true;
    setTimeout(() => { if (touring) travel(); }, 5000);   // an unread attempt is passed over, so the tour keeps going
  }
}

boot();
