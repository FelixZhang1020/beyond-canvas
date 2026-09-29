import test from 'node:test';
import assert from 'node:assert/strict';
import { loadStudio } from './load.mjs';
function harness() {
  const elements={};
  const node=id=>Object.values(elements).reverse().find(el=>el.id===id) || (elements[id] ||= {hidden:true,textContent:'',dataset:{},children:[],attrs:{},setAttribute(k,v){this.attrs[k]=v;},replaceChildren(){this.children=[];},append(...v){this.children.push(...v);},addEventListener(){}});
  let serial=0;
  const S=loadStudio({files:['src/29d-deployments.js'],globals:{document:{getElementById:node,createElement:()=>node('new'+serial++)}}});
  S.voice={configure(){}};
  return {S,node};
}
const cards=node=>node('deployment-checks').children.flatMap(group=>group.children[2].children);
const state=selected=>({selected,options:[{id:'earlier',name:'Earlier setup'},{id:'other',name:'Other setup'},{id:'stepfun',name:'StepFun first'}]});
const report=(target,ready=true)=>({target,ready,components:[{slot:'vlm.studio',model:target,status:ready?'ready':'unavailable',reason:ready?'catalog':'connection'}]});
test('toggle checks its setup without applying; apply preserves open editor',async()=>{
 const {S,node}=harness(); const checks=[],writes=[];
 S.state.session='old'; S.state.capabilities={deployment:'earlier'};
 S.state.transport={deployments:async()=>state('earlier'),checkDeployment:async n=>{checks.push(n);return report(n);},selectDeployment:async n=>{writes.push(n);return state(n);}};
 await S.deployments.open(); await S.deployments.choose('stepfun');
 assert.deepEqual(checks,['earlier','stepfun']);assert.deepEqual(writes,[]);
 assert.equal(node('deployment-stepfun').attrs['aria-pressed'],'true');
 assert.equal(cards(node)[0].children[2].textContent.includes('stepfun'),true);
 await S.deployments.apply();assert.deepEqual(writes,['stepfun']);
 assert.equal(S.state.session,'old');assert.equal(S.state.capabilities.deployment,'earlier');
});
test('late check for another setup cannot replace current results',async()=>{
 const {S,node}=harness();let finish;
 S.state.transport={deployments:async()=>state('earlier'),checkDeployment:async n=>n==='stepfun'?new Promise(r=>finish=r):report(n)};
 await S.deployments.open();const pending=S.deployments.choose('stepfun');
 assert.equal(node('deployment-checks').children.length,0);
 await S.deployments.choose('earlier');finish(report('stepfun',false));await pending;
 assert.equal(node('deployment-earlier').attrs['aria-pressed'],'true');
 assert.equal(cards(node)[0].dataset.status,'ready');
 assert.equal(cards(node)[0].children[2].textContent.includes('earlier'),true);
});
test('blocked apply keeps applied setup distinct from the inspected setup',async()=>{
 const {S,node}=harness();
 S.state.transport={deployments:async()=>state('earlier'),checkDeployment:async n=>report(n,false),selectDeployment:async()=>({...state('earlier'),switched:false,check:report('stepfun',false)})};
 await S.deployments.open();await S.deployments.choose('stepfun');await S.deployments.apply();
 assert.equal(node('deployment-stepfun').attrs['aria-pressed'],'true');
 assert.equal(cards(node)[0].dataset.status,'unavailable');
 assert.equal(node('deployment-apply').disabled,false);
});

test('groups components by capability and includes purpose and failure impact',async()=>{
 const {S,node}=harness();
 S.state.transport={deployments:async()=>state('earlier'),checkDeployment:async()=>({ready:false,components:[
 {slot:'speech.in',model:'Whisper',status:'unavailable',reason:'connection'},
 {slot:'vlm.studio',model:'vision',status:'ready',reason:'catalog'},
 {slot:'tts.studio',model:'voice',status:'unknown',reason:'unsupported'}]})};
 await S.deployments.open();
 const groups=node('deployment-checks').children;
 assert.equal(groups.length,2);
 assert.equal(groups[0].children[2].children.length,1);
 assert.equal(groups[1].children[2].children.length,2);
 const speech=cards(node).find(c=>c.children[2].textContent.includes('Whisper'));
 assert.equal(speech.dataset.status,'unavailable');
 assert.match(speech.children[1].textContent,/转成文字/);
 assert.match(speech.children[3].children[1].textContent,/可改用键盘输入/);
 assert.equal(cards(node).find(c=>c.dataset.status==='unknown').children[0].children[1].textContent.includes('未验证'),true);
});

test('dashboard counts actual statuses and hides totals while a fresh check runs',async()=>{
 const {S,node}=harness();let finish;
 S.state.transport={deployments:async()=>state('earlier'),checkDeployment:async()=>({ready:false,components:[
 {slot:'vlm.studio',model:'a',status:'ready',reason:'catalog'},
 {slot:'speech.in',model:'b',status:'unavailable',reason:'connection'},
 {slot:'tts.studio',model:'c',status:'unknown',reason:'unsupported'}]})};
 await S.deployments.open();
 assert.deepEqual(node('deployment-overview').children.map(c=>c.children[1].textContent),['3','1','1','1']);
 S.state.transport.checkDeployment=()=>new Promise(r=>finish=r);
 const pending=S.deployments.check();assert.equal(node('deployment-overview').hidden,true);
 finish({ready:false,components:[]});await pending;
 assert.equal(node('deployment-overview').hidden,true);
});


