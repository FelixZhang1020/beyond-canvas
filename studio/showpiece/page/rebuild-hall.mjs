// The whole hall as one 3D scene, built from the Spark's union of the seventeen stage models
// (studio/showpiece/rebuild_bake.py). Every piece keeps one row of state in two small textures:
// where it is moved to and whether it stands, and a colour that can cover its material. A stage,
// a repair, a load map and a physics test are all writes to those rows, so 4,331 pieces stay ten
// draw calls. Positions come only from the Spark's files; nothing here invents a piece or a path.
// It is lit and coloured as Blender draws the stage pictures (rebuild_demo.py and the hall-carpenter
// skill's lit_view): one flat colour per family of pieces, a shadowing sun and three soft lights.
import * as THREE from "three";
import { GLTFLoader } from "./vendor/loaders/GLTFLoader.js";
import { mergeGeometries } from "./vendor/utils/BufferGeometryUtils.js";

const WIDTH = 128;
// Blender's base colours for the stage pictures (studio/showpiece/rebuild_demo.py), in linear light.
const PALETTE = {
  stone: [.53, .51, .47], columns: [.33, .16, .09], walls: [.66, .56, .43], tie: [.35, .18, .10], brackets: [.40, .20, .11],
  frame: [.36, .18, .10], purlins: [.37, .19, .10], rafters: [.43, .26, .15], roof_tiles: [.25, .27, .29], ridges: [.19, .20, .22],
  other: [.40, .30, .22],
};
const COVERING = new Set(["roof_tiles", "ridges"]);
const ROOF = new Set(["roof_tiles", "ridges", "rafters", "purlins"]);
const RAMP = [[0, [.12, .10, .45]], [.25, [.05, .55, .85]], [.5, [.15, .75, .30]], [.7, [.95, .85, .15]], [.85, [.95, .45, .08]], [1, [.75, .05, .05]]];
const GREY = [.36, .34, .31];

export function loadColour(kN, [lo, hi]) {
  const t = Math.max(0, Math.min(1, (Math.log(Math.max(kN, 1e-6)) - Math.log(lo)) / (Math.log(hi) - Math.log(lo))));
  const i = Math.max(1, RAMP.findIndex(([at]) => at >= t));
  const [a, ca] = RAMP[i - 1], [b, cb] = RAMP[i];
  const f = (t - a) / (b - a || 1);
  return ca.map((v, k) => v + (cb[k] - v) * f);
}

function patch(material, uniforms) {
  material.onBeforeCompile = (shader) => {
    Object.assign(shader.uniforms, uniforms);
    shader.vertexShader = shader.vertexShader
      .replace("#include <common>", "#include <common>\nattribute float piece;\nuniform sampler2D pieceState;\nuniform sampler2D pieceColour;\nvarying vec4 vPiece;")
      .replace("#include <begin_vertex>", `#include <begin_vertex>
        ivec2 cell = ivec2(int(mod(piece, ${WIDTH}.0)), int(piece / ${WIDTH}.0));
        vec4 state = texelFetch(pieceState, cell, 0);
        vPiece = texelFetch(pieceColour, cell, 0);
        transformed = state.w < .5 ? vec3(0.0) : transformed + state.xyz;`);
    shader.fragmentShader = shader.fragmentShader
      .replace("#include <common>", "#include <common>\nvarying vec4 vPiece;")
      .replace("#include <color_fragment>", "#include <color_fragment>\ndiffuseColor.rgb = mix(diffuseColor.rgb, vPiece.rgb, vPiece.a);");
  };
  return material;
}

async function fetchOk(path, read) {
  const response = await fetch(path);
  if (!response.ok) throw new Error(`${path} HTTP ${response.status}`);
  return read(response);
}

function piecePart(object, id) {
  const geometry = object.geometry.clone();
  geometry.applyMatrix4(object.matrixWorld);
  for (const key of Object.keys(geometry.attributes)) if (key !== "position" && key !== "normal") geometry.deleteAttribute(key);
  if (!geometry.attributes.normal) geometry.computeVertexNormals();
  geometry.setAttribute("piece", new THREE.BufferAttribute(new Float32Array(geometry.attributes.position.count).fill(id), 1));
  return geometry;
}

