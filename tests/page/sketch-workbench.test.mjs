import test from 'node:test';
import assert from 'node:assert/strict';
import vm from 'node:vm';
import {readFileSync} from 'node:fs';

function setup() {
  class Element {
    hidden=true; dataset={}; children=[]; parentNode=null;
    attributes={};setAttribute(name,value){this.attributes[name]=value;}
    classList={values:new Set(),add(...names){names.forEach(name=>this.values.add(name));},remove(...names){names.forEach(name=>this.values.delete(name));},toggle(name,force){if(force===undefined)force=!this.values.has(name);force?this.values.add(name):this.values.delete(name);return force;},contains(name){return this.values.has(name);}};
    removeChild(node){const i=this.children.indexOf(node);if(i>=0){this.children.splice(i,1);node.parentNode=null;}}
    append(...nodes){for(const node of nodes){node.parentNode?.removeChild(node);this.children.push(node);node.parentNode=this;}}
    insertBefore(node, before){const i=this.children.indexOf(before);if(i<0)throw Error('Missing sibling');node.parentNode?.removeChild(node);this.children.splice(this.children.indexOf(before),0,node);node.parentNode=this;}
    replaceChildren(...nodes){for(const node of this.children)node.parentNode=null;this.children=[];this.append(...nodes);}
  }
  const elements=new Map();
  const el=id=>{if(!elements.has(id))elements.set(id,new Element());return elements.get(id);};
  el('buddy').append(el('cloud3d-choice'),el('buddy-actions'),el('process'));
  el('app').dataset.courseView='create';
  let drawing={id:'a',url:'/a.png'}, opens=[], disposed=0;
  const Studio={state:{session:'s',courseId:'c',mode:'move',settings:{entrance:'sketch'}},
    session:{currentDrawing:()=>drawing},i18n:{lang:'zh',t:k=>k},portfolio:{},
    cloudRelight:{valid:()=>true},relight:{active:null,valid:()=>true,open(host,scene,d){this.close();opens.push(d.id);
      const pair=new Element(),stage=new Element();pair.className='sketch-pair';pair.append(new Element(),stage);host.append(pair);this.active={scene,host};},
    close(){disposed++;this.active?.host.replaceChildren();this.active=null;}}};
  const context={Studio,AbortController,setTimeout,clearTimeout,setInterval,clearInterval,
    document:{getElementById:el,createElement:()=>new Element(),querySelector:()=>null}};
  vm.createContext(context);vm.runInContext(readFileSync('studio/page/src/27g-cloud-relight.js','utf8'),context);
  // This suite stubs rendering; the real cloud validator expects a complete GLB.
  Studio.cloudRelight.valid=()=>true;
  return {Studio,el,opens,context,get disposed(){return disposed;},select(id){drawing={id,url:`/${id}.png`};}};
}
const result=id=>({id,summary:{kind:'relight'},drawings:[id]});
test('creation loads only the latest saved scene for the selected drawing and releases it on exit',async()=>{
  const x=setup(), calls=[];
  x.Studio.portfolio.api=async path=>{calls.push(path);return path.includes('/activities/')?{outputs:{scene:{method:'cloud-glb'}}}:{activities:[result('b'),result('a')]};};
  await x.Studio.sketchWorkbench.refresh();
  assert.deepEqual(x.opens,['a']); assert.equal(x.el('sketch-workbench').hidden,false);
  await x.Studio.sketchWorkbench.refresh();assert.equal(calls.length,2);
  x.Studio.state.mode='feedback';await x.Studio.sketchWorkbench.refresh();
  assert.equal(x.Studio.relight.active,null);assert.equal(x.el('sketch-workbench').hidden,true);
});
test('regeneration shows live progress beside the model and clears it when the run ends',async()=>{
  const x=setup();
  x.Studio.portfolio.api=async path=>path.includes('/activities/')?{outputs:{scene:{method:'cloud-glb'}}}:{activities:[result('a')]};
  await x.Studio.sketchWorkbench.refresh();
  x.Studio.state.making='sketch-to-3d';
  x.Studio.sketchWorkbench.beginGeneration();
  x.Studio.sketchWorkbench.generationTick('正在运行 · 已用 4 分钟');
  const stage=x.el('sketch-workbench').children[0].children[1];
  const notice=stage.children.find(child=>child.className==='sketch-generation-status');
  assert.equal(notice.textContent,'cloud3d.regenerating · 正在运行 · 已用 4 分钟');
  x.Studio.state.making=null;
  await x.Studio.sketchWorkbench.refresh();
  assert.equal(stage.children.some(child=>child.className==='sketch-generation-status'),false);
});
test('a delayed scene cannot replace a newer drawing or reopen a closed workspace',async()=>{
  const x=setup(); let release;
  x.Studio.portfolio.api=async path=>path.includes('/activities/')?new Promise(resolve=>{release=resolve;}):{activities:[result('a')]};
  const pending=x.Studio.sketchWorkbench.refresh();await new Promise(setImmediate);
  x.select('b');await x.Studio.sketchWorkbench.refresh();
  release({outputs:{scene:{}}});await pending;
  assert.deepEqual(x.opens,[]);
  x.Studio.sketchWorkbench.close();assert.equal(x.el('sketch-workbench').hidden,true);
});
test('switching drawings cancels the old model download so it cannot compete for the slow link',async()=>{
  const x=setup(); let oldSignal;
  x.Studio.portfolio.api=async(path,options)=>{
    if(!path.includes('/activities/'))return {activities:[result('a'),result('b')]};
    if(path.endsWith('/a'))return new Promise((resolve,reject)=>{
      oldSignal=options.signal;
      oldSignal.addEventListener('abort',()=>reject(new Error('cancelled')),{once:true});
    });
    return {outputs:{scene:{method:'cloud-glb'}}};
  };
  const old=x.Studio.sketchWorkbench.refresh();await new Promise(setImmediate);
  assert.equal(oldSignal.aborted,false);
  x.select('b');await x.Studio.sketchWorkbench.refresh();await old;
  assert.equal(oldSignal.aborted,true);
  assert.deepEqual(x.opens,['b']);
});
test('a failed saved-model download keeps the drawing visible and offers a retry',async()=>{
  const x=setup(); let attempts=0;
  x.Studio.portfolio.api=async path=>{
    if(!path.includes('/activities/'))return {activities:[result('a')]};
    if(++attempts===1)throw Error('network lost');
    return {outputs:{scene:{method:'cloud-glb'}}};
  };
  await x.Studio.sketchWorkbench.refresh();
  const pair=x.el('sketch-workbench').children[0], retry=pair.children[1].children[2];
  assert.equal(pair.children[0].children[0].textContent,'relight.original');
  assert.equal(retry.textContent,'cloud3d.retryOpen');
  retry.onclick();await new Promise(setImmediate);
  assert.deepEqual(x.opens,['a']);
});
test('an ungenerated sketch shows its original and an empty work area without requesting generation',async()=>{
  const x=setup();let calls=0;x.Studio.portfolio.api=async()=>{calls++;return {activities:[]};};
  await x.Studio.sketchWorkbench.refresh();
  assert.equal(calls,1);assert.deepEqual(x.opens,[]);assert.equal(x.el('sketch-workbench').hidden,false);
  assert.equal(x.el('sketch-workbench').children[0].children.length,2);
  assert.equal(x.el('buddy-actions').parentNode.className,'sketch-controls');
  assert.equal(x.el('cloud3d-choice').parentNode,x.el('buddy'),'model choice stays out of the viewer');
  assert.equal(x.el('creation-workspace').classList.contains('sketch-study'),true);
  const copy=x.el('sketch-workbench').children[0].children[1].children[1];
  const idle=copy.textContent;
  x.Studio.state.making='sketch-to-3d';await x.Studio.sketchWorkbench.refresh();
  assert.equal(copy.textContent,'cloud3d.generating');
  x.Studio.state.making=null;await x.Studio.sketchWorkbench.refresh();
  assert.equal(copy.textContent,idle);
  x.Studio.sketchWorkbench.close();
  assert.equal(x.el('buddy-actions').parentNode,x.el('buddy'));
  assert.equal(x.el('cloud3d-choice').parentNode,x.el('buddy'));
  assert.equal(x.el('creation-workspace').classList.contains('sketch-study'),false);
});

