// Pure maths from the agent's result files to the live 3D view: where each piece is at a
// moment of a showpiece, what colour it wears, where the camera is. Blender is Z-up and the
// GLB is Y-up, so every vector from a plan passes through yUp. No DOM, so node tests them.

export const yUp = ([x, y, z]) => [x, z, -y];

export function ease(p) {
  const t = Math.min(1, Math.max(0, p));
  return t < 0.5 ? 2 * t * t : 1 - ((-2 * t + 2) ** 2) / 2;
}

// A joint close-up runs on derived copies named "... | JOINT"; the live view moves the piece itself.
export const pieceOf = (name) => String(name).replace(/ \| JOINT$/, "");

// Take-apart: each piece slides along its plan offset as the pull opens (0 closed, 1 open).
export function explodeAt(plan, p) {
  const k = ease(p);
  const out = {};
  for (const piece of plan.pieces || []) out[pieceOf(piece.name)] = yUp(piece.offset.map((v) => v * k));
  return out;
}

// Build-up: the scenes arrive one after another; a piece of the current scene drops from `drop` above.
export function raiseAt(scenes, p, drop = 3) {
  const list = scenes.scenes || [];
  const n = list.length;
  if (!n) return { visible: new Set(), offsets: {} };
  const t = Math.min(1, Math.max(0, p)) * n;
  const current = Math.min(n - 1, Math.floor(t));
  const local = ease(t - current);
  const visible = new Set();
  const offsets = {};
  list.forEach((scene, i) => {
    if (i > current) return;
    for (const name of scene.pieces || []) {
      visible.add(name);
      if (i === current && p < 1) offsets[name] = [0, drop * (1 - local), 0];
    }
  });
  return { visible, offsets };
}

// Load path: blue for a piece carrying little, red for one carrying much, on a log scale.
export function loadTint(loads, name, loKN = 0.5, hiKN = 1000) {
  const piece = (loads.pieces || {})[name];
  if (!piece) return null;
  const kN = Math.max(loKN, (piece.carries_N || 0) / 1000);
  const t = Math.min(1, Math.max(0, Math.log(kN / loKN) / Math.log(hiKN / loKN)));
  return [0.25 + 0.75 * t, 0.35 + 0.3 * (1 - Math.abs(t - 0.5) * 2), 0.95 - 0.85 * t];
}

// Tour: the camera at a moment of the film, from the segment whose frames hold it.
export function tourAt(tour, p) {
  const segs = tour.segments || [];
  const total = tour.frames || (segs.length ? segs[segs.length - 1].frames[1] : 0);
  if (!segs.length || !total) return null;
  const frame = 1 + Math.min(1, Math.max(0, p)) * (total - 1);
  const seg = segs.find((s) => frame <= s.frames[1]) || segs[segs.length - 1];
  const [a, b] = seg.frames;
  const k = b > a ? Math.min(1, Math.max(0, (frame - a) / (b - a))) : 0;
  const mix = (u, v) => u.map((x, i) => x + (v[i] - x) * k);
  return { at: yUp(mix(seg.at[0], seg.at[1])), look: yUp(mix(seg.look[0], seg.look[1])), hidden: seg.hidden_roles || [], name: seg.name };
}

// Settle: a piece that fell or shifted sinks by how far it dropped, and is marked.
export function settleShift(settle, name) {
  const piece = (settle.pieces || {})[name];
  if (!piece) return null;
  return { offset: [0, -(piece.drop_m || 0), 0], moved: (piece.moved_m || 0) > 0.1, fell: (piece.moved_m || 0) > 1 };
}

// Which showpiece a run holds, by the plan files it wrote; the last one written wins.
export function showpieceOf(files) {
  const known = [["explode.json", "explode"], ["scenes.json", "raise"], ["loads.json", "load"], ["tour.json", "tour"], ["settle.json", "settle"], ["collapse.json", "settle"]];
  let found = null;
  for (const name of files) {
    const hit = known.find(([file]) => file === name);
    if (hit) found = hit[1];
  }
  return found;
}

// How the pieces are grouped for drawing: what moves together is one mesh, so a hall of eight
// thousand pieces is a few dozen draw calls. A key per piece name; "static" never moves.
export function groupOf(kind, plan, roles = {}) {
  if (kind === "explode") {
    const moving = new Set((plan.pieces || []).filter((p) => p.offset.some((v) => v !== 0)).map((p) => pieceOf(p.name)));
    return (name) => (moving.has(name) ? `p:${name}` : "static");
  }
  if (kind === "raise") {
    const scene = {};
    (plan.scenes || []).forEach((s, i) => { for (const name of s.pieces || []) scene[name] = i; });
    return (name) => (name in scene ? `s:${scene[name]}` : "static");
  }
  if (kind === "tour") return (name) => `r:${roles[name] || "none"}`;
  const roof = (name) => (ROOF.has(roles[name]) ? `r:${roles[name]}` : "static");   // the roof lifts off to show the frame
  if (kind === "settle") return (name) => { const s = settleShift(plan, name); return s && s.moved ? `p:${name}` : roof(name); };
  if (kind === "load") return roof;
  return () => "static";
}

// The roles the load path and the settle test hide, as their films do, so the frame shows.
export const ROOF = new Set(["covering", "rafter"]);

// The colour a piece wears by its role, the same on every view: timber warm, the roof's tiles
// grey-blue, rafters a darker wood, walls plaster, the ground stone; anything else pale.
const ROLE_TINT = { timber: [0.72, 0.50, 0.31], rafter: [0.60, 0.40, 0.25], covering: [0.36, 0.40, 0.46], wall: [0.90, 0.85, 0.75], ground: [0.66, 0.63, 0.58] };
export function roleTint(role) { return ROLE_TINT[role] || [0.82, 0.79, 0.73]; }
