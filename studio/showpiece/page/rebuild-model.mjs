// The bracket sets exported from the logged Blender checkpoint on Spark, taken apart in their
// eight assembly phases. This viewer only adds navigation and phase colours; the whole hall is
// rebuild-hall.mjs.
import * as THREE from "three";
import { GLTFLoader } from "./vendor/loaders/GLTFLoader.js";
import { mergeGeometries } from "./vendor/utils/BufferGeometryUtils.js";

// The eight assembly phases, found by the part names the placing tool gives; their words are in
// rebuild-strings.json (bracket.p0 to bracket.p7).
const phases = [
  { match: /base block/ },
  { match: /tier 1 arm/ },
  { match: /tier 1 block/ },
  { match: /tier 2 arm/ },
  { match: /tier 2 block/ },
  { match: /tier 3 arm/ },
  { match: /tier 3 block/ },
  { match: /outrigger/ },
];

function withPlanarUv(source, matrix, name) {
  const geometry = source.index ? source.toNonIndexed() : source.clone();
  geometry.applyMatrix4(matrix);
  for (const key of Object.keys(geometry.attributes)) if (key !== "position" && key !== "normal") geometry.deleteAttribute(key);
  const p = geometry.attributes.position;
  const n = geometry.attributes.normal;
  const uv = new Float32Array(p.count * 2);
  const scale = /Roof|Tile|Ridge|Hip|Eave board/i.test(name) ? .24 : /Platform|Paving|Stone|Ground/i.test(name) ? .7 : .9;
  for (let i = 0; i < p.count; i++) {
    const ax = n ? Math.abs(n.getX(i)) : 0;
    const ay = n ? Math.abs(n.getY(i)) : 0;
    const az = n ? Math.abs(n.getZ(i)) : 0;
    const x = p.getX(i), y = p.getY(i), z = p.getZ(i);
    if (ay >= ax && ay >= az) { uv[i * 2] = x * scale; uv[i * 2 + 1] = z * scale; }
    else if (ax >= az) { uv[i * 2] = z * scale; uv[i * 2 + 1] = y * scale; }
    else { uv[i * 2] = x * scale; uv[i * 2 + 1] = y * scale; }
  }
  geometry.setAttribute("uv", new THREE.BufferAttribute(uv, 2));
  if (!n) geometry.computeVertexNormals();
  return geometry;
}

