import test from 'node:test';
import assert from 'node:assert/strict';
import { loadStudio } from './load.mjs';
import { readFileSync } from 'node:fs';

test('the planning panel has a distinct id from the existing classroom workspace',()=>{
  const source=readFileSync(new URL('../../studio/page/src/10-app.html',import.meta.url),'utf8');
  const unique=html=>{const ids=Array.from(html.matchAll(/\bid="([^"]+)"/g),m=>m[1]);return ids.length===new Set(ids).size;};
  assert.equal(unique(source),true);
  assert.equal(unique(source+'<section id="creation-workspace"></section>'),false);
});

test('a hidden planner retains task ownership, completion and edited text on return',()=>{
  const h=setup();h.S.creation.render();h.click({create:'rewrite'});h.finish({text:'Keep this draft'});
  h.click({create:'confirm'});
  h.setActive(false);h.S.creation.render();
  assert.equal(h.root.hidden,true);
  assert.equal(h.S.creation.owns('painting-to-animation'),true);
  h.finish({video_url:'/saved.mp4'});
  h.setActive(true);h.S.creation.render();
  assert.match(h.root.innerHTML,/data-create="open-(video|figure)"/);
  assert.equal(h.S.state.motionDrafts.a,'Keep this draft');
  assert.equal(h.calls.length,2);
});

test('failure while another mode is visible returns to the original draft with its error',()=>{
  const h=setup();h.S.creation.render();h.click({create:'rewrite'});h.finish({text:'My scene'});
  h.click({create:'confirm'});
  h.S.state.mode='book';h.S.creation.render();
  h.S.creation.stopped('Connection lost');h.S.state.busy=false;h.S.state.making=null;h.S.creation.render();
  h.S.state.mode='move';h.S.creation.render();
  assert.match(h.root.innerHTML,/Connection lost/);
  assert.equal(h.S.state.motionDrafts.a,'My scene');
  assert.equal(h.calls.length,2);
});

function setup() {
  const handlers={}, controls={};
  const root={hidden:true,innerHTML:'',addEventListener:(name,fn)=>handlers[name]=fn,
    querySelector:selector=>controls[selector] ||= {disabled:false}};
  const app={dataset:{}};let active=true;
  const queued=[],calls=[],opened=[];
  const S=loadStudio({files:['src/29a-creation.js','src/29h-lanes.js','src/29l-book-look.js'],globals:{queueMicrotask:fn=>queued.push(fn),document:{getElementById:id=>id==='creation-planner'?root:app}}});
  Object.assign(S.state,{session:'one',mode:'move',current:'a',settings:{entrance:'colour'},drawings:[{id:'a',url:'/a'},{id:'b',url:'/b'}]});
  // A draft is written in the talk lane, a clip or a book is made in the making lane.
  S.creation.init({active:()=>active,run:(skill,ids,opts)=>{calls.push({skill,ids,opts});if(S.creation.planning(skill))S.state.busy=true;else S.state.making=skill;S.creation.render();},
    stop:()=>{S.creation.stopped();S.state.busy=false;S.state.making=null;S.creation.render();},open:r=>opened.push(r)});
  function click(dataset){handlers.click({target:{closest:()=>({dataset,disabled:false})}});}
  function finish(out){const c=calls.at(-1);S.creation.completed(c.skill,out,S.state.drawings[0]);S.state.busy=false;S.state.making=null;S.creation.render();}
  function input(id,value,dataset={}){handlers.input({target:{id,value,dataset}});}
  return {S,root,queued,calls,click,finish,input,opened,setActive:v=>active=v};
}

test('entering motion drafts only text; edits reach media only after confirmation',()=>{
  const h=setup();h.S.creation.render();h.click({create:'rewrite'});
  assert.equal(h.calls[0].skill,'scene-description');
  h.finish({text:'A small hop'});
  assert.equal(h.calls.length,1);
  h.input('creation-motion','孩子编辑🌷');
  h.click({create:'rewrite'});assert.equal(h.calls[1].skill,'scene-description');
  assert.equal(h.calls[1].opts.previous,'孩子编辑🌷');
  h.click({create:'cancel'});
  assert.equal(h.S.state.motionDrafts.a,'孩子编辑🌷');
  h.click({create:'confirm'});
  assert.equal(h.calls[2].skill,'painting-to-animation');
  assert.equal(h.calls[2].opts.hint,'孩子编辑🌷');
});

test('book orders pictures, supplies available scenes, then sends exact edited passages',()=>{
  const h=setup();h.S.state.mode='book';h.S.state.motionDrafts={a:'Scene A'};h.S.creation.render();
  h.click({up:'b'});h.click({create:'plot'});
  assert.deepEqual(Array.from(h.calls[0].ids),['b','a']);
  assert.equal(h.calls[0].opts.scenes.a,'Scene A');assert.equal(h.calls[0].opts.scenes.b,undefined);
  const pages=[{drawing_id:'b',text:'B story'},{drawing_id:'a',text:'A story'}];
  h.finish({outline:pages,scenes:[{drawing_id:'b',text:'Scene B',supplemented:true},{drawing_id:'a',text:'Scene A',supplemented:false}]});
  assert.equal(h.S.state.motionDrafts.b,'Scene B');
  h.input('', '我的情节🌷', {page:'0'});assert.equal(h.calls.length,1);
  h.click({create:'book'});assert.equal(h.calls.length,1,'confirming the story opens the choice of pictures');
  h.click({create:'look-bind'});assert.equal(h.calls[1].skill,'drawings-to-storybook');
  assert.equal(h.calls[1].opts.pages[0].text,'我的情节🌷');
});

test('changed picture order and changed scene both invalidate an old plot',()=>{
  const h=setup();h.S.state.mode='book';h.S.creation.render();h.click({create:'plot'});
  h.finish({outline:[{drawing_id:'a',text:'A'},{drawing_id:'b',text:'B'}],scenes:[{drawing_id:'a',text:'A scene'},{drawing_id:'b',text:'B scene'}]});
  h.click({create:'back'});h.click({up:'b'});h.click({create:'book'});
  assert.equal(h.calls.length,1,'A mismatched order must never produce a book');
  h.click({up:'a'});h.S.state.motionDrafts.a='New scene';h.click({create:'book'});
  assert.equal(h.calls.length,1,'An old plot cannot confirm changed scenes');
});

test('opening a picture, and moving to another, starts nothing on its own',()=>{
  const h=setup();h.S.creation.render();
  assert.equal(h.calls.length,0);assert.equal(h.queued.length,0);assert.equal(h.S.state.busy,false);
  assert.match(h.root.innerHTML,/这幅画的作品/);
  assert.match(h.root.innerHTML,/data-create="edit-video"/);
  h.S.state.current='b';h.S.creation.render();
  assert.equal(h.calls.length,0);assert.equal(h.queued.length,0);assert.equal(h.S.state.busy,false);
});

test('an old running backend cannot accidentally receive unsupported planning requests',()=>{
  const h=setup();h.S.creation.configure(['painting-to-animation']);h.S.creation.render();
  h.click({create:'rewrite'});assert.equal(h.calls.length,0);assert.equal(h.queued.length,0);
  h.S.creation.configure(['painting-to-animation','scene-description','story-outline']);h.click({create:'rewrite'});
  assert.equal(h.calls[0].skill,'scene-description');
});

test('empty text cannot trigger animation and changing classes discards old results',()=>{
  const h=setup();h.S.state.motionDrafts={a:''};h.S.creation.render();h.click({create:'confirm'});assert.equal(h.calls.length,0);
  h.input('creation-motion','Hop');h.click({create:'confirm'});h.finish({video_url:'/old'});
  h.click({create:'open'});assert.equal(h.opened.length,1);
  h.S.state.session='two';h.S.state.motionDrafts={};h.S.creation.render();h.click({create:'open'});assert.equal(h.opened.length,1);
});

test('make it move only ever asks for the clip, even from a studio still reporting the retired picture choice',()=>{
  // The FLUX still picture was retired (Wan makes the real animation). An older
  // studio could still send image_edit and image_models; the page offers neither a picture nor a
  // picture model, and the request carries the words and asks for the clip by name, which is also
  // what gives the task line its measured twelve minutes instead of the unmeasured five.
  const h=setup();h.S.state.capabilities={image_edit:true,image_models:[{id:'flux',label:'FLUX.2 Klein 4B',status:'ready'}]};h.S.state.mediaKind='image';
  h.S.creation.render();h.click({create:'edit-video'});h.click({create:'rewrite'});h.finish({text:'轻轻抬头'});
  assert.doesNotMatch(h.root.innerHTML,/creation-output|creation-image-model|creation-fixed-model|FLUX/);
  assert.match(h.root.innerHTML,/maxlength="600"/);
  h.click({create:'confirm'});
  assert.equal(h.calls.at(-1).skill,'painting-to-animation');
  assert.equal(JSON.stringify(h.calls.at(-1).opts),JSON.stringify({hint:'轻轻抬头',media_kind:'video'}));
});

test('a scene the check still refused after its tries stays editable and can be confirmed as it is',()=>{
 // Operator: pressing 重新生成描述 must end in a description they can use. The studio now writes it
 // up to three times on one press; what it still refuses comes with the check's notes as advice only.
 const h=setup();h.S.creation.render();h.click({create:'rewrite'});
 h.S.creation.stopped('Review failed',{skill:'scene-description',drawing_id:'a',text:'Rejected draft'},[],true);h.S.state.busy=false;h.S.state.making=null;h.S.creation.render();
 assert.equal(h.S.state.motionDrafts.a,'Rejected draft');assert.match(h.root.innerHTML,/重写过几次/);
 assert.doesNotMatch(h.root.innerHTML,/Review failed/,'the note says it once, never again as a failure under the box');
 h.input('creation-motion','Rejected draft!');h.input('creation-motion','Rejected draft');
 assert.match(h.root.querySelector('.creation-review-warning').textContent,/重写过几次/,'an edit put back keeps the same note');
 assert.equal(h.root.querySelector('[data-create="confirm"]').disabled,false,'never a dead end');
 h.input('creation-motion','Teacher edits');
 h.click({create:'rewrite'});assert.equal(h.calls.at(-1).opts.previous,'Teacher edits');
 h.finish({text:'Reviewed draft'});h.click({create:'confirm'});assert.equal(h.calls.at(-1).skill,'painting-to-animation');
});

test('a rejected story stays visible and edits alone cannot unlock generation',()=>{
 const h=setup();h.S.state.mode='book';h.S.creation.render();h.click({create:'plot'});
 h.S.creation.stopped('Review failed',{skill:'story-outline',outline:[{drawing_id:'a',text:'One'},{drawing_id:'b',text:'Two'}],scenes:[]});h.S.state.busy=false;h.S.state.making=null;h.S.creation.render();
 assert.match(h.root.innerHTML,/One/);h.input('', 'Edited',{page:'0'});h.click({create:'book'});assert.equal(h.calls.length,1);
 h.click({create:'plot'});assert.equal(h.calls.at(-1).opts.previous,undefined,'a new story is written fresh, not from the rejected one');
 h.finish({outline:[{drawing_id:'a',text:'Good one'},{drawing_id:'b',text:'Good two'}],scenes:[]});h.click({create:'book'});h.click({create:'look-bind'});assert.equal(h.calls.at(-1).skill,'drawings-to-storybook');
});

test('a scene rejected during story planning is retained but not sent back as an approved scene',()=>{
 const h=setup();h.S.state.mode='book';h.S.creation.render();h.click({create:'plot'});
 h.S.creation.stopped('Review failed',{skill:'scene-description',drawing_id:'b',text:'Needs checking'});h.S.state.busy=false;h.S.state.making=null;h.S.creation.render();
 assert.equal(h.S.state.motionDrafts.b,'Needs checking');h.click({create:'plot'});assert.equal(h.calls.at(-1).opts.scenes.b,undefined);
});

test('a story rejected after an earlier scene rejection still shows its draft for editing',()=>{
 // Seen live, sketch course. Press 1: scene b rejected, its text parked in
 // motionDrafts. Press 2: b regenerated and passed, then the OUTLINE was rejected.
 // stopped() refused to replace b's stale rejected text, outlineValid() saw the
 // mismatch, and the render threw the edit step away: the teacher was told to edit
 // a draft and shown step 1 with nothing to edit. The success path already handles
 // this three lines up; the stopped path was missing the same clause.
 const h=setup();h.S.state.mode='book';h.S.creation.render();h.click({create:'plot'});
 h.S.creation.stopped('Review failed',{skill:'scene-description',drawing_id:'b',text:'Rejected scene'});h.S.state.busy=false;h.S.state.making=null;h.S.creation.render();
 h.click({create:'plot'});
 h.S.creation.stopped('Review failed',{skill:'story-outline',outline:[{drawing_id:'a',text:'One'},{drawing_id:'b',text:'Two'}],
   scenes:[{drawing_id:'a',text:'Scene A',supplemented:true},{drawing_id:'b',text:'Fresh scene B',supplemented:true}]});h.S.state.busy=false;h.S.state.making=null;h.S.creation.render();
 assert.match(h.root.innerHTML,/data-page="0">One</,'the rejected story is shown for editing');
 assert.equal(h.S.state.motionDrafts.b,'Fresh scene B','the scene that passed replaces the one that was rejected');
});

test('a story the teacher rewrites in every passage can be confirmed as the book',()=>{
 // Five of five outline attempts were refused in one run, two of them seeded with
 // the children's own words: the writer fuses unrelated drawings into one story and
 // the reviewer, rightly, refuses that. The binding keeps supplied text verbatim
 // behind a safety screen, so once every passage is the teacher's, the reviewer of
 // MODEL text has nothing left to review. One edited passage is not enough.
 const h=setup();h.S.state.mode='book';h.S.creation.render();h.click({create:'plot'});
 h.S.creation.stopped('Review failed',{skill:'story-outline',outline:[{drawing_id:'a',text:'One'},{drawing_id:'b',text:'Two'}],scenes:[]});h.S.state.busy=false;h.S.state.making=null;h.S.creation.render();
 h.input('','The child said one',{page:'0'});h.click({create:'book'});
 assert.equal(h.calls.length,1,'one rewritten passage beside a rejected one does not unlock the book');
 h.input('','The child said two',{page:'1'});h.click({create:'book'});h.click({create:'look-bind'});
 assert.equal(h.calls.at(-1).skill,'drawings-to-storybook');
 assert.deepEqual(h.calls.at(-1).opts.pages.map(p=>p.text),['The child said one','The child said two']);
});

test('a keystroke undone or the rejected text pasted back is not a rewrite',()=>{
 // Code review: every input event counted as a rewrite, so typing a
 // character and deleting it on each page unlocked a rejected model outline for
 // binding with no review at all. Ownership is a comparison with the rejected words.
 const h=setup();h.S.state.mode='book';h.S.creation.render();h.click({create:'plot'});
 h.S.creation.stopped('Review failed',{skill:'story-outline',outline:[{drawing_id:'a',text:'One'},{drawing_id:'b',text:'Two'}],scenes:[]});h.S.state.busy=false;h.S.state.making=null;h.S.creation.render();
 h.input('','The child said one',{page:'0'});
 h.input('','Twox',{page:'1'});h.input('','Two',{page:'1'});h.click({create:'book'});
 assert.equal(h.calls.length,1,'typing and undoing on the second page does not unlock the book');
 h.input('',' Two ',{page:'1'});h.click({create:'book'});
 assert.equal(h.calls.length,1,'the rejected text pasted back with spaces is still the rejected text');
 h.input('','',{page:'1'});h.click({create:'book'});
 assert.equal(h.calls.length,1,'an emptied page is not a rewrite either');
 h.input('','The child said two',{page:'1'});h.click({create:'book'});h.click({create:'look-bind'});
 assert.equal(h.calls.at(-1).skill,'drawings-to-storybook');
});

test('a scene rejected while planning the story tells the teacher to press Next again, not to edit',()=>{
 // On the sketch course there is no scene editor, and at step 1 there is never an
 // outline to edit either way. "Edit it and regenerate" pointed at nothing;
 // pressing Next redrafts the rejected scene, so that is what the note says.
 const h=setup();h.S.state.mode='book';h.S.creation.render();h.click({create:'plot'});
 h.S.creation.stopped('Review failed',{skill:'scene-description',drawing_id:'b',text:'Needs checking'});h.S.state.busy=false;h.S.state.making=null;h.S.creation.render();
 assert.match(h.root.innerHTML,/再按一次/);
 assert.doesNotMatch(h.root.innerHTML,/edit it, then regenerate/);
});

test('a rejected scene shows what the review flagged beside the draft until a rewrite passes',()=>{
 const h=setup();h.S.creation.render();h.click({create:'rewrite'});
 h.S.creation.stopped('Review failed',{skill:'scene-description',drawing_id:'a',text:'Three elephants'},
   [{evidence:'candidate adds a third elephant',suggestion:'keep the herd at two'}]);
 h.S.state.busy=false;h.S.state.making=null;h.S.creation.render();
 assert.match(h.root.innerHTML,/复核指出的问题/);
 assert.match(h.root.innerHTML,/candidate adds a third elephant/);
 assert.match(h.root.innerHTML,/keep the herd at two/);
 h.click({create:'rewrite'});h.finish({text:'Two elephants'});
 assert.doesNotMatch(h.root.innerHTML,/third elephant/);
 assert.doesNotMatch(h.root.innerHTML,/复核指出的问题/);
});

test('a rejected story shows what the review flagged beside its passages',()=>{
 const h=setup();h.S.state.mode='book';h.S.state.motionDrafts={a:'Scene A',b:'Scene B'};h.S.creation.render();
 h.click({create:'plot'});
 h.S.creation.stopped('Review failed',{skill:'story-outline',outline:[{drawing_id:'a',text:'One'},{drawing_id:'b',text:'Two'}],scenes:[]},
   [{evidence:'passage two reorders the drawings',suggestion:'keep the chosen order'}]);
 h.S.state.busy=false;h.S.state.making=null;h.S.creation.render();
 assert.match(h.root.innerHTML,/passage two reorders the drawings/);
 assert.match(h.root.innerHTML,/keep the chosen order/);
});

test('a teacher who rewrites a rejected scene can confirm their own words without another review',()=>{
 // The story flow already binds a fully rewritten outline as the teacher's own
 // words. A scene had no such door: after a rejection the confirm button stayed
 // off and every regeneration handed the reviewer fresh model text, so a wrong
 // reviewer could block a teacher for the rest of the class (once for 41 minutes,
 // over three elephants that were in the drawing).
 const h=setup();h.S.creation.render();h.click({create:'rewrite'});
 h.S.creation.stopped('Review failed',{skill:'scene-description',drawing_id:'a',text:'Three elephants'},
   [{evidence:'candidate adds a third elephant',suggestion:'keep the herd at two'}]);
 h.S.state.busy=false;h.S.state.making=null;h.S.creation.render();
 assert.match(h.root.innerHTML,/复核指出的问题/,'the notes stand beside the text as advice');
 h.input('creation-motion','Two elephants walk to the jeep');
 assert.equal(h.root.querySelector('[data-create="confirm"]').disabled,false);
 h.S.creation.render();
 assert.match(h.root.innerHTML,/描述已改为你的文字/);assert.doesNotMatch(h.root.innerHTML,/复核指出的问题/);
 h.click({create:'confirm'});assert.equal(h.calls.at(-1).skill,'painting-to-animation');
 assert.equal(h.calls.at(-1).opts.hint,'Two elephants walk to the jeep');
});

test("pasting the rejected scene text back does not count as the teacher's own words",()=>{
 const h=setup();h.S.creation.render();h.click({create:'rewrite'});
 h.S.creation.stopped('Review failed',{skill:'scene-description',drawing_id:'a',text:'Three elephants'},[]);
 h.S.state.busy=false;h.S.state.making=null;h.S.creation.render();
 h.input('creation-motion','Two elephants');h.input('creation-motion',' Three elephants ');
 h.S.creation.render();
 assert.match(h.root.innerHTML,/重写过几次/);assert.doesNotMatch(h.root.innerHTML,/描述已改为你的文字/);
 h.click({create:'confirm'});assert.equal(h.calls.at(-1).opts.hint,' Three elephants ','still the teacher\'s call');
});
