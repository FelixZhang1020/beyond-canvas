import test from 'node:test';
import assert from 'node:assert/strict';
import vm from 'node:vm';
import {readFileSync} from 'node:fs';

test('one compact sketch control panel drives either renderer and keeps legacy wireframe honest', () => {
  class Node {
    children=[];dataset={};attributes={};parentNode=null;
    constructor(tag){this.tagName=tag;}
    append(...nodes){for(const node of nodes){this.children.push(node);node.parentNode=this;}}
    setAttribute(name,value){this.attributes[name]=value;}
  }
  const calls=[];
  const stage=new Node('figure');
  const active={inspect:()=>({wireAvailable:false,richMaterials:false,direction:-30}),control:(...args)=>calls.push(args)};
  const context={Studio:{i18n:{t:key=>key},relight:{}},document:{createElement:tag=>new Node(tag),createTextNode:text=>Object.assign(new Node('#text'),{textContent:text})},stage,active};
  vm.createContext(context);
  vm.runInContext(readFileSync('studio/page/src/27g-cloud-relight.js','utf8'),context);
  const ui=vm.runInContext('sketchViewerControls(stage,active)',context);
  const walk=(node)=>[node,...node.children.flatMap(walk)];
  const nodes=walk(stage);
  const button=key=>nodes.find(n=>n.tagName==='button'&&n.textContent==='cloud3d.viewer.'+key);
  assert.equal(stage.children.length,1);
  const allMaterials=['plaster','matte','marble','wood','metal','glass','denim','rust','chocolate','normal','wire'];
  assert.equal(allMaterials.filter(name=>button(name)).length,11,'all classroom materials remain visible');
  assert.equal(button('wire').disabled,true,'an analytic legacy study has no triangle data');
  assert.equal(button('marble').disabled,true,'a legacy analytic result cannot display a scanned surface');
  assert.equal(button('plaster').attributes['aria-pressed'],'true');
  const views=nodes.find(n=>n.className==='sketch-view-actions').children.map(n=>n.textContent);
  assert.deepEqual(views,['cloud3d.viewer.auto','cloud3d.viewer.reset'],'dragging turns the model and moves the lamp; two view buttons are enough');
  for (const gone of ['orbit','light','align','zoomIn']) assert.equal(button(gone),undefined);
  button('auto').onclick();
  assert.deepEqual(calls.at(-1),['auto',true]);
  button('matte').onclick();
  assert.deepEqual(calls.at(-1),['material','matte']);
  const direction=nodes.find(n=>n.tagName==='input'&&n.type==='range');
  direction.value='75';direction.oninput();
  assert.deepEqual(calls.at(-1),['direction',75]);
  ui.sync({wireAvailable:true,richMaterials:true,material:'wire',ground:false});
  assert.equal(button('marble').disabled,false);
  button('marble').onclick();
  assert.deepEqual(calls.at(-1),['material','marble']);
  ui.sync({material:'wire'});
  assert.equal(button('wire').disabled,false);
  assert.equal(button('wire').attributes['aria-pressed'],'true');
  ui.sync({ready:false});
  assert.equal(button('auto').disabled,true,'model controls wait for the GLB to finish opening');
  assert.equal(direction.disabled,true);
  ui.sync({ready:true});
  assert.equal(button('auto').disabled,false);
  assert.equal(nodes.some(n=>String(n.textContent).includes('版本与重新生成')),false);
});
