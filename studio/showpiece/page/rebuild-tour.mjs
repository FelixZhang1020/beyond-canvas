// Playing every attempt one after another: the four rebuilds, then the designs in the order
// rebuild-designs.json lists them, and from the first again after the last (operator). Each attempt is a page
// of its own, so the tour travels in the address: the next page is opened with tour=1 and the speed and the
// key-moments choice it was playing at, and starts playing by itself. Opening any attempt by its own chip
// drops the tour, so a presenter who picks one takes the page back.
import { filesOf, isDesign } from "./rebuild-runs.mjs";

const SPEEDS = ["1", "1.5", "2", "4"];

export const tourOrder = (designs = []) => [1, 2, 3, 4, ...designs.map(({ n }) => `design${n}`)];

// The attempt after this one, the first after the last; an attempt the order does not know starts it again.
export function nextStop(order, run) {
  const at = order.findIndex((key) => String(key) === String(run));
  return order[(at + 1) % order.length];
}

export function tourHref(run, { speed = "1", keys = false } = {}) {
  const query = new URLSearchParams(isDesign(run) ? { design: run.slice(6) } : { run: String(run) });
  query.set("tour", "1");
  if (speed !== "1") query.set("speed", speed);
  if (keys) query.set("keys", "1");
  return `rebuild.html?${query}`;
}

// What the address says about a tour: whether one is on, and the speed and key-moments choice it carries.
export function tourFrom(search) {
  const query = new URLSearchParams(search), speed = query.get("speed");
  return { on: query.get("tour") === "1", speed: SPEEDS.includes(speed) ? speed : "1", keys: query.get("keys") === "1" };
}

// The next attempt's record and hall, fetched while this one plays, so its page opens on them from the browser's
// own copy: over a slow moment of the link a hall took two minutes to come, and the picture waited for it.
export function fetchAhead(run, get = fetch) {
  const { record, hall } = filesOf(run);
  for (const name of [record, `${hall}.json`, `${hall}.glb`]) get(name).then((answer) => answer.arrayBuffer()).catch(() => {});
}
