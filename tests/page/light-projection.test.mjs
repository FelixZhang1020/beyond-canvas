import test from 'node:test';
import assert from 'node:assert/strict';
import vm from 'node:vm';
import {readFileSync} from 'node:fs';
import * as THREE from '../../studio/showcase_3d/vendor/three.module.js';

const source=readFileSync('studio/showcase_3d/viewer.js','utf8');
const scope={THREE};vm.createContext(scope);
vm.runInContext(source.slice(source.indexOf('function projectLight('),source.indexOf('function updateLightMarker(')),scope);
test('light marker round-trips through the actual camera across rotation, zoom and aspect ratios',()=>{
  for(const aspect of [.6,1,1.8])for(const yaw of [0,Math.PI/2,Math.PI])for(const distance of [4,8]){
    const camera=new THREE.PerspectiveCamera(36,aspect,.05,80);
    camera.position.setFromSphericalCoords(distance,1.2,yaw);camera.lookAt(0,0,0);camera.updateMatrixWorld();
    const light=new THREE.Vector3(-.7,1.1,.8),original=light.clone();
    const screen=scope.projectLight(light,camera);
    const restored=scope.dragLightPosition(screen.x,screen.y,camera,light);
    assert.ok(restored.distanceTo(light)<1e-10);
    const moved=scope.dragLightPosition(.4,.3,camera,light);
    const projected=scope.projectLight(moved,camera);
    assert.ok(Math.abs(projected.x-.4)<1e-10 && Math.abs(projected.y-.3)<1e-10);
    assert.ok(light.equals(original));
  }
});
test('a camera rotation moves the marker; the former angle-to-pixel formula cannot represent it',()=>{
  const camera=new THREE.PerspectiveCamera(36,1,.05,80),light=new THREE.Vector3(-.8,1,.9);
  camera.position.set(0,1,5);camera.lookAt(0,0,0);const before=scope.projectLight(light,camera);
  camera.position.set(-5,1,0);camera.lookAt(0,0,0);const after=scope.projectLight(light,camera);
  assert.ok(Math.abs(before.x-after.x)>.1);
  assert.notEqual(before.x,.1+(-45+180)/360*.8);
});
test('normal colour shader retains real lighting; glass keeps a lit surface component',()=>{
  const context={THREE,classroomMode:true,studyMode:true,materials:{normal:new THREE.MeshStandardMaterial(),glass:new THREE.MeshPhysicalMaterial()}};
  vm.createContext(context);
  const start=source.indexOf('if (studyMode) {');
  vm.runInContext(source.slice(start,source.indexOf('// Object-space grain')),context);
  const normal={fragmentShader:THREE.ShaderLib.standard.fragmentShader};
  context.materials.normal.onBeforeCompile(normal);
  assert.ok(normal.fragmentShader.includes('diffuseColor.rgb = normal * 0.5 + 0.5;'));
  assert.ok(normal.fragmentShader.includes('#include <lights_fragment_begin>'));
  assert.ok(context.materials.glass.transmission<1);
});
for (const classroomMode of [true, false]) test(`${classroomMode ? 'classroom' : 'exhibit'} glass keeps ground and shadows enabled, and switching material restores opaque shadows`,()=>{
  const controls={'#material':{value:'glass'},'#ground':{checked:true,disabled:true},'#wood-control':{},'#material-note':{}};
  const context={scans:{ensure:()=>{},status:()=>undefined},classroomMode,studyMode:true,classroomEnglish:false,materials:{glass:{},normal:{}},surfaceNotes:{},
    $:id=>controls[id],document:{querySelectorAll:()=>[]},neutralMetalEnvironment:()=>null};
  vm.createContext(context);
  vm.runInContext(source.slice(source.indexOf('function applySurface('),source.indexOf('let manifest,')),context);
  const mesh={isMesh:true,castShadow:false};
  const card={scene:{},backdrop:{},floor:{},light:{shadow:{}},model:{traverse:fn=>fn(mesh)},sphere:{}};
  context.applySurface(card);
  assert.equal(card.floor.visible,true);
  assert.equal(controls['#ground'].disabled,false);
  assert.equal(mesh.castShadow,true);
  assert.equal(card.light.shadow.intensity,.25);
  controls['#material'].value='normal';context.applySurface(card);
  assert.equal(card.light.shadow.intensity,1);
  controls['#ground'].checked=false;context.applySurface(card);
  assert.equal(card.floor.visible,false);
});
test('classroom uses the exact saved mesh calibration, not a provider-wide front',()=>{
  const context={THREE,radians:THREE.MathUtils.degToRad,origin:new THREE.Vector3()};vm.createContext(context);
  vm.runInContext(source.slice(source.indexOf('function cameraQuaternion('),source.indexOf('async function loadCard(')),context);
  const catalog=JSON.parse(readFileSync('studio/showcase_3d/manifest.json','utf8'));
  const item=catalog.samples.find(s=>s.id==='geometry').cases.find(c=>c.model==='trellis2');
  assert.deepEqual(context.calibratedBase(item,catalog),[135,75]);
  assert.equal(context.calibratedBase({...item,sha256:'unknown',camera_base:undefined},catalog)[0],45);
  assert.deepEqual(context.calibratedBase({...item,camera_base:[20,85]},catalog),[20,85]);
  assert.deepEqual(context.calibratedBase({model:'trellis2',camera_base:[135,75]},{}),[135,75]);
  for (const camera_base of [[NaN,75],[0,0],[0,180],[181,75],[20],['20',85]]) {
    assert.deepEqual(context.calibratedBase({...item,camera_base},catalog),[135,75]);
  }
  const extent=new THREE.Vector3(2.4,1.8,2);
  for(const aspect of [.6,1,2.2]){
    const distance=context.fittedDistance(extent,aspect),camera=new THREE.PerspectiveCamera(36,aspect,.05,80);
    camera.position.setFromSphericalCoords(distance,THREE.MathUtils.degToRad(75),0);camera.lookAt(0,0,0);camera.updateMatrixWorld();
    for(const x of [-1,1])for(const y of [-1,1])for(const z of [-1,1]){
      const p=new THREE.Vector3(x*extent.x/2,y*extent.y/2,z*extent.z/2).project(camera);
      assert.ok(Math.abs(p.x)<.8 && Math.abs(p.y)<.8);
    }
  }
});

