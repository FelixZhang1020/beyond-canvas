import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { runInNewContext } from 'node:vm';
import { loadStudio } from './load.mjs';

test('return restores the task picture, mode and book order without owning a new course',()=>{
  const S=loadStudio({files:['src/29c-task-navigation.js']});
  Object.assign(S.state,{session:'s',courseId:'c',mode:'book',current:'a',chosen:['b','a']});
  S.taskNavigation.start();
  S.state.mode='feedback'; S.state.current='b'; S.state.chosen.reverse();
  assert.equal(S.taskNavigation.visible(false),false);
  assert.equal(S.taskNavigation.restore(),true);
  assert.equal(S.state.mode,'book');assert.equal(S.state.current,'a');
  assert.deepEqual(Array.from(S.state.chosen),['b','a']);
  assert.equal(S.taskNavigation.visible(true),false);
  assert.equal(S.taskNavigation.visible(false),true);
  S.state.session='another';
  assert.equal(S.taskNavigation.restore(),false);
  assert.equal(S.taskNavigation.current(),null);
});

test('browsing home leaves the request running; explicit interruption still stops it',async()=>{
  const source=readFileSync(new URL('../../studio/page/src/30-main.js',import.meta.url),'utf8');
  function fn(name){const at=source.indexOf('  function '+name+'(')>=0?source.indexOf('  function '+name+'('):source.indexOf('  async function '+name+'(');assert.ok(at>=0);const rest=source.slice(at);const end=rest.slice(1).search(/\n  (?:async )?function /);return end<0?rest:rest.slice(0,end+1);}
  let stops=0;
  const nodes={};
  const globals={changingClass:false,atHome:false,st:{courseId:'c',current:'a'},
    $:id=>nodes[id] ||= {},rememberDraft(){},updatePrimary(){},stopRun(){stops++;},releaseListening(){},
    S:{book:{stop(){}},media:{close(){}},portfolio:{selected:{},open(){}}}};
  runInNewContext([fn('pauseInteraction'),fn('openHome')].join('\n')+'\nthis.openHome=openHome;this.pauseInteraction=pauseInteraction;',globals);
  globals.openHome();
  assert.equal(stops,0);
  globals.pauseInteraction();assert.equal(stops,1);
});

test('a task the teacher has seen through no longer follows her around',()=>{
  // Seen once: "任务已完成 · 已等待 100 秒 / 返回当前任务" on every 回顾 tab after a
  // review the teacher had already watched finish. Nothing cleared the task's
  // origin once its result had been shown, so the banner stayed until the
  // session changed. A task that finished out of sight still keeps its origin,
  // because that is what 返回当前任务 exists for.
  const S=loadStudio({files:['src/29c-task-navigation.js']});
  Object.assign(S.state,{session:'s',courseId:'c',mode:'feedback',current:'a',chosen:[]});
  S.taskNavigation.start();
  assert.ok(S.taskNavigation.current());
  S.taskNavigation.finish();
  assert.equal(S.taskNavigation.current(),null);
  assert.equal(S.taskNavigation.visible(false),false);
});
