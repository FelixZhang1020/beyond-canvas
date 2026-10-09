import test from 'node:test';
import assert from 'node:assert/strict';
import vm from 'node:vm';
import {readFileSync} from 'node:fs';
const context={Studio:{}};vm.createContext(context);
vm.runInContext(readFileSync('studio/page/src/27g-cloud-relight.js','utf8'),context);
const good={version:1,method:'cloud-glb',model:'trellis2',glb:'x'.repeat(40),bytes:30,sha256:'a'.repeat(64)};
test('cloud viewer rejects unknown methods, providers and excessive payloads before creating an iframe',()=>{
  assert.equal(context.Studio.cloudRelight.valid(good),true);
  for (const value of [null,{...good,version:2},{...good,model:'arbitrary'},{...good,bytes:17*1024*1024},{...good,sha256:'bad'},{...good,glb:''}])
    assert.equal(context.Studio.cloudRelight.valid(value),false);
});

test('unmatched new views show a review notice while still displaying the generated mesh',()=>{
  function node(){return {style:{},children:[],append(...items){this.children.push(...items);}};}
  const ui={Studio:{i18n:{t:key=>key},relight:{}},document:{createElement:node},
    window:{addEventListener(){}},location:{origin:'http://localhost:7060'},setTimeout:()=>1,clearTimeout(){}};
  vm.createContext(ui);vm.runInContext(readFileSync('studio/page/src/27g-cloud-relight.js','utf8'),ui);
  for (const status of ['needs_review','matched',undefined]) {
    const host={...node(),id:'review-output-content'};
    ui.Studio.cloudRelight.open(host,{...good,camera_calibration:{status}},{url:'/drawing'});
    assert.equal(host.children.at(-1).textContent.includes('cloud3d.viewNeedsReview'),status==='needs_review');
    assert.ok(host.children.some(child=>child.src==='/viewer/3d/classroom.html'));
  }
});

test('a model sent apart comes by the stall-proof download, and the viewer still gets it as base64',async()=>{
  // A head's model stalled inside the "done" on the class's link, and the page called a finished job a failure.
  function node(){return {style:{},children:[],append(...items){this.children.push(...items);}};}
  const asked=[],timers=[],posted=[],address='/api/courses/c1/activities/a1/media/scene.glb?v=0123';
  const steady=(url,again,hold,idle)=>{asked.push([url,again(),idle]);hold({abort(){}});return Promise.resolve(new Blob(['glTF bytes']));};
  class FileReader{readAsDataURL(blob){blob.arrayBuffer().then(b=>{this.result='data:model/gltf-binary;base64,'+Buffer.from(b).toString('base64');this.onload();});}}
  const ui={Studio:{i18n:{t:key=>key,lang:'zh'},relight:{},steady},document:{createElement:node},FileReader,URL,
    window:{addEventListener(){}},location:{origin:'http://localhost:7060',href:'http://localhost:7060/'},
    setTimeout:(fn,ms)=>timers.push(ms),clearTimeout(){}};
  vm.createContext(ui);vm.runInContext(readFileSync('studio/page/src/27g-cloud-relight.js','utf8'),ui);
  const host={...node(),id:'review-output-content'};
  ui.Studio.cloudRelight.open(host,{...good,glb:address},{url:'/drawing'});
  assert.deepEqual(asked,[[address,true,8000]],'asked for at once, and again while the viewer is open');
  assert.ok(!timers.includes(120000),'no "cannot be shown" countdown while the model is still coming');
  const frame=host.children.find(child=>child.src==='/viewer/3d/classroom.html');
  frame.contentWindow={postMessage:message=>posted.push(message)};
  await frame.onload();
  assert.equal(posted[0].scene.glb,Buffer.from('glTF bytes').toString('base64'));
  assert.equal(posted[0].scene.sha256,good.sha256,'the viewer checks the model as before');
  assert.ok(timers.includes(120000),'the countdown starts once the viewer has the model');
});

test('the kept angle is the one the viewer shows: no turn keeps the base, and any turn from the rest base is itself',()=>{
  const turned=(base,orbit)=>[...context.Studio.cloudRelight.turned(base,orbit)];
  // The camera opens at the base's own height, so "no turn" is (0, base polar).
  for (const base of [[150,65],[-40,80],[45,75],[31,64]]) assert.deepEqual(turned(base,[0,base[1]]).map(Math.abs),base.map(Math.abs));
  for (const orbit of [[30,75],[-120,60],[90,100]]) assert.deepEqual(turned([0,75],orbit),orbit);
  assert.deepEqual(turned([150,75],[-120,75]),[30,75],'turning back 120 degrees from 150 faces 30');
});

test('from a checked base at another height the kept angle is still the direction she looked from',()=>{
  // The model stays upright and the camera takes the height, so a saved view is the base's
  // yaw plus the camera's turn, at the camera's height. The old tilted-model answers drifted by the base
  // polar minus 75 on every save (found in review before landing).
  const {turned}=context.Studio.cloudRelight;
  for (const [base,orbit,want] of [[[31,64],[0,64],[31,64]],[[150,65],[-120,60],[30,60]],[[170,70],[30,40],[-160,40]]])
    assert.deepEqual([...turned(base,orbit)],want);
});

test('a view the teacher set says so under the model',()=>{
  function node(){return {style:{},children:[],append(...items){this.children.push(...items);}};}
  const ui={Studio:{i18n:{t:key=>key},relight:{}},document:{createElement:node},
    window:{addEventListener(){}},location:{origin:'http://localhost:7060'},setTimeout:()=>1,clearTimeout(){}};
  vm.createContext(ui);vm.runInContext(readFileSync('studio/page/src/27g-cloud-relight.js','utf8'),ui);
  const host={...node(),id:'review-output-content'};
  ui.Studio.cloudRelight.open(host,{...good,camera_calibration:{status:'teacher'}},{url:'/drawing'});
  assert.ok(host.children.at(-1).textContent.includes('cloud3d.viewTeacher'));
});

test('an older solids study opens in the same model viewer, from the angle it was read at',()=>{
  function node(){return {style:{},children:[],append(...items){this.children.push(...items);}};}
  const solids={version:1,method:'geometric-approximation',camera:{target:[0,1,0],distance:10,elevation:25,azimuth:-30,fov:40},
    light:[-3,6,5],objects:[{kind:'sphere',position:[0,1,0],size:[2,2,2],yaw:0}]};
  const ui={Studio:{i18n:{t:key=>key},relight:{valid:scene=>scene.method==='geometric-approximation'}},document:{createElement:node},
    window:{addEventListener(){}},location:{origin:'http://localhost:7060'},setTimeout:()=>1,clearTimeout(){}};
  vm.createContext(ui);vm.runInContext(readFileSync('studio/page/src/27g-cloud-relight.js','utf8'),ui);
  // Operator: the solids get the model viewer's surfaces, not a second, weaker set of them.
  assert.equal(ui.Studio.cloudRelight.solids(solids),true);
  assert.equal(ui.Studio.cloudRelight.solids(good),false,'a GLB is not a solids study');
  const host={...node(),id:'review-output-content'};
  ui.Studio.cloudRelight.open(host,solids,{url:'/drawing'});
  assert.ok(host.children.some(child=>child.src==='/viewer/3d/classroom.html'));
  const refused={...node(),id:'review-output-content'};
  ui.Studio.cloudRelight.open(refused,{...solids,method:'unknown'},{url:'/drawing'});
  assert.ok(!refused.children.some(child=>child.src),'anything else is still refused before an iframe exists');
  assert.equal(refused.children.at(-1).textContent,'cloud3d.failed');
});