test('the original is visible while the course checks for a saved model',async()=>{
  const x=setup();let release;
  x.Studio.portfolio.api=()=>new Promise(resolve=>{release=resolve;});
  const pending=x.Studio.sketchWorkbench.refresh();
  assert.equal(x.el('sketch-workbench').hidden,false);
  assert.equal(x.el('sketch-workbench').children[0].children.length,2);
  assert.equal(x.el('buddy-actions').parentNode,x.el('buddy'));
  release({activities:[]});await pending;
  assert.equal(x.el('buddy-actions').parentNode.className,'sketch-controls');
});

test('saved 3D work in a colour course uses form copy; an ordinary animation does not',async()=>{
  const x=setup();x.Studio.state.settings.entrance='colour';
  x.el('piece-title').textContent='animation';
  x.Studio.portfolio.api=async path=>path.includes('/activities/')?{outputs:{scene:{}}}:{activities:[result('a')]};
  await x.Studio.sketchWorkbench.refresh();
  assert.equal(x.el('piece-title').textContent,'picture.title.form');
  assert.equal(x.el('piece-hint').textContent,'picture.hint.form');
  assert.equal(x.el('creation-workspace').classList.contains('sketch-study'),false);
  assert.equal(x.el('buddy-actions').parentNode,x.el('buddy'));
  x.select('b');x.el('piece-title').textContent='animation';
  x.Studio.portfolio.api=async()=>({activities:[]});
  await x.Studio.sketchWorkbench.refresh();
  assert.equal(x.el('piece-title').textContent,'animation');
  assert.equal(x.el('sketch-workbench').hidden,true);
});

