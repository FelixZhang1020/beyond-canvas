// The wiring board: every part of the harness as a box, every packaged skill as a tile on the shelf,
// the wires between them, and the marks that move: the request dot and the verdict. Built once
// from the roster; the page lights and moves what is on it. The board speaks English whatever the
// page's language, so the only words here are the roster's names and two group labels.
const SVG = "http://www.w3.org/2000/svg";
const GROUPS = { studio: "studio", "3d": "3D" };

export function svg(tag, attrs = {}, text) {
  const node = document.createElementNS(SVG, tag);
  for (const [k, v] of Object.entries(attrs)) node.setAttribute(k, v);
  if (text !== undefined) node.textContent = text;
  return node;
}

// A name like "Hook: before a tool" takes two lines; anything else takes one.
function nameText(s) {
  const b = s.box;
  const [head, tail] = s.name.includes(": ") ? s.name.split(": ") : [s.name, null];
  const tall = b.h >= 45;                                  // the loop, the tools and the shelf carry their name on the top line
  const text = svg("text", { x: b.x + b.w / 2, y: tall ? b.y + 11 : b.y + b.h / 2 + (tail ? -2 : 2.3), "text-anchor": "middle" });
  text.append(svg("tspan", {}, head));
  if (tail) text.append(svg("tspan", { class: "s", x: b.x + b.w / 2, dy: 8 }, tail));
  return text;
}

function stationBox(s, { onPin, tooltip }) {
  const b = s.box;
  const g = svg("g", { id: `st-${s.id}`, class: "station", tabindex: "0", role: "button", "aria-label": s.name });
  const rect = svg("rect", { class: "st", x: b.x, y: b.y, width: b.w, height: b.h, rx: 5 });
  rect.append(svg("title", {}, tooltip(s)));
  g.append(rect, nameText(s));
  g.onclick = () => onPin(s.id);
  g.onkeydown = (e) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); onPin(s.id); } };
  return g;
}

// An upright phone gets the same parts, tiles and wires laid out tall (the roster's `tall`): the wide board on
// a phone was a 620px strip that swiped, half of it and the moving request off the screen. Ids are unchanged,
// so lighting and the dot work on either arrangement.
export function arranged(roster, tall) {
  if (!tall) return roster;
  const t = roster.tall;
  return { ...roster, view: t.view,
    stations: roster.stations.map((s) => ({ ...s, box: t.boxes[s.id] })),
    skills: roster.skills.map((k) => ({ ...k, tile: t.tiles[k.id] })),
    wires: roster.wires.map((w) => ({ ...w, d: t.wires[w.id] })) };
}

export function buildBoard(roster, { onPin, tooltip, label }) {
  const root = svg("svg", { class: "hv-board", viewBox: roster.view, role: "img", "aria-label": label });
  for (const w of roster.wires) root.append(svg("path", { class: `wire${w.back ? " back" : ""}`, id: `wire-${w.id}`, d: w.d }));
  for (const s of roster.stations) root.append(stationBox(s, { onPin, tooltip }));
  for (const k of roster.skills) {
    const r = k.tile;
    const tile = svg("rect", { class: "tile", id: `tile-${k.id}`, x: r.x, y: r.y, width: r.w, height: r.h, rx: 2 });
    tile.append(svg("title", {}, k.id));
    root.append(tile);
  }
  for (const [group, word] of Object.entries(GROUPS)) {          // the group labels sit above their row of tiles
    const mine = roster.skills.filter((k) => k.group === group);
    root.append(svg("text", { class: "s", x: mine[0].tile.x, y: mine[0].tile.y - 3 }, `${word} ${mine.length}`));
  }
  const shelf = roster.stations.find((s) => s.id === "skills").box;
  root.append(svg("text", { class: "m", id: "skill-name", x: roster.skills[0].tile.x, y: shelf.y + shelf.h - 4 }, ""));
  const judge = roster.stations.find((s) => s.id === "subagent").box;
  root.append(svg("text", { class: "verdict", id: "verdict", x: judge.x + judge.w / 2, y: judge.y - 5, "text-anchor": "middle" }, ""));
  root.append(svg("circle", { class: "halo", id: "halo", r: 6, cx: -10, cy: -10 }), svg("circle", { class: "dot", id: "dot", r: 2.6, cx: -10, cy: -10 }));
  return root;
}

// Light the board for a step: one part, one skill tile, one wire, one verdict; a pinned part keeps its ring.
export function lightBoard(roster, lit, pinned) {
  for (const st of roster.stations) {
    const rect = document.getElementById(`st-${st.id}`).querySelector("rect");
    rect.classList.toggle("lit", st.id === lit.station);
    rect.classList.toggle("pinned", st.id === pinned);
  }
  for (const k of roster.skills) document.getElementById(`tile-${k.id}`).classList.toggle("lit", k.id === lit.skill);
  for (const w of roster.wires) document.getElementById(`wire-${w.id}`).classList.toggle("hot", w.id === lit.wire);
  document.getElementById("skill-name").textContent = lit.skill || "";
  const v = document.getElementById("verdict");
  v.textContent = lit.verdict ? lit.verdict.toUpperCase() : "";
  v.setAttribute("class", `verdict ${lit.verdict || ""}`);
}

// The request dot rides the lit wire; with reduced motion it sits at the wire's end.
export function moveDot(wireId, progress, still) {
  const path = wireId ? document.getElementById(`wire-${wireId}`) : null;
  const len = path ? path.getTotalLength() : 0;
  const p = path ? path.getPointAtLength(Math.min(len, (still ? 1 : progress) * len)) : { x: -10, y: -10 };
  for (const id of ["dot", "halo"]) { const c = document.getElementById(id); c.setAttribute("cx", p.x); c.setAttribute("cy", p.y); }
}
