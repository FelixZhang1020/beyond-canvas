import test from 'node:test';
import assert from 'node:assert/strict';
import { loadStudio } from './load.mjs';

test('restoring a saved response without a question still permits another answer', () => {
  const S=loadStudio({files:['src/26-companion.js']});let asked;
  S.companion.clearResult=()=>{};S.companion.say=()=>{};
  S.companion.ask=(...args)=>asked=args;
  S.companion.els={next:{},heardText:{}};
  for(const beat of ['opening','reply','sample']) {
    asked=undefined;
    S.companion.restoreFeedback({text:'Saved response',beat},'Unsent words');
    assert.ok(asked,'the row for the child\'s next words is made ready');
    assert.equal(S.companion.els.heardText.value,'Unsent words');
  }
});

test('restoring a turn brings back the row for the child\'s next words', () => {
  // Found driving the Spark: after 撤回上一轮 the record, type and send row was gone,
  // because clearing the result hid it and nothing showed it again.
  const S=loadStudio({files:['src/26-companion.js']});
  S.companion.say=()=>{};
  const row={hidden:false}, heard={hidden:false}, answer={hidden:true}, silent={hidden:true};
  S.companion.els={ask:row,heard,answer,silent,next:{},heardText:{value:''}};
  S.companion.clearResult=function(){row.hidden=true;heard.hidden=true;};
  S.companion.restoreFeedback({text:'Saved reply',question:'Where next?',beat:'reply'},'');
  assert.equal(row.hidden,false);
});

test('editing a saved ending pre-fills it, while read-only books refuse editing', () => {
  const fields={ending:{hidden:true},'ending-text':{value:'',focus(){this.focused=true;}}};
  const S=loadStudio({files:['src/28-book.js'],globals:{document:{getElementById:id=>fields[id]}}});
  S.book.stop=()=>{};S.book.pages=[{ending:true,text:'Original ending'}];S.book.i=0;
  S.book.readOnly=true;S.book.editEnding();assert.equal(fields.ending.hidden,true);
  S.book.readOnly=false;S.book.editEnding();assert.equal(fields.ending.hidden,false);
  assert.equal(fields['ending-text'].value,'Original ending');
  assert.equal(fields['ending-text'].focused,true);
});

test('leaving a course clears pose drafts so another course cannot inherit them',async()=>{
  const S=loadStudio({globals:{URL:{revokeObjectURL(){}}}});
  Object.assign(S.state,{session:'one',drawings:[],motionDrafts:{a:'Raise trunk'},transport:{forgetSession:async()=>{}}});
  await S.session.end();assert.equal(Object.keys(S.state.motionDrafts).length,0);
});
