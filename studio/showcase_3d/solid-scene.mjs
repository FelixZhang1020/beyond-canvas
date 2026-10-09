import * as THREE from 'three';

// The classroom's older studies are measured solids or a small mesh, not a GLB. Built here, they get the same
// surfaces, light and controls as a generated model (operator).
const SOLID_KINDS = ['box','sphere','cylinder'];
export function solidScene(scene) {
  const finite = (list, n) => Array.isArray(list) && list.length === n && list.every(Number.isFinite);
  if (!scene || !finite(scene.camera && [scene.camera.azimuth, scene.camera.elevation], 2)) return false;
  if (scene.mesh) {
    const {positions, normals, indices} = scene.mesh;
    return Array.isArray(positions) && positions.length % 3 === 0 && positions.length <= 3 * 65535 &&
      Array.isArray(normals) && normals.length === positions.length && Array.isArray(indices) && indices.length % 3 === 0 &&
      positions.every(Number.isFinite) && normals.every(Number.isFinite) && indices.every(i => Number.isInteger(i) && i >= 0 && i < positions.length / 3);
  }
  return Array.isArray(scene.objects) && scene.objects.length > 0 && scene.objects.length <= 6 &&
    scene.objects.every(o => SOLID_KINDS.includes(o.kind) && finite(o.position, 3) && finite(o.size, 3) && o.size.every(v => v > 0) && Number.isFinite(o.yaw));
}
export function solidGroup(scene) {
  const group = new THREE.Group();
  if (scene.mesh) {
    const geometry = new THREE.BufferGeometry();
    geometry.setAttribute('position', new THREE.Float32BufferAttribute(scene.mesh.positions, 3));
    geometry.setAttribute('normal', new THREE.Float32BufferAttribute(scene.mesh.normals, 3));
    geometry.setIndex(scene.mesh.indices);
    group.add(new THREE.Mesh(geometry));
    return group;
  }
  for (const o of scene.objects) {
    // An even, readable grid for the triangle view: smooth enough in shading, not a solid mass of lines.
    const geometry = o.kind === 'box' ? new THREE.BoxGeometry(1, 1, 1, 4, 4, 4)
      : o.kind === 'sphere' ? new THREE.SphereGeometry(0.5, 36, 18) : new THREE.CylinderGeometry(0.5, 0.5, 1, 36, 4);
    const mesh = new THREE.Mesh(geometry);
    mesh.scale.set(...o.size); mesh.position.set(...o.position); mesh.rotation.y = THREE.MathUtils.degToRad(o.yaw);
    group.add(mesh);
  }
  return group;
}
