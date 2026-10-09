import test from 'node:test';
import assert from 'node:assert/strict';
import { loadStudio } from './load.mjs';

test('progress stays indeterminate until a valid reported percentage, and resets per stage and task', () => {
  let now=0; const el={innerHTML:'',dataset:{lane:'talk'}};   // the planner's box shows the conversation's lane
  const S=loadStudio({files:['src/29b-task-status.js'],globals:{Date:{now:()=>now},document:{getElementById:()=>el}}});
  S.state.busy=true; S.taskStatus.start();
  now=130000;
  assert.doesNotMatch(S.taskStatus.html(), /value=/);
  assert.match(S.taskStatus.html(), /130/);
  assert.match(S.taskStatus.html(), /等待时间较长/);
  S.taskStatus.update({stage:'painting-to-animation',status:'running',partial:{percent:42}});
  assert.match(el.innerHTML,/value="42"/);
  S.taskStatus.update({stage:'another',status:'running',partial:{percent:120}});
  assert.doesNotMatch(el.innerHTML,/value=/);
  S.taskStatus.update({stage:'another',status:'running',partial:{percent:'50'}});
  assert.doesNotMatch(el.innerHTML,/value=/);
  S.taskStatus.update({stage:'another',status:'loading'});
  assert.match(el.innerHTML,/正在加载模型/);
  S.makeStatus.start('painting-to-animation'); S.makeStatus.update({stage:'painting-to-animation',status:'running',partial:{percent:7}});
  assert.match(el.innerHTML,/正在加载模型/,'a clip being made does not write into the conversation\'s box');
  S.taskStatus.start();
  assert.match(S.taskStatus.html(),/正在提交任务/);
  assert.doesNotMatch(S.taskStatus.html(),/value=/);
});

test('a video job names its measured cost instead of raising an alarm at two minutes', () => {
  let now=0; const el={innerHTML:'',dataset:{lane:'talk'}};   // the planner's box shows the conversation's lane
  const S=loadStudio({files:['src/29b-task-status.js'],globals:{Date:{now:()=>now},document:{getElementById:()=>el}}});
  S.state.busy=true; S.taskStatus.start('painting-to-animation.video');
  // The Spark's 5 s clip: 1,082 s measured (it was 3 s and 691 s before that).
  now=900000;
  assert.doesNotMatch(S.taskStatus.html(), /等待时间较长/);
  assert.match(S.taskStatus.html(), /约 18 分钟/);
  now=1100000;
  assert.match(S.taskStatus.html(), /等待时间较长/);
  assert.doesNotMatch(S.taskStatus.html(), /约 18 分钟/);
});

test('a 3D figure is not called slow while it is still inside its measured time', () => {
  let now=0; const el={innerHTML:'',dataset:{lane:'talk'}};   // the planner's box shows the conversation's lane
  const S=loadStudio({files:['src/29b-task-status.js'],globals:{Date:{now:()=>now},document:{getElementById:()=>el}}});
  S.state.busy=true; S.taskStatus.start('painting-to-animation.figure');
  // The Spark, three writings: one toy in nine took over five minutes; the planner's own note says two to six.
  now=315000;
  assert.doesNotMatch(S.taskStatus.html(), /等待时间较长/);
  assert.match(S.taskStatus.html(), /约 6 分钟/);
  now=370000;
  assert.match(S.taskStatus.html(), /等待时间较长/);
});

test('a task with no measured time keeps the two-minute note', () => {
  let now=0; const el={innerHTML:'',dataset:{lane:'talk'}};   // the planner's box shows the conversation's lane
  const S=loadStudio({files:['src/29b-task-status.js'],globals:{Date:{now:()=>now},document:{getElementById:()=>el}}});
  S.state.busy=true; S.taskStatus.start('drawings-to-storybook');
  now=130000;
  assert.match(S.taskStatus.html(), /等待时间较长/);
  S.taskStatus.start('sketch-to-3d');
  now=260000;
  assert.match(S.taskStatus.html(), /等待时间较长/);
});

async function transport(fetch) {
  const events=[]; let stream;
  class EventSource {
    constructor(){stream=this;this.handlers={};}
    addEventListener(name,fn){this.handlers[name]=fn;}
    close(){this.closed=true;}
  }
  const S=loadStudio({files:['src/23-transport-http.js'],globals:{fetch,EventSource}});
  const task=S.transports.http.request('s','painting-to-animation',['a'],{},ev=>events.push(ev));
  await new Promise(resolve=>setImmediate(resolve));
  return {events,stream,task};
}

test('submission failure differs from server unreachable', async()=>{
  // A refused reply carries a body, and the studio names the refusal in it: the page reads that
  // name to tell a course it can rejoin from one it cannot.
  const rejected=await transport(async()=>({ok:false,status:409,json:async()=>({error:'closed',code:'course_closed'})}));
  assert.equal(rejected.events.at(-1).reason_code,'submission_failed');
  const offline=await transport(async()=>{throw new TypeError('fetch failed');});
  assert.equal(offline.events.at(-1).reason_code,'server_unreachable');
});

test('accepted task reports submission and connection loss without claiming model failure', async()=>{
  const h=await transport(async()=>({ok:true,status:202,json:async()=>({request_id:'r'})}));
  assert.equal(h.events[0].status,'submitted');
  h.stream.onerror(); h.stream.onerror();
  assert.equal(h.events.length,2);
  assert.equal(h.events[1].reason_code,'connection_lost');
});

test('completion and cancellation suppress late connection errors', async()=>{
  const fetch=async()=>({ok:true,status:202,json:async()=>({request_id:'r'})});
  const done=await transport(fetch);
  done.stream.handlers.done({data:'{"outputs":{}}'});done.stream.onerror();
  assert.deepEqual(done.events.map(e=>e.status),['submitted','done']);
  const stopped=await transport(fetch);stopped.task.abort();stopped.stream.onerror();
  assert.deepEqual(stopped.events.map(e=>e.status),['submitted']);
});

test('an online clip is expected in about two minutes', () => {
  let now=0; const el={innerHTML:''};
  const S=loadStudio({files:['src/29b-task-status.js'],globals:{Date:{now:()=>now},document:{getElementById:()=>el}}});
  S.state.busy=true; S.taskStatus.start('painting-to-animation.online');
  // Wan 3.0 on DashScope: 86 s for 5 s and 107 s for 10 s at 480P.
  now=100000;
  assert.match(S.taskStatus.html(), /约 2 分钟/);
  assert.doesNotMatch(S.taskStatus.html(), /等待时间较长/);
});
