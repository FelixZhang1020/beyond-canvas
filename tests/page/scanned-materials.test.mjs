import test from 'node:test';
import assert from 'node:assert/strict';
import * as THREE from '../../studio/showcase_3d/vendor/three.module.js';
import {scannedSurfaces} from '../../studio/showcase_3d/assets/materials/scanned.js';
const settle=()=>new Promise(resolve=>setImmediate(resolve));
test('scans load once, separate color from data, compile and dispose',async()=>{
  let requests=0,refreshes=0;const loaded=[];
  class Loader {async loadAsync(){requests++;const t=new THREE.Texture();loaded.push(t);return t;}}
  const materials={wood:new THREE.MeshPhysicalMaterial()};
  const scans=scannedSurfaces({...THREE,TextureLoader:Loader},materials,{value:.6},()=>refreshes++);
  scans.ensure('wood');scans.ensure('wood');await settle();
  assert.equal(requests,3);assert.equal(scans.status('wood'),'ready');assert.equal(refreshes,1);
  assert.equal(loaded[0].colorSpace,THREE.SRGBColorSpace);assert.equal(loaded[1].colorSpace,THREE.NoColorSpace);
  const shader={uniforms:{},vertexShader:THREE.ShaderLib.physical.vertexShader,fragmentShader:THREE.ShaderLib.physical.fragmentShader};
  materials.wood.onBeforeCompile(shader);assert.ok(shader.fragmentShader.includes('projectScan(scanColor'));assert.ok(shader.vertexShader.includes('surfacePosition'));
  let released=0;loaded.forEach(t=>t.addEventListener('dispose',()=>released++));scans.dispose();assert.equal(released,3);
});
test('failed texture retains base material and reports error',async()=>{
  class Loader {async loadAsync(){throw Error('missing');}}
  const material=new THREE.MeshStandardMaterial({color:0x123456}),original=material.onBeforeCompile;
  const scans=scannedSurfaces({...THREE,TextureLoader:Loader},{rust:material},{value:1},()=>{});
  scans.ensure('rust');await settle();assert.equal(scans.status('rust'),'error');assert.equal(material.onBeforeCompile,original);assert.equal(material.color.getHex(),0x123456);scans.dispose();
});
