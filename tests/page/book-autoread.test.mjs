import test from 'node:test';
import assert from 'node:assert/strict';
import {loadStudio} from './load.mjs';

function setup(globals={}) {
  const els=new Map(), calls=[];
  const el=id=>{
    if(!els.has(id)) els.set(id,{style:{},classList:{toggle(){}},firstChild:{},pause(){},load(){},removeAttribute(){}});
    return els.get(id);
  };
  const S=loadStudio({files:['src/28-book.js'],globals:{document:{getElementById:el},...globals}});
  S.voice={stop(){calls.push('stop');},speak(text,options){calls.push({text,options,visible:!el('viewer-overlay').hidden});}};
  const open=text=>S.book.open('Book',{pages:[{text}]},[],{courseId:'saved',history:true,readOnly:true});
  return {S,calls,open,el};
}

test('opening reads the visible first page and stops before an unanswered ending',()=>{
  const {S,calls,open}=setup();open('First page');
  assert.equal(calls.length,2);assert.equal(calls[0],'stop');
  assert.equal(calls[1].text,'First page');assert.equal(calls[1].visible,true);
  assert.equal(calls[1].options.courseId,'saved');assert.equal(S.book.playing,true);
  calls[1].options.onend();assert.equal(S.book.playing,false);assert.equal(S.book.i,0);
});

test('manual turns read the new page, natural completion advances, and the final ending stops',()=>{
  const {S,calls}=setup();
  S.book.open('Book',{pages:[{text:'One'},{text:'Two'},{text:'Three'}],ending:'The end'},[]);
  const first=calls.at(-1).options.onend;
  S.book.go(1);assert.equal(S.book.i,1);assert.equal(calls.at(-1).text,'Two');
  first();assert.equal(S.book.i,1,'old completion cannot skip the new page');
  calls.at(-1).options.onend();assert.equal(S.book.i,2);assert.equal(calls.at(-1).text,'Three');
  calls.at(-1).options.onend();assert.equal(S.book.i,3);assert.equal(calls.at(-1).text,'The end');
  calls.at(-1).options.onend();assert.equal(S.book.i,3);assert.equal(S.book.playing,false);
});

test('each page is read in the voice of its drawing, and the ending in the voice of the page before it',()=>{
  // The child's own voice, copied from the first answer said out loud about the drawing; the studio
  // answers with its own storybook voice for a drawing no child talked about out loud (studio/voice/child_voice.py).
  const {S,calls}=setup();
  S.book.open('Book',{pages:[{drawing_id:'fish',text:'One'},{drawing_id:'tree',text:'Two'}],ending:'The end'},[]);
  assert.equal(calls.at(-1).options.voice,'child:fish');
  calls.at(-1).options.onend();assert.equal(calls.at(-1).text,'Two');assert.equal(calls.at(-1).options.voice,'child:tree');
  calls.at(-1).options.onend();assert.equal(calls.at(-1).text,'The end');assert.equal(calls.at(-1).options.voice,'child:tree');
});

test('errors, stop and active manual gestures never trigger automatic page changes',()=>{
  const {S,calls}=setup();
  S.book.open('Book',{pages:[{text:'One'},{text:'Two'}]},[]);
  calls.at(-1).options.onerror();assert.equal(S.book.i,0);assert.equal(S.book.playing,false);
  S.book.read();const stale=calls.at(-1).options.onend;
  S.book.stop();stale();assert.equal(S.book.i,0);
  S.book.read();S.bookTurn={active:{},update(){}};
  calls.at(-1).options.onend();assert.equal(S.book.i,0);
});

test('empty pages stay silent and old completion cannot interrupt a newly opened book',()=>{
  const {S,calls,open}=setup();open('');assert.deepEqual(calls,['stop']);
  open('Old');const oldDone=calls.at(-1).options.onend;
  open('New');oldDone();assert.equal(S.book.playing,true);
  S.book.go(1);assert.equal(S.book.playing,false);assert.equal(calls.at(-1),'stop');
  assert.equal(calls.filter(c=>typeof c==='object').length,2);
});

