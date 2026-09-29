// The class page's 3D figure viewer (painting-to-figure). It draws the parts the studio checked, with the same
// unit shapes as the check's preview (studio/making/figure_render.py): each centred, full extent 1 along every axis,
// scaled by "size", turned by "turn" in degrees (order XYZ) and placed at "at". Parts arrive only as data, by
// postMessage from the class page on the same origin; nothing here runs code a model wrote.
import * as THREE from 'three';

const SHAPES = {
  sphere: () => new THREE.SphereGeometry(.5, 32, 20),
  box: () => new THREE.BoxGeometry(1, 1, 1),
  cylinder: () => new THREE.CylinderGeometry(.5, .5, 1, 32),
  cone: () => new THREE.ConeGeometry(.5, 1, 32),
  capsule: () => new THREE.CapsuleGeometry(.5, 1, 8, 24).scale(1, .5, 1),   // total height 1, round ends
  torus: () => new THREE.TorusGeometry(.375, .125, 12, 32).rotateX(Math.PI / 2).scale(1, 4, 1),   // flat, 1 thick
};
const BASE = '#d9cfbd', PAPER = '#f7f4ee', MAX_PARTS = 140;

function triple(v, low, high) { return Array.isArray(v) && v.length === 3 && v.every(n => typeof n === 'number' && Number.isFinite(n) && n >= low && n <= high); }
export function valid(figure) {
  return !!figure && figure.version === 1 && Array.isArray(figure.parts) && figure.parts.length >= 3 && figure.parts.length <= MAX_PARTS
    && figure.parts.every(p => p && Object.hasOwn(SHAPES, p.shape) && triple(p.at, -3, 4) && triple(p.size, .01, 4)
      && triple(p.turn, -360, 360) && /^#[0-9a-f]{6}$/.test(p.colour));
}
export function baseRadius(figure) {
  const reach = Math.max(...figure.parts.map(p => Math.hypot(p.at[0], p.at[2]) + Math.max(p.size[0], p.size[2]) / 2));
  return Math.min(2.2, Math.max(.8, reach + .15));
}

const canvas = document.getElementById('figure'), note = document.getElementById('note');
const renderer = new THREE.WebGLRenderer({canvas, antialias: true, preserveDrawingBuffer: true});
renderer.setPixelRatio(Math.min(devicePixelRatio, 2)); renderer.shadowMap.enabled = true;
renderer.outputColorSpace = THREE.SRGBColorSpace;
const scene = new THREE.Scene(); scene.background = new THREE.Color(PAPER);
const camera = new THREE.PerspectiveCamera(35, 1, .05, 60);
scene.add(new THREE.HemisphereLight(0xfffaf0, 0x9d9486, 1.6));
const sun = new THREE.DirectionalLight(0xffffff, 2.2); sun.position.set(-2.5, 5, 3.5); sun.castShadow = true;
sun.shadow.mapSize.set(2048, 2048); Object.assign(sun.shadow.camera, {left: -3, right: 3, top: 3, bottom: -3});
scene.add(sun);
const toy = new THREE.Group(); scene.add(toy);
let orbit = {yaw: 20, pitch: 16, zoom: 1}, centre = new THREE.Vector3(0, 1, 0), reach = 2.4, idle = true, drag = null;

function show(figure) {
  toy.clear();
  const r = baseRadius(figure);
  const base = new THREE.Mesh(new THREE.CylinderGeometry(r, r, .1, 64), new THREE.MeshStandardMaterial({color: BASE, roughness: .9}));
  base.position.y = -.05; base.receiveShadow = true; toy.add(base);
  for (const p of figure.parts) {
    const mesh = new THREE.Mesh(SHAPES[p.shape](), new THREE.MeshStandardMaterial({color: p.colour, roughness: .55}));
    mesh.scale.set(...p.size); mesh.rotation.set(...p.turn.map(THREE.MathUtils.degToRad), 'XYZ'); mesh.position.set(...p.at);
    mesh.castShadow = mesh.receiveShadow = true; toy.add(mesh);
  }
  const box = new THREE.Box3().setFromObject(toy); box.getCenter(centre);
  reach = box.getSize(new THREE.Vector3()).length() / 2;
}

function frame() {
  const w = canvas.clientWidth, h = canvas.clientHeight;
  if (canvas.width !== Math.round(w * renderer.getPixelRatio())) { renderer.setSize(w, h, false); camera.aspect = w / h; camera.updateProjectionMatrix(); }
  if (idle) orbit.yaw += .12;
  const distance = reach / Math.sin(THREE.MathUtils.degToRad(35 / 2)) * 1.08 * orbit.zoom / Math.min(1, camera.aspect);
  camera.position.setFromSphericalCoords(distance, THREE.MathUtils.degToRad(90 - orbit.pitch), THREE.MathUtils.degToRad(orbit.yaw)).add(centre);
  camera.lookAt(centre); renderer.render(scene, camera); requestAnimationFrame(frame);
}

canvas.addEventListener('pointerdown', e => { idle = false; drag = {x: e.clientX, y: e.clientY}; canvas.setPointerCapture(e.pointerId); });
canvas.addEventListener('pointermove', e => {
  if (!drag) return;
  orbit.yaw -= (e.clientX - drag.x) * .4; orbit.pitch = Math.max(-5, Math.min(70, orbit.pitch + (e.clientY - drag.y) * .3));
  drag = {x: e.clientX, y: e.clientY};
});
canvas.addEventListener('pointerup', () => { drag = null; });
canvas.addEventListener('wheel', e => { e.preventDefault(); idle = false; orbit.zoom = Math.max(.6, Math.min(1.8, orbit.zoom * (e.deltaY > 0 ? 1.08 : .93))); }, {passive: false});

window.addEventListener('message', event => {
  if (event.origin !== location.origin || event.source !== window.parent) return;
  if (event.data?.type === 'snapshot') {   // the page's "save it to take home"; the buffer is kept for this
    canvas.toBlob(blob => window.parent.postMessage({type: 'figure-snapshot', blob}, location.origin), 'image/png');
    return;
  }
  if (event.data?.type !== 'figure') return;
  if (!valid(event.data.figure)) { note.hidden = false; window.parent.postMessage({type: 'figure-error'}, location.origin); return; }
  show(event.data.figure); note.hidden = true;
  window.parent.postMessage({type: 'figure-ready'}, location.origin);
});
requestAnimationFrame(frame);
window.parent.postMessage({type: 'figure-viewer-loaded'}, location.origin);