test('an unreadable saved model keeps the original and offers regeneration',async()=>{
  const x=setup();
  x.Studio.relight.open=function(){this.active=null;};
  x.Studio.portfolio.api=async path=>path.includes('/activities/')?{outputs:{scene:{method:'cloud-glb'}}}:{activities:[result('a')]};
  await x.Studio.sketchWorkbench.refresh();
  const pair=x.el('sketch-workbench').children[0];
  assert.equal(pair.children.length,2);
  assert.equal(pair.children[1].children[1].textContent,'cloud3d.workbenchFailed');
  assert.equal(x.el('buddy-actions').parentNode.className,'sketch-controls');
});

test('an older saved light study keeps its viewer tools beside the original',async()=>{
  const x=setup();
  x.Studio.relight.open=function(host){this.close();
    const views=x.el('legacy-views'),stage=x.el('legacy-stage');views.className='relight-views';
    stage.append(x.el('legacy-canvas'));views.append(x.el('legacy-original'),stage);
    for(const [id,name] of [['legacy-note','relight-note'],['legacy-hint','relight-hint'],['legacy-controls','relight-controls']])x.el(id).className=name;
    host.append(x.el('legacy-note'),views,x.el('legacy-hint'),x.el('legacy-controls'));
    this.active={host};};
  x.Studio.portfolio.api=async path=>path.includes('/activities/')?{outputs:{scene:{method:'single-image-mesh'}}}:{activities:[result('a')]};
  await x.Studio.sketchWorkbench.refresh();
  const stage=x.el('legacy-stage');
  assert.equal(stage.children[0].textContent,'cloud3d.workbenchTitle');
  assert.equal(x.el('legacy-controls').parentNode,null,'old light controls do not duplicate the shared viewer');
  assert.equal(x.el('legacy-hint').parentNode,null);
  assert.equal(x.el('buddy-actions').parentNode.className,'sketch-controls');
  assert.equal(x.el('buddy-actions').parentNode.parentNode,stage);
  x.Studio.sketchWorkbench.close();
  assert.equal(x.el('buddy-actions').parentNode,x.el('buddy'));
});