// lit_view's lights, turned from Blender's z-up into three.js's y-up: a sun from the front right
// that casts the shadows, a key from the front left, one from behind, and a low fill from below.
function lights(scene, home, s) {
  const at = (x, y, z) => new THREE.Vector3(home.x + x * s, home.y + y * s, home.z + z * s);
  const sun = new THREE.DirectionalLight(0xffffff, 2.3);
  sun.position.copy(at(1, 1.4, 1));
  sun.target.position.copy(home);
  sun.castShadow = true;
  sun.shadow.mapSize.set(2048, 2048);
  Object.assign(sun.shadow.camera, { left: -.8 * s, right: .8 * s, top: .8 * s, bottom: -.8 * s, near: .5, far: 4 * s });
  sun.shadow.bias = -.0004;
  sun.shadow.normalBias = .03;
  scene.add(sun, sun.target, new THREE.AmbientLight(0xffffff, .14));
  for (const [x, y, z, strength] of [[-1.5, .6, 1, .85], [.4, 1, -1.6, .45], [-.6, -.5, .8, .3]]) {
    const light = new THREE.DirectionalLight(0xffffff, strength);
    light.position.copy(at(x, y, z));
    light.target.position.copy(home);
    scene.add(light, light.target);
  }
}

function orbitControls(host, orbit) {
  host.addEventListener("pointerdown", (e) => { orbit.dragging = true; orbit.auto = false; orbit.goal = null; host.setPointerCapture(e.pointerId); orbit.x = e.clientX; orbit.y = e.clientY; });
  host.addEventListener("pointermove", (e) => {
    if (!orbit.dragging) return;
    orbit.theta -= (e.clientX - orbit.x) * .006;
    orbit.phi = Math.max(.2, Math.min(1.55, orbit.phi - (e.clientY - orbit.y) * .006));
    orbit.x = e.clientX; orbit.y = e.clientY;
  });
  host.addEventListener("pointerup", () => { orbit.dragging = false; });
  host.addEventListener("wheel", (e) => { e.preventDefault(); orbit.goal = null; orbit.distance = Math.max(4, Math.min(160, orbit.distance * Math.exp(e.deltaY * .001))); }, { passive: false });
}