test('blocked prerecorded autoplay returns to the manual read state',async()=>{
  const {S,el}=setup({Audio:class {play(){return Promise.reject(new Error('NotAllowedError'));} pause(){}}});
  S.book.open('Book',{pages:[{text:'',audio_url:'saved.mp3'}]},[]);
  await Promise.resolve();
  assert.equal(S.book.playing,false);assert.equal(el('book-read').hidden,false);
});

test('reader mounts narration in its reserved slot and ignores navigation keys in form fields',()=>{
  const {S,open,el}=setup();let host,delta;
  S.voice.place=value=>{host=value;};open('First');
  assert.equal(host,el('book-voice-slot'));
  S.book.go=value=>{delta=value;};
  el('book').onkeydown({key:'ArrowRight',target:{closest:()=>true}});
  assert.equal(delta,undefined);
  el('book').onkeydown({key:'ArrowRight',target:{closest:()=>false},preventDefault(){}});
  assert.equal(delta,1);
});

test('review mounts the same reader in its panel and returns it to the overlay when leaving',()=>{
  const {S,el}=setup();
  const book=el('book');
  const overlayHost={appendChild(child){child.parentNode=this;}};
  const inlineHost={appendChild(child){child.parentNode=this;}};
  book.parentNode=overlayHost;
  S.book.open('Book',{pages:[{text:'第一页'}]},[],{courseId:'one',history:true,readOnly:true,inlineHost});
  assert.equal(book.parentNode,inlineHost);
  assert.equal(el('viewer-overlay').hidden,true);
  assert.equal(S.book.playing,true);
  S.book.closeInline();
  assert.equal(book.parentNode,overlayHost);
  assert.equal(book.hidden,true);
  assert.equal(S.book.playing,false);
});


test('storybook text always uses child A instead of a saved adult recording',()=>{
  const {S,calls}=setup({Audio:class {constructor(){throw new Error('Old recording must not play');}}});
  S.book.open('Book',{pages:[{text:'Story text',audio_url:'adult.mp3'}]},[]);
  assert.equal(calls.at(-1).text,'Story text');
  assert.equal(calls.at(-1).options.voice,'soft-child');
});

test('a teacher who stops the reading is not read to on the next page, until they ask again', () => {
  // Before the fix: after Stop, every page turn started reading aloud again.
  const {S, calls} = setup();
  S.book.open('Book', {pages: [{text: 'One'}, {text: 'Two'}, {text: 'Three'}]}, []);
  const spoken = () => calls.filter(c => typeof c === 'object').map(c => c.text);
  S.book.read(); assert.equal(S.book.playing, false, 'the read button stops it');
  S.book.go(1); assert.equal(S.book.i, 1); assert.deepEqual(spoken(), ['One'], 'the next page stays quiet');
  S.book.read(); assert.deepEqual(spoken(), ['One', 'Two'], 'asked again, it reads');
  calls.at(-1).options.onend(); assert.equal(S.book.i, 2); assert.deepEqual(spoken(), ['One', 'Two', 'Three'], 'and carries on');
});

test('the arrow keys keep turning pages: the page takes the keyboard back after a turn it made', () => {
  // Before the fix: the turn hid the page, the keyboard lost its place, and the second arrow did nothing.
  const {S, el} = setup(); let focused = 0; el('page-text').focus = () => { focused++; };
  S.book.open('Book', {pages: [{text: 'One'}, {text: 'Two'}, {text: 'Three'}]}, []);
  const right = {key: 'ArrowRight', target: {closest: () => false}, preventDefault() {}};
  el('book').onkeydown(right); assert.equal(S.book.i, 1); assert.equal(focused, 1);
  el('book').onkeydown(right); assert.equal(S.book.i, 2); assert.equal(focused, 2);
  S.book.go(-1); assert.equal(focused, 2, 'a turn by button leaves the keyboard where it is');
});

test('the child\'s ending stays on the book it was given to, and is named the ending once written', () => {
  // Before the fix: opened again, the book asked "and then?" once more, and a written ending still read "the story goes on".
  const {S, el} = setup(); const out = {pages: [{text: 'One'}], artifact_id: 'bk'};
  S.book.open('Book', out, [], {readOnly: false});
  S.book.go(1); assert.equal(el('book-page-label').textContent, '故事还在继续');
  assert.equal(S.book.answer('They shared the cheese.'), true);
  assert.equal(el('book-page-label').textContent, '故事的结尾');
  assert.equal(out.ending, 'They shared the cheese.', 'opened again from the same result, the book still has it');
});