test('reloading a generated study keeps its controls and old model until the new result is ready',async()=>{
  const x=setup();let release;let newest=false;
  x.Studio.portfolio.api=async path=>{
    if(path==='/c')return {activities:[{...result('a'),id:newest?'new':'old'}]};
    if(path.endsWith('/new'))return new Promise(resolve=>{release=resolve;});
    return {outputs:{scene:{method:'cloud-glb',version:newest?2:1}}};
  };
  await x.Studio.sketchWorkbench.refresh();
  assert.equal(x.Studio.sketchWorkbench.hasModelFor,'a');
  const original=x.Studio.relight.active;
  newest=true;
  const pending=x.Studio.sketchWorkbench.refreshLatest();await new Promise(setImmediate);
  assert.equal(x.Studio.relight.active,original);
  assert.equal(x.el('buddy-actions').parentNode.className,'sketch-controls');
  release({outputs:{scene:{method:'cloud-glb',version:2}}});await pending;
  assert.notEqual(x.Studio.relight.active,original);
  assert.equal(x.el('buddy-actions').parentNode.className,'sketch-controls');
  assert.equal(x.el('primary-text').textContent,'cloud3d.regenerate');
});

test('a completed regeneration uses the scene already delivered in its event',async()=>{
  const x=setup(),calls=[];let newest=false;
  x.Studio.portfolio.api=async path=>{calls.push(path);
    return path==='/c'?{activities:[{...result('a'),id:newest?'new':'old'}]}
      :{outputs:{scene:{method:'cloud-glb',version:1}}};};
  await x.Studio.sketchWorkbench.refresh();
  x.Studio.sketchWorkbench.remember('/c/activities/new',{outputs:{scene:{method:'cloud-glb',version:2}}});
  newest=true;await x.Studio.sketchWorkbench.refreshLatest();
  assert.equal(x.Studio.relight.active.scene.version,2);
  assert.equal(calls.includes('/c/activities/new'),false);
});

test('a failed regeneration download leaves the earlier viewer usable',async()=>{
  const x=setup();let newest=false;
  x.Studio.portfolio.api=async path=>{
    if(path==='/c')return {activities:[{...result('a'),id:newest?'new':'old'}]};
    if(path.endsWith('/new'))throw Error('network lost');
    return {outputs:{scene:{method:'cloud-glb'}}};
  };
  await x.Studio.sketchWorkbench.refresh();const original=x.Studio.relight.active;
  newest=true;await x.Studio.sketchWorkbench.refreshLatest();
  assert.equal(x.Studio.relight.active,original);
  assert.equal(x.el('buddy-actions').parentNode.className,'sketch-controls');
  const stage=x.el('sketch-workbench').children[0].children[1];
  assert.equal(stage.children.find(child=>child.className==='sketch-generation-status').textContent,'cloud3d.refreshFailed');
});

