import test from 'node:test';
import assert from 'node:assert/strict';
import {loadStudio} from './load.mjs';

function setup(reduced=false) {
  class Element {
    style={};dataset={};children=[];events={};paused=false;hidden=false;
    classList={add(){},remove(){}};
    append(...els){this.children.push(...els);} appendChild(el){this.append(el);}
    setAttribute(){} getBoundingClientRect(){return {width:500};}
    addEventListener(name,fn){this.events[name]=fn;}
    setPointerCapture(id){this.capture=id;}hasPointerCapture(id){return this.capture===id;}
    releasePointerCapture(){this.capture=null;}remove(){this.removed=true;}
    pause(){this.paused=true;}play(){this.paused=false;return Promise.resolve();}
  }
  const elements=new Map(), el=id=>{if(!elements.has(id))elements.set(id,new Element());return elements.get(id);};
  const timers=new Map();let timer=0;
  const S=loadStudio({files:['src/28b-book-turn.js'],globals:{document:{getElementById:el,createElement:()=>new Element()},
    matchMedia:()=>({matches:reduced}),setTimeout:fn=>{timers.set(++timer,fn);return timer;},clearTimeout:id=>timers.delete(id)}});
  const turns=[];
  S.book={i:0,pages:[{url:'a.png',text:'A'},{url:'b.png',text:'B'},{text:'Ending'}],goTo(delta){this.i+=delta;turns.push(delta);S.bookTurn.update();}};
  S.bookTurn.update();
  const event=(x)=>({button:0,pointerId:1,clientX:x,preventDefault(){}});
  return {S,el,turns,event,flush(){for(const [id,fn] of timers){timers.delete(id);fn();}}};
}

test('button turns commit once after animation; first and last page bounds hold',()=>{
  const {S,turns,flush,el}=setup();
  S.bookTurn.turn(-1);assert.equal(S.bookTurn.active,null);assert.equal(el('book-corner-prev').disabled,true);
  S.bookTurn.turn(1);S.bookTurn.turn(1);assert.equal(turns.length,0);
  flush();assert.deepEqual(turns,[1]);assert.equal(S.bookTurn.active,null);
  S.bookTurn.turn(1);flush();assert.equal(el('book-corner-next').disabled,true);
  S.bookTurn.turn(1);flush();assert.equal(turns.length,2);
});

test('drag follows the pointer, short drags spring back, long drags turn',()=>{
  const {S,el,event,flush,turns}=setup(),corner=el('book-corner-next');
  corner.events.pointerdown(event(500));corner.events.pointermove(event(450));
  assert.equal(S.bookTurn.active.progress,.1);
  corner.events.pointerup(event(450));flush();assert.equal(turns.length,0);
  assert.equal(el('page-video').paused,false);
  corner.events.pointerdown(event(500));corner.events.pointermove(event(300));
  assert.equal(S.bookTurn.active.progress,.4);
  corner.events.pointerup(event(300));flush();assert.deepEqual(turns,[1]);
});

test('closing or cancelling a pending turn prevents a late page change',()=>{
  const {S,turns,flush}=setup();S.bookTurn.turn(1);
  const paper=S.bookTurn.active.paper;S.bookTurn.cancel();flush();
  assert.equal(paper.removed,true);assert.equal(turns.length,0);assert.equal(S.bookTurn.active,null);
});

test('reduced-motion preference uses immediate manual turns without animated layers',()=>{
  const {S,turns}=setup(true);S.bookTurn.turn(1);assert.deepEqual(turns,[1]);assert.equal(S.bookTurn.active,null);
});

test('static and animated turning faces use the same visual and copy columns',()=>{
  const {S}=setup();
  const still=S.bookTurn.face({url:'drawing.png',text:'Story'},0);
  const animated=S.bookTurn.face({url:'drawing.png',video_url:'saved.mp4',text:'Story'},0);
  for(const face of [still,animated]) {
    assert.equal(face.children[0].className,'book-visual');
    assert.equal(face.children[1].className,'book-copy');
    assert.equal(face.children[1].children[1].textContent,'Story');
    assert.equal(face.style.gridTemplateColumns,undefined);
  }
});