test('steel reflection direction follows the adjustable light without raising scene fill',()=>{
  const controls={'#light-azimuth':{value:-45},'#light-elevation':{value:50},'#ground':{checked:true}};
  const metal=new THREE.MeshStandardMaterial();
  const context={THREE,radians:THREE.MathUtils.degToRad,$:id=>controls[id],materials:{metal},updateLightMarker:()=>{}};
  vm.createContext(context);
  vm.runInContext(source.slice(source.indexOf('function setLight('),source.indexOf('function changeOrbit(')),context);
  const card={light:new THREE.PointLight(),floor:{},scene:{environmentIntensity:.25}};
  context.setLight(card);const before=metal.envMapRotation.y;
  assert.equal(before,THREE.MathUtils.degToRad(-45));
  controls['#light-azimuth'].value=70;context.setLight(card);
  assert.notEqual(metal.envMapRotation.y,before);
  assert.equal(metal.envMapRotation.y,Math.atan2(card.light.position.x,card.light.position.z));
  assert.equal(card.scene.environmentIntensity,.25);
});

test('reset clears orbit and manual alignment together',()=>{
  const controls = {'#auto':{setAttribute(){}},'.align-yaw':{value:'25'},'.align-pitch':{value:'10'}};
  const card = {el:{},orbit:{yaw:40,polar:30,zoom:2},pivot:new THREE.Group()};
  card.pivot.rotation.set(.3,.5,0);
  assert.notEqual(card.pivot.quaternion.w,1);
  const context={cards:[card],$:id=>controls[id],requestRender(){},auto:true};
  vm.createContext(context);
  vm.runInContext(source.slice(source.indexOf('function reset()'),source.indexOf('async function selectSample')),context);
  context.reset();
  assert.equal(card.orbit.yaw,0);assert.equal(card.orbit.zoom,1);
  card.initialZoom=.8;card.orbit.zoom=1.5;context.reset();
  assert.equal(card.orbit.zoom,.8,'reset restores the classroom framing');
  assert.equal(card.pivot.quaternion.w,1);assert.equal(controls['.align-yaw'].value,'0');
});