export async function makeHall(host, stem = "rebuild-hall") {
  const [record, glb] = await Promise.all([
    fetchOk(`${stem}.json`, (r) => r.json()), fetchOk(`${stem}.glb`, (r) => r.arrayBuffer())]);
  const count = record.pieces.length;
  const rows = Math.ceil(count / WIDTH);
  const state = new Float32Array(WIDTH * rows * 4);
  const colour = new Float32Array(WIDTH * rows * 4);
  const stateTex = new THREE.DataTexture(state, WIDTH, rows, THREE.RGBAFormat, THREE.FloatType);
  const colourTex = new THREE.DataTexture(colour, WIDTH, rows, THREE.RGBAFormat, THREE.FloatType);
  const uniforms = { pieceState: { value: stateTex }, pieceColour: { value: colourTex } };
  const family = record.pieces.map(([, f]) => f);

  const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true });
  renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 1.5));
  renderer.toneMapping = THREE.AgXToneMapping;        // Blender 5's own view transform
  renderer.toneMappingExposure = .85;
  renderer.shadowMap.enabled = true;
  renderer.shadowMap.type = THREE.PCFSoftShadowMap;
  host.append(renderer.domElement);
  const scene = new THREE.Scene();
  const camera = new THREE.PerspectiveCamera(36, 1, .1, 800);

  const gltf = await new GLTFLoader().parseAsync(glb, "");
  gltf.scene.updateWorldMatrix(true, true);
  const byFamily = {};
  const box = new THREE.Box3();
  gltf.scene.traverse((object) => {
    if (!object.isMesh) return;
    const id = Number(object.name.replace(/\D/g, ""));
    const geometry = piecePart(object, id);
    geometry.computeBoundingBox();
    box.union(geometry.boundingBox);
    (byFamily[PALETTE[family[id]] ? family[id] : "other"] ||= []).push(geometry);
  });
  const depth = patch(new THREE.MeshDepthMaterial({ depthPacking: THREE.RGBADepthPacking }), uniforms);   // shadows follow the pieces
  for (const [name, found] of Object.entries(byFamily)) {
    const parts = found.some((g) => !g.index) ? found.map((g) => (g.index ? g.toNonIndexed() : g)) : found;
    const colour = new THREE.Color().setRGB(...PALETTE[name]);
    const material = patch(new THREE.MeshStandardMaterial({ color: colour, roughness: .82, metalness: 0, side: THREE.DoubleSide }), uniforms);
    const mesh = new THREE.Mesh(mergeGeometries(parts, false), material);
    Object.assign(mesh, { frustumCulled: false, castShadow: true, receiveShadow: true, customDepthMaterial: depth });
    scene.add(mesh);
    for (const part of found) part.dispose();
  }
  const size = box.getSize(new THREE.Vector3());
  const home = box.getCenter(new THREE.Vector3());
  lights(scene, home, Math.max(size.x, size.y, size.z));
  // The stage pictures' camera: the front right corner, a little above (lit_view).
  const orbit = { theta: 1.09, phi: 1.25, distance: size.length() * 1.05, target: home.clone(), goal: null, dragging: false, auto: true };
  orbitControls(host, orbit);
  function resize() {
    const w = host.clientWidth, h = host.clientHeight;
    if (!w || !h) return;
    renderer.setSize(w, h, false);
    camera.aspect = w / h;
    camera.updateProjectionMatrix();
  }
  new ResizeObserver(resize).observe(host);

  // A stage is shown whole: each tool call placed a whole family of pieces at once, and so does this.
  const shown = new Uint8Array(count);
  function setStage(key, { cutaway = false } = {}) {
    const wanted = new Set(record.stages[key] || []);
    for (let id = 0; id < count; id++) {
      const on = wanted.has(id) && !(cutaway && ROOF.has(family[id]));
      state[id * 4 + 3] = on ? 1 : 0;
      state[id * 4] = state[id * 4 + 1] = state[id * 4 + 2] = 0;
      shown[id] = on;
    }
    stateTex.needsUpdate = true;
  }
  function piecesOf(key, names) { return (record.stages[key] || []).filter((id) => names.includes(family[id])); }

  // Flashes: a family the tool has just placed glows and fades back to its own colour; a frame the tool
  // took down glows red and goes. `then` is what the pieces keep: nothing, a colour, or "gone".
  let effects = [];
  function flash(ids, rgb, ms, then = null) {
    const t0 = performance.now();
    effects.push({ ids, rgb, t0, t1: t0 + ms, then });
  }
  function paintEffect(e, t) {
    const done = t >= 1;
    for (const id of e.ids) {
      if (done && e.then === "gone") { state[id * 4 + 3] = 0; shown[id] = 0; colour[id * 4 + 3] = 0; }
      else if (done && e.then) colour.set([...e.then, 1], id * 4);
      else colour.set([...e.rgb, done ? 0 : e.then ? 1 : 1 - t], id * 4);
    }
  }
  function finishEffects() {
    for (const e of effects) paintEffect(e, 1);
    effects = [];
    stateTex.needsUpdate = colourTex.needsUpdate = true;
  }

  function clearColour() { colour.fill(0); colourTex.needsUpdate = true; }
  function mark(ids, rgb) { for (const id of ids) colour.set([...rgb, 1], id * 4); colourTex.needsUpdate = true; }
  function hideFamilies(names) {
    for (let id = 0; id < count; id++) if (names.includes(family[id])) { state[id * 4 + 3] = 0; shown[id] = 0; }
    stateTex.needsUpdate = true;
  }

  // The weight test, as the load-path skill paints it: pieces take their colour roof first, at
  // the frame flow.json gives each; ground and walls keep their material, the rest wait in grey.
  function paintLoads(round, progress) {
    const data = record.rounds[round];
    data.last ??= Math.max(...data.loads.map(([, , reveal]) => reveal));   // the wave then holds; stretch it over the step
    const frame = progress * (data.last + 1);
    for (let id = 0; id < count; id++) colour.set([...GREY, family[id] === "stone" || family[id] === "walls" ? 0 : 1], id * 4);
    for (const [id, kN, reveal] of data.loads) if (reveal <= frame) colour.set([...loadColour(kN, record.scale_kN), 1], id * 4);
    colourTex.needsUpdate = true;
  }

  const motions = new Map();
  function motion(round, tag) {
    const key = `${tag}-${round}`;
    if (!motions.has(key)) {
      motions.set(key, fetchOk(`rebuild-${tag}-${round}.gz`, async (r) => ({
        head: record.rounds[round][tag],
        values: new Int16Array(await new Response(r.body.pipeThrough(new DecompressionStream("gzip"))).arrayBuffer()),
      })));
    }
    return motions.get(key);
  }
  // Blender's x, y, z are three.js's x, z, -y. `scale` magnifies travel so millimetres can be seen.
  function pose(track, progress, scale) {
    const { head, values } = track;
    const n = head.ids.length, at = Math.max(0, Math.min(head.samples - 1, progress * (head.samples - 1)));
    const s0 = Math.floor(at), s1 = Math.min(head.samples - 1, s0 + 1), f = at - s0;
    const unit = head.unit_mm / 1000 * scale;
    for (let j = 0; j < n; j++) {
      const id = head.ids[j], a = (s0 * n + j) * 3, b = (s1 * n + j) * 3;
      const x = values[a] + (values[b] - values[a]) * f;
      const y = values[a + 1] + (values[b + 1] - values[a + 1]) * f;
      const z = values[a + 2] + (values[b + 2] - values[a + 2]) * f;
      state[id * 4] = x * unit; state[id * 4 + 1] = z * unit; state[id * 4 + 2] = -y * unit;
    }
    stateTex.needsUpdate = true;
  }

  function look(view) {
    const d = size.length();
    const views = {
      whole: { target: home, distance: d * 1.05, phi: 1.25 },
      ends: { target: new THREE.Vector3(home.x, home.y + size.y * .15, home.z), distance: d * .8, phi: .95 },
      frame: { target: new THREE.Vector3(home.x, home.y - size.y * .1, home.z), distance: d * .92, phi: 1.02 },
      low: { target: new THREE.Vector3(home.x, box.min.y + size.y * .25, home.z), distance: d * .82, phi: 1.2 },
    };
    orbit.goal = views[view] || views.whole;
    orbit.auto = true;
  }

  let raf = 0, active = false;
  function frame(now) {
    if (!active) { raf = 0; return; }
    raf = requestAnimationFrame(frame);
    if (effects.length) {
      effects = effects.filter((e) => {
        const t = Math.max(0, Math.min(1, (now - e.t0) / (e.t1 - e.t0)));
        paintEffect(e, t);
        return t < 1;
      });
      stateTex.needsUpdate = colourTex.needsUpdate = true;
    }
    if (orbit.goal) {
      orbit.target.lerp(orbit.goal.target, .04);
      orbit.distance += (orbit.goal.distance - orbit.distance) * .04;
      orbit.phi += (orbit.goal.phi - orbit.phi) * .04;
    }
    if (orbit.auto && !orbit.dragging) orbit.theta += .0012;
    const { target, distance, theta, phi } = orbit;
    camera.position.set(target.x + distance * Math.sin(phi) * Math.cos(theta), target.y + distance * Math.cos(phi), target.z + distance * Math.sin(phi) * Math.sin(theta));
    camera.lookAt(target);
    renderer.render(scene, camera);
  }
  function start() { active = true; resize(); if (!raf) raf = requestAnimationFrame(frame); }
  function stop() { active = false; }
  function changed(from, to) {
    const a = new Set(record.stages[from] || []), b = new Set(record.stages[to] || []);
    return { added: [...b].filter((id) => !a.has(id)), removed: [...a].filter((id) => !b.has(id)) };
  }
  return { record, setStage, piecesOf, flash, finishEffects, clearColour, mark, hideFamilies, paintLoads, motion, pose, look,
    start, stop, changed };
}