test('a remade model sent apart that cannot be fetched leaves the earlier one up and offers retry, then is kept',async()=>{
  // The model comes at its own address (studio/server/media_links.py); it must arrive before the earlier one goes.
  const x=setup();let newest=false,fetches=0,stalls=true;
  const address='/api/courses/c/activities/new/media/scene.glb?v=1',whole=Buffer.from('model').toString('base64');
  x.Studio.steady=async()=>{fetches++;if(stalls)throw Error('stalled, and stalled again');return new Blob(['model']);};
  x.context.FileReader=class{readAsDataURL(blob){blob.arrayBuffer().then(b=>{this.result='data:model/gltf-binary;base64,'+Buffer.from(b).toString('base64');this.onload();});}};
  x.Studio.portfolio.api=async path=>path==='/c'?{activities:[{...result('a'),id:newest?'new':'old'}]}
    :{outputs:{scene:{method:'cloud-glb',glb:path.endsWith('/new')?address:'aGVsbG8='}}};
  await x.Studio.sketchWorkbench.refresh();const original=x.Studio.relight.active;
  newest=true;await x.Studio.sketchWorkbench.refreshLatest();
  assert.equal(x.Studio.relight.active,original,'the earlier model stays while the new one cannot be had');
  const notice=x.el('sketch-workbench').children[0].children[1].children.find(child=>child.className==='sketch-generation-status');
  const retry=notice.children.find(child=>child.textContent==='cloud3d.retryOpen');
  assert.ok(retry,'the failure ends in the retry the workbench already offers');
  stalls=false;await retry.onclick();
  assert.equal(x.Studio.relight.active.scene.glb,whole,'the viewer gets the model itself, as base64');
  assert.equal([...x.Studio.sketchWorkbench.saved.values()].at(-1).outputs.scene.glb,whole,'kept, so coming back opens it at once');
  assert.equal(fetches,2);
});

test('a failed 3D generation leaves its earlier viewer and displays the failure there',async()=>{
  const x=setup();
  x.Studio.portfolio.api=async path=>path==='/c'?{activities:[result('a')]}:{outputs:{scene:{method:'cloud-glb'}}};
  await x.Studio.sketchWorkbench.refresh();const original=x.Studio.relight.active;
  x.Studio.sketchWorkbench.generationFailed('generation failed');
  assert.equal(x.Studio.relight.active,original);
  const stage=x.el('sketch-workbench').children[0].children[1];
  assert.equal(stage.children.find(child=>child.className==='sketch-generation-status').textContent,'generation failed');
});

test('an invalid new 3D result cannot replace the earlier usable viewer',async()=>{
  const x=setup();let newest=false;
  x.Studio.cloudRelight.valid=scene=>scene.version===1;
  x.Studio.portfolio.api=async path=>path==='/c'
    ?{activities:[{...result('a'),id:newest?'new':'old'}]}
    :{outputs:{scene:{method:'cloud-glb',version:path.endsWith('/new')?2:1}}};
  await x.Studio.sketchWorkbench.refresh();const original=x.Studio.relight.active;
  newest=true;await x.Studio.sketchWorkbench.refreshLatest();
  assert.equal(x.Studio.relight.active,original);
  assert.equal(x.el('buddy-actions').parentNode.className,'sketch-controls');
});

test('a regenerated study shows the latest result without a model or version menu',async()=>{
  const x=setup();
  x.Studio.portfolio.api=async path=>path==='/c'
    ?{activities:[{...result('a'),id:'old'},{...result('a'),id:'new'}]}
    :{outputs:{scene:{method:'cloud-glb',version:path.endsWith('/old')?1:2}}};
  await x.Studio.sketchWorkbench.refresh();
  assert.equal(x.Studio.relight.active.scene.version,2);
  assert.equal(x.el('buddy-actions').parentNode.className,'sketch-controls');
  assert.equal(x.el('cloud3d-choice').parentNode,x.el('buddy'));
  assert.equal(x.Studio.sketchWorkbench.selectedActivity.size,0);
});

test('workbench heading preserves the active translation language',()=>{
  const x=setup();
  const context={Studio:x.Studio,localStorage:{getItem(){return 'zh';}}};
  context.window=context;
  vm.createContext(context);
  for(const name of ['studio/page/src/20-i18n.js','studio/page/locales/zh.js'])
    vm.runInContext(readFileSync(name,'utf8'),context);
  x.Studio.i18n.lang='zh';x.Studio.sketchWorkbench.syncHeading();
  assert.equal(x.el('piece-title').textContent,'转一转，看看画里的形体');
  x.Studio.i18n.lang='en';x.Studio.sketchWorkbench.syncHeading();
  assert.equal(x.el('piece-title').textContent,'转一转，看看画里的形体');
});

