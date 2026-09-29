import { test } from 'node:test';
import assert from 'node:assert/strict';
import { loadStudio } from './load.mjs';

const S=loadStudio({files:['src/27e-relight.js']}), R=S.relight;
const camera={target:[0,1,0],distance:10,elevation:25,azimuth:0,fov:40};
const scene={version:1,method:'geometric-approximation',camera,light:[-3,6,5],source_aspect:1.5,
  objects:[{kind:'sphere',position:[0,1,0],size:[2,2,2],yaw:0}]};

test('valid solids pass; missing, nonfinite, oversized and floating scenes fail',()=>{
  assert.equal(R.valid(scene),true);
  for(const bad of [null,{}, {...scene,objects:[]}, {...scene,objects:Array(7).fill(scene.objects[0])},
    {...scene,light:[0,NaN,0]}, {...scene,objects:[{...scene.objects[0],kind:'mesh'}]},
    {...scene,objects:[{...scene.objects[0],size:[2,-1,2]}]},
    {...scene,objects:[{...scene.objects[0],position:[0,2,0]}]}])assert.equal(R.valid(bad),false);
});

test('4K and Retina canvases obey the pixel and DPR budgets',()=>{
  for(const [w,h,d] of [[3840,2160,2],[7680,4320,3],[800,500,3],[400,300,1]]){
    const [rw,rh]=R.resolution(w,h,d);
    assert.ok(rw*rh<=1000000 && rw<=1440 && rw<=w*1.5 && rh<=h*1.5);
    assert.ok(Math.abs(rw/rh-w/h)<.01);
  }
});

test('perspective rays converge at the camera, and orbit changes the eye',()=>{
  const center=R.ray(camera,.5,.5,1.5), edge=R.ray(camera,1,.5,1.5);
  assert.deepEqual(center.origin,edge.origin);
  assert.ok(edge.direction[0]>center.direction[0]);
  const other=R.basis({...camera,azimuth:90});
  assert.ok(other.eye[0]>8 && Math.abs(other.eye[2])<1e-8);
});

test('light placement projects onto the tabletop; pointing into sky gives no fake position',()=>{
  const left=R.floorPoint(camera,.25,.7,1.5), right=R.floorPoint(camera,.75,.7,1.5);
  assert.ok(left[0]<0 && right[0]>0);
  assert.ok(Math.abs(left[1])<1e-8 && Math.abs(right[1])<1e-8);
  assert.equal(R.floorPoint({...camera,elevation:8},.5,0,1.5),null);
});

test('every relighting control has a Chinese label',()=>{
  const keys=Object.keys(S.strings.zh).filter(k=>k.startsWith('relight.'));
  assert.ok(keys.length>0,'no relighting labels found at all');
  for(const key of keys) assert.ok(S.strings.zh[key],key);
});