export function makeRebuildModel(host) {
  const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true });
  renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 1.5));
  host.append(renderer.domElement);
  const scene = new THREE.Scene();
  scene.add(new THREE.HemisphereLight(0xffeee0, 0x606877, 2.1));
  const sun = new THREE.DirectionalLight(0xffe8c6, 2.5);
  sun.position.set(8, 18, 13);
  scene.add(sun);
  const camera = new THREE.PerspectiveCamera(38, 1, .01, 1000);
  const accent = phases.map((_, i) => new THREE.MeshStandardMaterial({ color: [0xd2a05b, 0x9e603b, 0x71b6a5, 0xac6842, 0x8fb1a0, 0xbf7648, 0xc8bd82, 0xe2a14c][i], side: THREE.DoubleSide, roughness: .82 }));
  const cache = new Map();
  const drawn = [];
  const orbit = { theta: .78, phi: 1.1, distance: 12, center: new THREE.Vector3(), dragging: false, auto: true };
  let active = false, raf = 0, mode = "", scope = "single", phase = 0, selected = "", request = 0, sets = 0;

  host.addEventListener("pointerdown", event => { orbit.dragging = true; orbit.auto = false; host.setPointerCapture(event.pointerId); host.dataset.lastX = event.clientX; host.dataset.lastY = event.clientY; });
  host.addEventListener("pointermove", event => {
    if (!orbit.dragging) return;
    orbit.theta -= (event.clientX - Number(host.dataset.lastX)) * .006;
    orbit.phi = Math.max(.15, Math.min(2.6, orbit.phi - (event.clientY - Number(host.dataset.lastY)) * .006));
    host.dataset.lastX = event.clientX; host.dataset.lastY = event.clientY;
  });
  host.addEventListener("pointerup", () => { orbit.dragging = false; });
  host.addEventListener("wheel", event => { event.preventDefault(); orbit.distance = Math.max(.4, Math.min(180, orbit.distance * Math.exp(event.deltaY * .001))); orbit.auto = false; }, { passive: false });

  function resize() {
    const width = host.clientWidth, height = host.clientHeight;
    if (!width || !height) return;
    renderer.setSize(width, height, false);
    camera.aspect = width / height;
    camera.updateProjectionMatrix();
  }
  new ResizeObserver(resize).observe(host);

  function frame() {
    if (!active) return;
    raf = requestAnimationFrame(frame);
    if (orbit.auto) orbit.theta += .0007;
    const { center, distance, theta, phi } = orbit;
    camera.position.set(center.x + distance * Math.sin(phi) * Math.cos(theta), center.y + distance * Math.cos(phi), center.z + distance * Math.sin(phi) * Math.sin(theta));
    camera.lookAt(center);
    renderer.render(scene, camera);
  }

  async function piecesFor(which) {
    const source = "brackets";
    if (cache.has(source)) return cache.get(source);
    const response = await fetch("rebuild-brackets.glb");
    if (!response.ok) throw new Error(`rebuild-brackets.glb HTTP ${response.status}`);
    const gltf = await new GLTFLoader().parseAsync(await response.arrayBuffer(), "");
    gltf.scene.updateWorldMatrix(true, true);
    const original = new Map();
    for (const node of gltf.parser.json.nodes || []) if (node.name) original.set(THREE.PropertyBinding.sanitizeNodeName(node.name), node.name);
    const pieces = [];
    gltf.scene.traverse(object => {
      if (!object.isMesh) return;
      const name = original.get(object.name) || object.name;
      if (source === "brackets" && !name.startsWith("Bracket ")) return;
      const split = name.split(" | ");
      pieces.push({ name, set: split[0], part: split[1] || "", geometry: withPlanarUv(object.geometry, object.matrixWorld, name) });
    });
    cache.set(source, pieces);
    if (source === "brackets") {
      const counts = new Map();
      for (const piece of pieces) counts.set(piece.set, (counts.get(piece.set) || 0) + 1);
      selected = [...counts].filter(([name]) => !name.includes("between")).sort((a, b) => b[1] - a[1])[0]?.[0] || "";
      sets = counts.size;
    }
    return pieces;
  }

  function phaseOf(part) { return phases.findIndex(item => item.match.test(part)); }
  function clearDrawn() { for (const mesh of drawn) { scene.remove(mesh); mesh.geometry.dispose(); } drawn.length = 0; }
  function addMerged(parts, material) {
    if (!parts.length) return;
    const geometry = mergeGeometries(parts.map(piece => piece.geometry), false);
    if (!geometry) throw new Error("the bracket pieces could not be merged");
    const mesh = new THREE.Mesh(geometry, material);
    scene.add(mesh);
    drawn.push(mesh);
  }
  function fit(parts, closer = false) {
    const box = new THREE.Box3();
    for (const piece of parts) box.union(new THREE.Box3().setFromBufferAttribute(piece.geometry.attributes.position));
    if (box.isEmpty()) return;
    box.getCenter(orbit.center);
    const span = box.getSize(new THREE.Vector3());
    orbit.distance = Math.max(1, span.length() * (closer ? 1.38 : 1.28));
    camera.near = Math.max(.01, orbit.distance / 500);
    camera.far = orbit.distance * 25;
    camera.updateProjectionMatrix();
    orbit.auto = true;
  }
  function draw() {
    clearDrawn();
    const chosen = (cache.get("brackets") || []).filter(piece => scope === "all" || piece.set === selected);
    for (let i = 0; i < phases.length; i++) addMerged(chosen.filter(piece => phaseOf(piece.part) === i && i <= phase), accent[i]);
    fit(chosen, scope === "single");
    resize();
  }
  async function show(which) {
    const current = ++request;
    await piecesFor(which);
    if (current !== request) return null;
    if (mode !== which) { mode = which; draw(); }
    active = true;
    resize();
    if (!raf) raf = requestAnimationFrame(frame);
    return { count: cache.get("brackets").length, sets, selected };
  }
  function hide() { request++; active = false; cancelAnimationFrame(raf); raf = 0; }
  function setPhase(value) { phase = Math.max(0, Math.min(phases.length - 1, value)); if (mode) draw(); return phases[phase]; }
  function setScope(value) { scope = value === "all" ? "all" : "single"; if (mode) draw(); }
  return { show, hide, setPhase, setScope, phases, get phase() { return phase; }, get scope() { return scope; } };
}