test('setup buttons follow the registry and expose each alternative with provenance',async()=>{
 const {S,node}=harness();
 S.state.transport={deployments:async()=>state('earlier'),checkDeployment:async()=>({ready:true,components:[
 {slot:'mesh.portrait.trellis2',model:'TRELLIS.2',provider:'Replicate',location:'API',source:'Official model',status:'ready',reason:'catalog'},
 {slot:'mesh.portrait.pixal',model:'Alternative',optional:true,provider:'Provider B',location:'API',status:'unavailable',reason:'credentials'}]})};
 await S.deployments.open();
 assert.deepEqual(node('deployment-options').children.map(n=>n.id),['deployment-earlier','deployment-other','deployment-stepfun']);
 assert.equal(cards(node).length,2);
 assert.match(cards(node)[0].children[3].children[3].textContent,/Replicate/);
 assert.match(cards(node)[1].children[0].children[0].textContent,/可选/);
 await S.deployments.choose('bogus');assert.equal(node('deployment-earlier').attrs['aria-pressed'],'true');
});


test('a completed check refreshes editor capabilities and keeps the session on its own deployment',async()=>{
 // The picture-model selection this also guarded went with the still picture.
 const {S,node}=harness();let checked=false,events=0;
 S.state.session='old';
 S.bus.on('capabilities',()=>events++);
 S.state.transport={deployments:async sid=>({...state('earlier'),session:{deployment:'earlier',mesh_models:[{id:'alternative',status:checked?'unavailable':'unknown'}]}}),checkDeployment:async n=>{checked=true;return report(n);}};
 await S.deployments.open();await S.deployments.choose('stepfun');
 assert.equal(S.state.capabilities.mesh_models[0].status,'unavailable');
 assert.equal(node('deployment-stepfun').attrs['aria-pressed'],'true');assert.equal(S.state.capabilities.deployment,'earlier');assert.equal(events,2);
});

test('a delayed capabilities refresh cannot overwrite a newer session',async()=>{
 const {S}=harness();let finish,count=0;
 S.state.session='old';
 S.state.transport={deployments:async()=>++count===1?state('earlier'):new Promise(r=>finish=r),checkDeployment:async n=>report(n)};
 const pending=S.deployments.open();
 while(!finish) await Promise.resolve();
 S.state.session='new';S.state.capabilities={deployment:'other'};
 finish({...state('earlier'),session:{deployment:'earlier'}});await pending;
 assert.equal(S.state.capabilities.deployment,'other');
});

test('late capability data cannot replace a more recent setup check',async()=>{
 const {S,node}=harness();let finish,count=0;
 S.state.session='old';
 S.state.transport={deployments:async()=>{count++;return count===2?new Promise(r=>finish=r):({...state('earlier'),session:{deployment:'earlier',marker:'latest'}});},checkDeployment:async n=>report(n)};
 const pending=S.deployments.open();while(!finish) await Promise.resolve();
 await S.deployments.choose('stepfun');
 finish({...state('earlier'),session:{deployment:'earlier',marker:'stale'}});await pending;
 assert.equal(S.state.capabilities.marker,'latest');assert.equal(node('deployment-stepfun').attrs['aria-pressed'],'true');
});

test('status separates dated generation evidence from current unknown readiness',async()=>{
 const {S,node}=harness();
 S.state.transport={deployments:async()=>state('earlier'),checkDeployment:async()=>({ready:true,components:[
 {slot:'mesh.portrait.pixal',model:'pixal',provider:'fal.ai',status:'unknown',reason:'unsupported',optional:true},
 {slot:'mesh.portrait.trellis2',model:'trellis2',provider:'DGX Spark',status:'ready',reason:'standby'}]})};
 await S.deployments.open();
 assert.match(node('deployment-status').textContent,/检查时间/);
 const rows=cards(node);
 const pixal=rows.find(c=>c.dataset.status==='unknown');
 assert.match(pixal.children.at(-1).textContent,/曾真实生成成功/);
 assert.match(pixal.children[0].children[1].textContent,/未验证/);
 assert.equal(rows.find(c=>c.dataset.status==='ready').children.length,4);
});

test('with one deployment the panel is a status board: no switch, no apply, still checked',async()=>{
 // StepFun First is the only deployment now. The switch and
 // Apply hide themselves because the service lists one option, not because the
 // page knows the product: list two again and they come back.
 const {S,node}=harness();const checks=[];
 const only={selected:'stepfun',options:[{id:'stepfun',name:'StepFun first'}]};
 S.state.transport={deployments:async()=>only,checkDeployment:async n=>{checks.push(n);return report(n);}};
 await S.deployments.open();
 assert.equal(node('deployment-options').hidden,true);
 assert.equal(node('deployment-apply').hidden,true);
 assert.deepEqual(checks,['stepfun']);
 assert.equal(cards(node)[0].dataset.status,'ready');
 assert.match(node('deployment-detail').textContent,/订阅内的 StepFun 模型/);
});