test('the child\'s ending is read aloud once it is saved, unless the teacher stopped the reading', async () => {
  // Before the fix: the last words of the book went in without a sound.
  const save = async stopFirst => {
    const {S, calls, el} = setup(); el('ending').querySelector = () => ({disabled: false});
    S.portfolio = {saveEnding: async () => ({})};
    S.book.open('Book', {pages: [{text: 'One'}], artifact_id: 'bk'}, [], {readOnly: false});
    if (stopFirst) S.book.read();
    S.book.go(1); el('ending-text').value = 'They shared the cheese.';
    await S.book.saveEnding({preventDefault() {}}, () => {});
    assert.equal(el('ending-text').value, '');
    return calls.filter(c => typeof c === 'object').map(c => c.text);
  };
  assert.deepEqual(await save(false), ['One', 'They shared the cheese.']);
  assert.deepEqual(await save(true), ['One'], 'a stopped book stays quiet');
});

test('a recording of the ending stops when the book is closed or its page turned, and the chat\'s does not', () => {
  // Before the fix: the microphone stayed on under a closed book.
  const {S, el} = setup(); let released = 0, recording = false;
  S.microphones = {release() { released++; }};
  el('ending-listen').classList.contains = name => name === 'on' && recording;
  S.book.open('Book', {pages: [{text: 'One'}]}, [], {readOnly: false});
  S.book.go(1); assert.equal(released, 0, 'the ending was not recording, so the chat\'s microphone is left alone');
  recording = true; S.book.go(-1); assert.equal(released, 1, 'turned away mid-recording, the microphone is let go');
  recording = false; el('ending-listen').disabled = true;
  S.book.stop(); assert.equal(released, 2, 'closed while the microphone was still starting, or the words still coming');
});

test('a long passage steps its type down until all of it shows, and one that still cannot says there is more', () => {
  // Before the fix: the last line or two of pages 1, 3 and 4 was hidden with nothing to say it was there.
  const {S, el} = setup({getComputedStyle: () => ({fontSize: '23px'})});
  const box = el('page-text'), classes = new Set();
  box.classList = {toggle: (name, on) => { if (on) classes.add(name); else classes.delete(name); }};
  let natural = 448;   // the passage's height at 23px; a line holds fewer characters as the type grows
  Object.defineProperty(box, 'scrollHeight', {get: () => Math.round(natural * ((parseFloat(box.style.fontSize) || 23) / 23) ** 2)});
  box.clientHeight = 390; box.scrollTop = 0;
  S.book.open('Book', {pages: [{text: 'A passage a little too long for its page.'}, {text: 'A very long passage.'}]}, []);
  assert.equal(box.style.fontSize, '21px'); assert.equal(classes.has('more'), false, 'it fits, so nothing fades');
  natural = 1200; S.book.go(1);
  assert.equal(box.style.fontSize, '15px', 'never smaller than 15px');
  assert.equal(classes.has('more'), true, 'what is still below is shown to be there');
  box.scrollTop = box.scrollHeight - box.clientHeight; box.onscroll();
  assert.equal(classes.has('more'), false, 'read to the end, the fade goes');
});

test('a page with a clip shows its drawing until the clip can play', () => {
  // Before the fix: page 1 stayed blank while its clip loaded.
  const {S, el} = setup(); const video = el('page-video');
  video.play = () => Promise.resolve(); video.removeAttribute = name => { delete video[name]; };
  S.book.open('Book', {pages: [{drawing_id: 'a', text: 'One', video_url: 'clip.mp4'}, {drawing_id: 'b', text: 'Two'}]},
    [{id: 'a', url: '/a.png'}, {id: 'b', url: '/b.png'}]);
  assert.equal(video.poster, '/a.png');
  S.book.go(1); assert.equal(video.poster, undefined, 'a page without a clip leaves no poster behind');
});