test('coming back to a drawing opens its saved model at once, and says it is opening the first time',async()=>{
  const x=setup(), calls=[]; let release;
  x.Studio.portfolio.api=async path=>{calls.push(path);
    return path.includes('/activities/')?new Promise(resolve=>{release=resolve;}):{activities:[result('a'),result('b')]};};
  const first=x.Studio.sketchWorkbench.refresh();await new Promise(setImmediate);
  const shown=x.el('sketch-workbench');
  assert.equal(shown.hidden,false,'the original stays in view while the model downloads');
  assert.equal(shown.children[0].children[1].children[1].textContent,'cloud3d.opening');
  release({outputs:{scene:{method:'cloud-glb'}}});await first;
  assert.equal(x.el('buddy-actions').parentNode.className,'sketch-controls');
  assert.equal(x.el('cloud3d-choice').parentNode,x.el('buddy'),'saved results use the same viewer without a version menu');
  x.Studio.portfolio.api=async path=>{calls.push(path);return path.includes('/activities/')?{outputs:{scene:{}}}:{activities:[result('a'),result('b')]};};
  x.select('b');await x.Studio.sketchWorkbench.refresh();
  x.select('a');await x.Studio.sketchWorkbench.refresh();
  assert.deepEqual(x.opens,['a','b','a']);
  assert.equal(calls.filter(path=>path==='/c/activities/a').length,1,'the model is downloaded once, not on every return');
});

test('the teacher keeps the angle she turned the model to, and it opens that way next time',async()=>{
  const x=setup(), sent=[];
  const scene={method:'cloud-glb',camera_base:[150,65],camera_calibration:{status:'matched'}};
  x.Studio.relight.open=function(host,s,d){this.close();x.opens.push([d.id,s.camera_base]);
    const pair=x.el('test-pair');pair.className='sketch-pair';pair.replaceChildren(x.el('test-original'),x.el('test-stage'));
    host.append(pair);this.active={view:()=>[31,64],host};};
  x.Studio.portfolio.api=async(path,options)=>{if(options?.method==='PATCH')sent.push([path,JSON.parse(options.body)]);
    return path.endsWith('/view')?null:path.includes('/activities/')?{outputs:{scene}}:{activities:[result('a')]};};
  await x.Studio.sketchWorkbench.refresh();
  const controls=x.el('buddy-actions').parentNode;
  assert.equal(controls.className,'sketch-controls');
  const button=controls.children.find(child=>child.className?.includes('keep-view'));
  assert.equal(button.textContent,'cloud3d.keepView');
  await button.onclick();await new Promise(setImmediate);
  assert.deepEqual(sent,[['/c/activities/a/view',{camera_base:[31,64]}]]);
  assert.deepEqual(x.opens,[['a',[150,65]],['a',[31,64]]]);
  assert.deepEqual(JSON.parse(JSON.stringify(scene.camera_calibration)),{status:'teacher',check:{status:'matched'}});
});

test('closing the viewer from anywhere hands the make button back instead of throwing it away',async()=>{
  const x=setup();
  x.Studio.portfolio.api=async path=>path.includes('/activities/')?{outputs:{scene:{method:'cloud-glb'}}}:{activities:[result('a')]};
  await x.Studio.sketchWorkbench.refresh();
  assert.equal(x.el('buddy-actions').parentNode.className,'sketch-controls');
  // Leaving the tab closes whatever media is showing through the real viewer's close, not the workbench's:
  // before the fix, that emptied the 3D panel with the button row inside it, and every tab switch after it failed.
  const viewer=x.Studio.relight.active;
  vm.runInContext(readFileSync('studio/page/src/27e-relight.js','utf8'),x.context);
  x.Studio.relight.active=Object.assign(viewer,{dispose(){viewer.host.replaceChildren();}});
  x.Studio.relight.close();
  assert.equal(x.el('buddy-actions').parentNode,x.el('buddy'));
  assert.equal(x.Studio.sketchWorkbench.key,'','the next visit rebuilds the panel it can no longer trust');
});
