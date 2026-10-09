import test from 'node:test';
import assert from 'node:assert/strict';
import vm from 'node:vm';
import {readFileSync} from 'node:fs';
import * as THREE from '../../studio/showcase_3d/vendor/three.module.js';
const source = readFileSync('studio/showcase_3d/viewer.js', 'utf8');
const bakeSource = source.slice(source.indexOf('// Bake display-space coordinates once:'));
const bake = bakeSource.slice(bakeSource.indexOf('    aligned.updateWorldMatrix(true, true);'), bakeSource.indexOf('    applySurface(card);', bakeSource.indexOf('    aligned.updateWorldMatrix(true, true);')));
test('surface coordinates agree across provider units and stay fixed during rotation', () => {
  const results = [];
  for (const units of [1, 1000]) {
    const raw = new THREE.Group(), aligned = new THREE.Group();
    const mesh = new THREE.Mesh(new THREE.BoxGeometry(units, units, units));
    raw.add(mesh); aligned.add(raw); aligned.scale.setScalar(2.4 / units);
    vm.runInNewContext(bake, {aligned, raw});
    const before = Array.from(mesh.geometry.attributes.surfacePosition.array);
    aligned.rotation.y = 1.3; aligned.updateMatrixWorld(true);
    assert.deepEqual(Array.from(mesh.geometry.attributes.surfacePosition.array), before);
    results.push({surface: before, raw: Array.from(mesh.geometry.attributes.position.array)});
  }
  assert.deepEqual(results[0].surface, results[1].surface);
  assert.notDeepEqual(results[0].raw, results[1].raw, 'old raw-position mapping fails the scale control');
});