test('drawing is on demand, hidden tabs stop, and closing releases the GPU and pending frame',()=>{
  const frames=new Map(), timers=new Map(), nodes=[], listeners=new Map();let seq=0,draws=0,disposed=0;
  const gl=new Proxy({}, {get:(_,key)=>{
    if(key==='getShaderParameter'||key==='getProgramParameter')return ()=>true;
    if(key==='drawArrays')return ()=>draws++;
    if(key==='deleteProgram')return ()=>disposed++;
    if(key==='createShader'||key==='createProgram'||key==='createBuffer')return ()=>({});
    return ()=>{};
  }});
  class Element{
    constructor(tag){this.tagName=tag;this.children=[];this.style={};this.attributes={};this.classList={add(){},remove(){},toggle(){},contains(){return false;}};nodes.push(this);}
    appendChild(n){this.children.push(n);} replaceChildren(){this.children=[];}
    setAttribute(k,v){this.attributes[k]=v;} addEventListener(){} remove(){}
    getBoundingClientRect(){return {left:0,top:0,width:800,height:533};} getContext(){return gl;}
    setPointerCapture(id){this.capture=id;}
  }
  const document={hidden:false,createElement:tag=>new Element(tag),
    addEventListener:(k,v)=>listeners.set(k,v),removeEventListener:k=>listeners.delete(k)};
  const studio=loadStudio({files:['src/27e-relight.js'],globals:{document,
    requestAnimationFrame:fn=>{frames.set(++seq,fn);return seq;},cancelAnimationFrame:id=>frames.delete(id),
    setTimeout:fn=>{timers.set(++seq,fn);return seq;},clearTimeout:id=>timers.delete(id),
    ResizeObserver:class{observe(){}disconnect(){}}
  }});
  const flush=()=>{const batch=[...frames.values()];frames.clear();batch.forEach(fn=>fn());};
  const host=new Element('div');
  studio.relight.open(host,scene,{url:'local-drawing'});
  assert.equal(frames.size,1);flush();assert.equal(draws,1);assert.equal(frames.size,0,'no idle loop');
  const slider=nodes.find(n=>n.attributes['aria-label']==='灯的左右位置');
  slider.value=5;slider.oninput();flush();assert.equal(draws,2);
  const lamp=nodes.find(n=>n.className==='relight-map-lamp');assert.equal(lamp.style.left,'81.25%');
  const stageLamp=nodes.find(n=>n.className==='relight-stage-lamp');
  assert.ok(stageLamp,'the visible viewer must contain a light source');
  assert.ok(parseFloat(stageLamp.style.left)>0 && parseFloat(stageLamp.style.top)>0);
  studio.relight.active.control('direction',180);studio.relight.active.control('elevation',30);
  const initialLeft=stageLamp.style.left;
  studio.relight.active.control('direction',150);
  assert.notEqual(stageLamp.style.left,initialLeft,'direction slider updates the visible source');
  // The marker sits on the light as the camera sees it: grabbing it where it is leaves the light alone,
  // before and after the view turns (before the fix it was placed by compass direction and drifted off the light).
  const canvas=nodes.find(n=>n.tagName==='canvas');
  const roundTrip=()=>{
    flush();const before=studio.relight.active.inspect(),x=parseFloat(stageLamp.style.left),y=parseFloat(stageLamp.style.top);
    stageLamp.onpointerdown({button:0,pointerId:9,stopPropagation(){}});
    stageLamp.onpointermove({clientX:x,clientY:y,pointerId:9,stopPropagation(){}});stageLamp.onpointerup();
    const after=studio.relight.active.inspect();
    assert.ok(Math.abs(after.direction-before.direction)<=1 && Math.abs(after.elevation-before.elevation)<=1,
      `grabbing the marker in place moved the light from ${before.direction}/${before.elevation} to ${after.direction}/${after.elevation}`);
  };
  // Bring the light into the frame first; outside it the marker waits at the edge, not on the light.
  const centre=()=>{stageLamp.onpointerdown({button:0,pointerId:8,stopPropagation(){}});
    stageLamp.onpointermove({clientX:400,clientY:230,pointerId:8,stopPropagation(){}});stageLamp.onpointerup();};
  centre();roundTrip();
  flush();const seenAt=stageLamp.style.left;
  const turned=studio.relight.active.view?.();
  canvas.onpointerdown({clientX:400,clientY:260,pointerId:5});canvas.onpointermove({clientX:520,clientY:260,pointerId:5});canvas.onpointerup();
  assert.notDeepEqual(studio.relight.active.view?.(),turned,'the drag turned the view');
  flush();assert.notEqual(stageLamp.style.left,seenAt,'the light stayed put, so turning the view moves its marker');
  centre();roundTrip();
  stageLamp.onpointerdown({button:0,pointerId:1,stopPropagation(){}});
  stageLamp.onpointermove({clientX:600,clientY:120,pointerId:1,stopPropagation(){}});
  // The lamp moves the light by itself; a drag on the model must still turn the model afterwards
  // (before the fix, grabbing the lamp left every later drag moving the light, with no button to undo it).
  assert.equal(studio.relight.active.inspect().mode,'orbit');
  assert.ok(studio.relight.active.inspect().direction>0);
  assert.ok(studio.relight.active.inspect().elevation>10);
  stageLamp.onpointerup();

  studio.relight.active.control('elevation',10);
  assert.equal(studio.relight.active.inspect().elevation,10);
  studio.relight.active.control('elevation',85);
  assert.equal(studio.relight.active.inspect().elevation,85,'the height slider must not snap back while dragging');
  studio.relight.active.control('mode','light');
  assert.equal(studio.relight.active.inspect().mode,'light');
  document.hidden=true;listeners.get('visibilitychange')();slider.oninput();
  assert.equal(frames.size,0);assert.equal(timers.size,0);
  document.hidden=false;listeners.get('visibilitychange')();assert.equal(frames.size,1);
  studio.relight.close();assert.equal(frames.size,0);assert.equal(disposed,1);assert.equal(listeners.size,0);
  assert.equal(host.children.length,0);assert.equal(studio.relight.active,null);
  slider.oninput();assert.equal(frames.size,0,'stale handler cannot restart rendering');
});
