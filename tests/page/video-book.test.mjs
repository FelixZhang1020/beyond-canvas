import test from 'node:test';
import assert from 'node:assert/strict';
import {loadStudio} from './load.mjs';

test('video pages loop automatically, do not restart on narration updates, and pause on page changes',()=>{
  const els=new Map();
  const el=id=>{
    if(!els.has(id)) els.set(id,{style:{},classList:{toggle(){}},firstChild:{},pause(){this.pauses=(this.pauses||0)+1;},load(){},play(){this.plays=(this.plays||0)+1;return Promise.resolve();},removeAttribute(){this.src='';}});
    return els.get(id);
  };
  const S=loadStudio({files:['src/28-book.js'],globals:{document:{getElementById:el}}});S.voice={speak(text,opts){opts.onstart?.();}};
  S.book.open('Book',{pages:[{drawing_id:'a',text:'A',video_url:'data:video/mp4;base64,AAAA'},{drawing_id:'b',text:'B'}]},[{id:'a',url:'a.png'},{id:'b',url:'b.png'}]);
  const v=el('page-video');assert.equal(v.plays,1);assert.equal(v.loop,true);assert.equal(v.muted,true);assert.equal(el('page-art').hidden,true);
  v.currentTime=3.375;v.ended=true;S.book.show();assert.equal(v.currentTime,3.375);assert.equal(v.plays,1);
  S.book.go(1);assert.equal(v.hidden,true);assert.equal(v.src,'');assert.equal(el('page-art').hidden,false);
  S.book.go(-1);assert.equal(v.plays,2);
});

test('a page about to be read fetches its clip once its voice is heard, or after three seconds',()=>{
  // The voice and the clip share one slow link from the Spark, and the voice used to wait behind the clip.
  const video={style:{},load(){},pause(){},play(){this.plays=(this.plays||0)+1;return Promise.resolve();},removeAttribute(){this.src='';}};
  const els=new Map([['page-video',video]]), el=id=>{if(!els.has(id))els.set(id,{style:{},classList:{toggle(){}},firstChild:{}});return els.get(id);};
  const timers=[], speaking=[];
  const S=loadStudio({files:['src/28-book.js'],globals:{document:{getElementById:el},setTimeout:(fn,ms)=>timers.push([fn,ms])}});
  S.voice={speak(text,opts){speaking.push(opts);},stop(){}};
  S.book.open('Book',{pages:[{drawing_id:'a',text:'A',video_url:'/clip-a'},{drawing_id:'b',text:'B',video_url:'/clip-b'}]},[{id:'a',url:'a.png'},{id:'b',url:'b.png'}]);
  assert.equal(video.src,'');assert.equal(video.poster,'a.png','the drawing shows meanwhile');
  speaking.at(-1).onstart();assert.equal(video.src,'/clip-a');assert.equal(video.plays,1);
  timers.at(-1)[0]();assert.equal(video.plays,1,'fetched once, whichever comes first');
  S.book.go(1);assert.equal(video.src,'');assert.equal(timers.at(-1)[1],3000);
  timers.at(-1)[0]();assert.equal(video.src,'/clip-b','a voice not heard in three seconds holds the clip no longer');
  S.book.read();S.book.go(-1);assert.equal(video.src,'/clip-a','a stopped book shows its clip at once');
});

test('a book closed before its voice is heard fetches no clip; Stop on the page shows it at once',()=>{
  // Code review: closing the book released the waiting clip onto the slow link.
  const video={style:{},load(){},pause(){},play(){return Promise.resolve();},removeAttribute(){this.src='';}};
  const els=new Map([['page-video',video]]), el=id=>{if(!els.has(id))els.set(id,{style:{},classList:{toggle(){}},firstChild:{}});return els.get(id);};
  const timers=new Map();let n=0;
  const S=loadStudio({files:['src/28-book.js'],globals:{document:{getElementById:el},
    setTimeout:fn=>{timers.set(++n,fn);return n;},clearTimeout:id=>timers.delete(id)}});
  S.voice={speak(text,opts){this.onstart=opts.onstart;},stop(){const go=this.onstart;this.onstart=null;go?.();}};
  const open=()=>S.book.open('Book',{pages:[{drawing_id:'a',text:'A',video_url:'/clip-a'}]},[{id:'a',url:'a.png'}]);
  open();S.book.stop();[...timers.values()].forEach(fn=>fn());
  assert.equal(video.src,'','nothing fetched for a book on its way out');
  open();S.book.read();assert.equal(video.src,'/clip-a');
});

test('export embeds autoplay looping video and keeps still pages as images',()=>{
  const S=loadStudio({files:['src/27d-keepsake.js']});
  const html=S.keepsake.bookHtml('Book',[{art:'data:video/mp4;base64,AAAA',video:true},{art:'data:image/png;base64,BBBB'}]);
  assert.match(html,/<video controls playsinline muted autoplay loop src="data:video\/mp4/);
  assert.match(html,/<img alt="" src="data:image\/png/);
});
