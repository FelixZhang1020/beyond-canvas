import { test } from 'node:test';
import assert from 'node:assert/strict';
import { loadStudio } from './load.mjs';

const mesh={positions:[-1,0,-1,1,0,-1,0,0,1,0,2,0],normals:[0,1,0,0,1,0,0,1,0,0,1,0],
  indices:[0,1,2,0,3,1,1,3,2,2,3,0],size:[2,2,2]};
const camera={target:[0,1,0],distance:6,elevation:10,azimuth:0,fov:40};
const scene={version:1,method:'single-image-mesh',mesh,camera,light:[-3,6,5],source_aspect:.67};
const S=loadStudio({files:['src/27e-relight.js','src/27f-mesh.js']});

test('mesh scenes use the bounded triangle path; corrupted arrays are rejected',()=>{
  assert.equal(S.relight.valid(scene),true);
  assert.equal(S.relight.valid({...scene,subject:'fruit',source_aspect:1.5}),true);
  assert.equal(S.relight.valid({...scene,subject:'arbitrary'}),false);
  for(const update of [{positions:[NaN,...mesh.positions.slice(1)]},{indices:[999,...mesh.indices.slice(1)]},
    {normals:mesh.normals.map(()=>0)},{positions:Array(60001*3).fill(1)},{size:[-1,2,2]}]){
    assert.equal(S.relight.valid({...scene,mesh:{...mesh,...update}}),false);
  }
  assert.equal(S.relight.valid({...scene,light:[NaN,6,5]}),false);
});

test('mesh view and existing ray camera agree on the target and perspective',()=>{
  const M=S.mesh,eye=S.relight.basis(camera).eye;
  const vp=M.multiply(M.perspective(40,1,.05,40),M.view(eye,camera.target,[0,1,0]));
  const project=p=>[0,1,2,3].map(r=>vp[r]*p[0]+vp[4+r]*p[1]+vp[8+r]*p[2]+vp[12+r]);
  const center=project(camera.target),right=project([1,1,0]);
  assert.ok(Math.abs(center[0])<1e-8 && Math.abs(center[1])<1e-8);
  assert.ok(center[3]>0 && right[0]/right[3]>0);
});

test('mixed still life uses the shared shadow mesh instead of replacing the pear with a sphere',()=>{
  const mixed={...scene,method:'parametric-still-life',source_aspect:1.5,
    objects:[{kind:'pear',position:[0,1,0],size:[1,2,1],yaw:0}]};
  assert.equal(S.relight.valid(mixed),true);
  assert.equal(S.relight.valid({...mixed,mesh:null}),false);
  assert.equal(S.relight.valid({...mixed,objects:[]}),false);
  assert.equal(S.relight.valid({...mixed,objects:[{...mixed.objects[0],size:[NaN,2,1]}]}),false);
  assert.equal(S.relight.valid({...mixed,method:'geometric-approximation'}),false);
  assert.equal(S.relight.valid({...scene,method:'unknown'}),false);
});

test('six bounded shadow faces redraw only when light moves; all resources are released',()=>{
  const calls={draw:0,modes:[],textureSizes:[],deleted:[]};let id=0;
  const constants={FRAMEBUFFER_COMPLETE:1,VERTEX_SHADER:2,FRAGMENT_SHADER:3,TRIANGLES:4,LINES:5};
  const gl=new Proxy(constants,{get:(object,key)=>{
    if(key in object)return object[key];
    if(key.startsWith('create'))return ()=>({id:++id});
    if(key.startsWith('delete'))return item=>calls.deleted.push(item.id);
    if(key==='getShaderParameter'||key==='getProgramParameter')return ()=>true;
    if(key==='getAttribLocation')return (_,name)=>name==='position'?0:1;
    if(key==='getUniformLocation')return ()=>({});
    if(key==='checkFramebufferStatus')return ()=>1;
    if(key==='drawElements')return mode=>{calls.draw++;calls.modes.push(mode);};
    if(key==='texImage2D')return (...args)=>calls.textureSizes.push(args.slice(3,5));
    return ()=>{};
  }});
  const studio=loadStudio({files:['src/27e-relight.js','src/27f-mesh.js']});
  const canvas={getContext:()=>gl,getBoundingClientRect:()=>({width:3840,height:2160})};
  const renderer=studio.mesh.renderer(canvas,scene);
  renderer.draw(camera,scene.light,1,false);
  assert.equal(calls.draw,8); // Six shadow views, floor, mesh.
  assert.equal(calls.textureSizes.length,6);
  assert.ok(calls.textureSizes.every(([w,h])=>w===1024&&h===1024));
  assert.ok(canvas.width*canvas.height<=1000000);
  renderer.draw({...camera,azimuth:90},scene.light,1,true);
  assert.equal(calls.draw,10,'orbit reuses the shadow map');
  renderer.draw(camera,[3,6,5],1,true);
  assert.equal(calls.draw,18,'moving the lamp refreshes occlusion');
  renderer.draw(camera,[3,6,5],1,false,{material:'wire',ground:false});
  assert.equal(calls.draw,20,'wireframe draws the filled model and edges without a floor or new shadow maps');
  assert.deepEqual(calls.modes.slice(-2),[gl.TRIANGLES,gl.LINES]);
  renderer.dispose();
  assert.equal(new Set(calls.deleted).size,id,'every GPU allocation is freed');
});
