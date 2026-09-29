// The moments a presenter jumps to: every catch, every repair round, the pass and the ending, marked on
// the slider; and the "key moments only" play, which skips thinking, reading and routine checks. What
// counts as key is read from each step's scene and the harness's own catches, never from step numbers.
import { caught } from "./rebuild-scenes.mjs";

const KEY_SCENES = new Set(["build", "brackets", "refused", "repair", "passed"]);
const TESTS = new Set(["weights", "settle", "shake"]);

export function isKey(ch) {
  return KEY_SCENES.has(ch.scene) || caught(ch) || ch.kind === "final" || ch.kind === "stop" || !!ch.media
    || (ch.full && TESTS.has(ch.scene));
}

// The next key moment after (or before) a step, or null when there is none.
export function nextKey(chapters, from, direction = 1) {
  for (let i = from + direction; i >= 0 && i < chapters.length; i += direction) if (isKey(chapters[i])) return i;
  return null;
}

function markOf(ch) {
  if (caught(ch)) return "caught";
  if (ch.scene === "repair") return "repair";
  if (ch.scene === "passed") return "pass";
  if (ch.kind === "final" || ch.kind === "stop") return "end";
  return null;
}

// One button on the slider per marked step, placed where the slider's thumb stands for that step.
export function drawMarks(host, chapters, t, jump) {
  host.replaceChildren();
  const last = Math.max(1, chapters.length - 1);
  chapters.forEach((ch, i) => {
    const kind = markOf(ch);
    if (!kind) return;
    const mark = document.createElement("button");
    mark.type = "button";
    mark.className = `mark ${kind}`;
    mark.style.left = `${(i / last) * 100}%`;
    mark.title = t("mark.title", { n: ch.step, what: ch.title });
    mark.setAttribute("aria-label", mark.title);
    mark.onclick = () => jump(i);
    host.append(mark);
  });
}

// Total playing time of the key moments only, for the toggle's own label.
export function keySeconds(chapters, durationOf) {
  return Math.round(chapters.filter(isKey).reduce((sum, ch) => sum + durationOf(ch), 0) / 1000);
}
