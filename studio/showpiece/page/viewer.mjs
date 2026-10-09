// The live 3D view on the agent's screen: the model's GLB copy in three.js, drag to turn,
// wheel to zoom, a slow turn until touched; the pieces move the way the agent's plans say.
// The pieces are kept as a library of coloured geometries and drawn merged by what moves
// together, so a hall of eight thousand pieces is a few dozen draw calls.
import * as THREE from "three";
import { GLTFLoader } from "./vendor/loaders/GLTFLoader.js";
import { mergeGeometries } from "./vendor/utils/BufferGeometryUtils.js";
import { explodeAt, raiseAt, loadTint, tourAt, settleShift, groupOf, ROOF, roleTint } from "./plans.mjs";

const CYCLE_MS = { explode: 27000, raise: 42000, tour: 48000, settle: 18000, load: 18000 };   // a third of the first speed, on request
const HOLD = 0.78;   // the last part of every cycle holds the end pose
const FELL = [0.83, 0.23, 0.23];
const SHIFTED = [0.98, 0.62, 0.26];

export function makeViewer(host) {
  const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true });
  renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 1.5));   // flat-shaded pieces gain nothing above this; a big dense screen gains half its pixels back
  host.append(renderer.domElement);
  const scene = new THREE.Scene();
  const camera = new THREE.PerspectiveCamera(38, 16 / 9, 0.05, 4000);
  scene.add(new THREE.HemisphereLight(0xfff6e8, 0xd9c7b2, 1.4));
  const sun = new THREE.DirectionalLight(0xfff1dc, 2.0);
  sun.position.set(1, 1.6, 0.8);
  scene.add(sun);
  const fill = new THREE.DirectionalLight(0xe8f0ff, 0.7);
  fill.position.set(-1, 0.5, -0.6);
  scene.add(fill);
  const material = new THREE.MeshStandardMaterial({ vertexColors: true, flatShading: true, roughness: 0.85, metalness: 0.0 });
  const orbit = { theta: 0.7, phi: 1.1, dist: 10, target: new THREE.Vector3(), auto: true };
  const library = new Map();   // piece name -> [{ geometry (world space), colour }]
  const drawn = new Map();     // group key -> mesh
  let roles = {}, show = null, t0 = 0, raf = 0, dragging = false, last = null;

  host.addEventListener("pointerdown", (e) => { dragging = true; last = [e.clientX, e.clientY]; orbit.auto = false; host.setPointerCapture(e.pointerId); });
  host.addEventListener("pointermove", (e) => {
    if (!dragging) return;
    const [dx, dy] = [e.clientX - last[0], e.clientY - last[1]];
    last = [e.clientX, e.clientY];
    orbit.theta -= dx * 0.006;
    orbit.phi = Math.min(1.5, Math.max(0.12, orbit.phi - dy * 0.006));
  });
  host.addEventListener("pointerup", () => { dragging = false; });
  host.addEventListener("wheel", (e) => { e.preventDefault(); orbit.dist *= Math.exp(e.deltaY * 0.0012); orbit.auto = false; }, { passive: false });

  function resize() {
    const w = host.clientWidth, h = host.clientHeight;
    if (!w || !h) return;
    renderer.setSize(w, h, false);
    camera.aspect = w / h;
    camera.updateProjectionMatrix();
  }
  new ResizeObserver(resize).observe(host);

  function placeCamera() {
    if (show && show.pose) {
      camera.position.set(...show.pose.at);
      camera.lookAt(...show.pose.look);
      return;
    }
    const { theta, phi, dist, target } = orbit;
    camera.position.set(target.x + dist * Math.sin(phi) * Math.cos(theta), target.y + dist * Math.cos(phi), target.z + dist * Math.sin(phi) * Math.sin(theta));
    camera.lookAt(target);
  }

  // Each piece's meshes as world-space geometry, with the material's colour remembered.
  function shelve(name, object) {
    object.updateWorldMatrix(true, true);
    const parts = [];
    object.traverse((m) => {
      if (!m.isMesh) return;
      const g = m.geometry.index ? m.geometry.toNonIndexed() : m.geometry.clone();
      g.applyMatrix4(m.matrixWorld);
      for (const key of Object.keys(g.attributes)) if (key !== "position") g.deleteAttribute(key);
      const c = m.material && m.material.color ? m.material.color : new THREE.Color(0.8, 0.8, 0.8);
      parts.push({ geometry: g, colour: [c.r, c.g, c.b] });
    });
    if (parts.length) library.set(name, parts);
  }

  function coloured(geometry, [r, g, b]) {
    const n = geometry.attributes.position.count;
    const colours = new Float32Array(n * 3);
    for (let i = 0; i < n; i += 1) { colours[i * 3] = r; colours[i * 3 + 1] = g; colours[i * 3 + 2] = b; }
    const out = geometry.clone();
    out.setAttribute("color", new THREE.BufferAttribute(colours, 3));
    return out;
  }

  // Draw the library merged by group; `tintOf(name)` may recolour a piece for this showpiece.
  function rebuild(groupKey, tintOf = () => null) {
    for (const mesh of drawn.values()) { scene.remove(mesh); mesh.geometry.dispose(); }
    drawn.clear();
    const buckets = new Map();
    for (const [name, parts] of library) {
      const key = groupKey(name);
      if (!buckets.has(key)) buckets.set(key, []);
      const tint = tintOf(name);
      for (const part of parts) buckets.get(key).push(coloured(part.geometry, tint || part.colour));
    }
    for (const [key, geometries] of buckets) {
      const mesh = new THREE.Mesh(mergeGeometries(geometries, false), material);
      for (const g of geometries) g.dispose();
      mesh.name = key;
      scene.add(mesh);
      drawn.set(key, mesh);
    }
  }

  // Fit the view to the pieces, leaving out the one with the widest footprint (a courtyard, a slab).
  function fit() {
    const boxes = [...library].map(([name, parts]) => {
      const box = new THREE.Box3();
      for (const part of parts) box.union(new THREE.Box3().setFromBufferAttribute(part.geometry.attributes.position));
      return { name, box, span: box.getSize(new THREE.Vector3()).length() };
    });
    if (!boxes.length) return;
    boxes.sort((a, b) => b.span - a.span);
    const fitBox = new THREE.Box3();
    for (const { box } of boxes.slice(boxes.length > 1 ? 1 : 0)) fitBox.union(box);
    const size = fitBox.getSize(new THREE.Vector3());
    fitBox.getCenter(orbit.target);
    orbit.dist = (size.length() / 2) / Math.tan((camera.fov * Math.PI) / 360) * 1.15;
    camera.near = orbit.dist / 200;
    camera.far = orbit.dist * 60;
    camera.updateProjectionMatrix();
  }

  function apply(p) {
    if (!show) return;
    const { kind, plan } = show;
    if (kind === "explode") {
      const off = explodeAt(plan, p);
      for (const [key, mesh] of drawn) {
        const d = key.startsWith("p:") ? off[key.slice(2)] : null;
        if (d) mesh.position.set(d[0], d[1], d[2]);
      }
    } else if (kind === "raise") {
      const { visible, offsets } = raiseAt(plan, p);
      for (const [key, mesh] of drawn) {
        if (!key.startsWith("s:")) continue;
        const first = show.sceneNames[Number(key.slice(2))][0];
        mesh.visible = visible.has(first);
        mesh.position.y = offsets[first] ? offsets[first][1] : 0;
      }
    } else if (kind === "tour") {
      show.pose = tourAt(plan, p);
      for (const [key, mesh] of drawn) mesh.visible = !(show.pose && show.pose.hidden.includes(key.slice(2)));
    } else if (kind === "load" || kind === "settle") {
      for (const [key, mesh] of drawn) if (key.startsWith("r:")) mesh.visible = !ROOF.has(key.slice(2));
    }
  }

  // The pull-apart is watched up close: the view settles on the pieces that move.
  function focusOnMovers() {
    const box = new THREE.Box3();
    for (const [key, mesh] of drawn) if (key.startsWith("p:")) { mesh.geometry.computeBoundingBox(); box.union(mesh.geometry.boundingBox); }
    if (box.isEmpty()) return;
    const size = box.getSize(new THREE.Vector3());
    box.getCenter(orbit.target);
    orbit.dist = Math.max(size.x, size.y, size.z) * 1.9 + size.y * 1.5;
    orbit.phi = 1.15;
  }

  function frame(now) {
    raf = requestAnimationFrame(frame);
    if (orbit.auto && !dragging) orbit.theta += 0.0008;   // one turn in about two minutes, on request
    if (show) apply(Math.min(1, ((now - t0) % CYCLE_MS[show.kind]) / (CYCLE_MS[show.kind] * HOLD)));
    placeCamera();
    renderer.render(scene, camera);
  }

  function start() { if (!raf) { resize(); raf = requestAnimationFrame(frame); } }
  function stop() { if (raf) { cancelAnimationFrame(raf); raf = 0; } }

  // The GLB copy of a model: each top-level node is one piece, found again by its Blender name.
  async function load(url) {
    const response = await fetch(url);
    if (!response.ok) throw new Error(`model ${response.status}`);
    const gltf = await new GLTFLoader().parseAsync(await response.arrayBuffer(), "");
    show = null;
    library.clear();
    // The loader rewrites node names (spaces, dots); the GLB's own node list keeps the Blender
    // names, so each rewritten name is mapped back through the same rewriting.
    const original = new Map();
    for (const def of gltf.parser.json.nodes || []) if (def.name) original.set(THREE.PropertyBinding.sanitizeNodeName(def.name), def.name);
    for (const o of gltf.scene.children) shelve(original.get(o.name) || o.name, o);
    fit();
    rebuild(() => "static", byRole);
    start();
    return library.size;
  }

  // One showpiece from its plan file: the pull-apart, the build-up, the load tint, the tour, the settle.
  function setShowpiece(kind, plan, roleMap) {
    roles = roleMap || roles;
    show = { kind, plan, pose: null, sceneNames: (plan.scenes || []).map((s) => s.pieces || []) };
    t0 = performance.now();
    let tintOf = byRole;
    if (kind === "load") tintOf = (name) => loadTint(plan, name) || byRole(name);
    if (kind === "settle") tintOf = (name) => { const s = settleShift(plan, name); return s && s.fell ? FELL : s && s.moved ? SHIFTED : byRole(name); };
    rebuild(groupOf(kind, plan, roles), tintOf);
    if (kind === "explode") focusOnMovers();
    if (kind === "settle") {
      for (const [key, mesh] of drawn) { const s = key.startsWith("p:") ? settleShift(plan, key.slice(2)) : null; if (s) mesh.position.y = s.offset[1]; }
    }
    orbit.auto = true;
    start();
  }

  const byRole = (name) => roleTint(roles[name]);
  function clear() { show = null; if (library.size) rebuild(() => "static", byRole); }
  // The roles of the pieces, from the run's anatomy; the idle view repaints by them at once.
  function setRoles(roleMap) { roles = roleMap || {}; if (!show && library.size) rebuild(() => "static", byRole); }
  function dispose() { stop(); renderer.dispose(); renderer.domElement.remove(); }

  return { load, setShowpiece, setRoles, clear, start, stop, dispose, get pieces() { return library.size; }, get meshes() { return drawn.size; } };
}
