import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {createContext, runInContext} from 'node:vm';

const source = readFileSync(new URL('../../studio/showpiece/page/floating-console.js', import.meta.url), 'utf8');

test('moving fixes the outer width while collapse and narrow screens remain bounded', () => {
  const panel = {style:{}}, host = {style:{right:'16px'}};
  const ctx = createContext({panel, host, $:() => panel, document:{documentElement:{clientWidth:1280}}, window:{innerHeight:720}});
  runInContext('let open = true, preferredSize = null;\n' + source.slice(source.indexOf('  function fitSize('), source.indexOf('  function saveSize(')), ctx);
  runInContext('applySize()', ctx);
  assert.equal(host.style.width, '520px');
  host.style.right = '748px';
  runInContext('applySize()', ctx);
  assert.equal(host.style.width, '520px', 'moving left must not invoke shrink-to-fit');
  runInContext('document.documentElement.clientWidth = 375; applySize()', ctx);
  assert.equal(host.style.width, '343px', 'screen width still limits the panel');
  runInContext('open = false; applySize()', ctx);
  assert.equal(host.style.width, '', 'collapsed launcher must not retain a full-width hit area');
});

test('dragging clears old selection and blocks new selection only during the gesture', () => {
  let cleared = 0, prevented = 0, handler;
  const classes = new Set();
  const ctx = createContext({document:{
    getSelection:() => ({removeAllRanges:() => cleared++}),
    documentElement:{classList:{add:c => classes.add(c), remove:c => classes.delete(c)}},
    addEventListener:(type, fn) => { if (type === 'selectstart') handler = fn; }
  }});
  runInContext('let drag = null, moving = null;\n' + source.slice(source.indexOf('  function startInteraction('), source.indexOf("  const grip = $('resize');")), ctx);
  const select = () => handler({preventDefault:() => prevented++});
  select(); assert.equal(prevented, 0);
  runInContext('moving = {}; startInteraction()', ctx);
  select(); assert.equal(cleared, 1); assert.equal(prevented, 1); assert.ok(classes.has('backstage-interacting'));
  runInContext('moving = null; stopInteraction()', ctx);
  select(); assert.equal(prevented, 1); assert.equal(classes.size, 0);
  runInContext('drag = {}; startInteraction()', ctx);
  select(); assert.equal(prevented, 2, 'resize gestures receive the same protection');
});

test('module context switches all supplied sections together and isolates offline data', () => {
  function element(tag) {
    return {tag, dataset:{}, children:[], textContent:'', classList:{add() {}},
      append(...children) { this.children.push(...children); },
      replaceChildren(...children) { this.children = children; },
      setAttribute() {}};
  }
  const ids = new Map();
  const $ = id => { if (!ids.has(id)) ids.set(id, element('div')); return ids.get(id); };
  const custom = {slot:'processes'}, clock = {slot:'clock'};
  const snapshot = {sources:['classroom'], parts:[{id:'tools', name:'Tools'}], jobs:[{
    id:'classroom:1', source:'classroom', skill:'art-feedback', status:'running',
    processes:[{name:'studio-safety',status:'gate_pass',seconds:.5,events:2}],
    events:[{stage:'studio-safety',status:'gate_pass'}]
  }]};
  const ctx = createContext({$, document:{createElement:element}, snapshot,
    words:(zh,en) => en, window:{Backstage:{}}, host:{querySelector:s => s.includes('clock') ? clock : null},
    pageModules:['processes','pipeline','log'], supplied:new Map([['processes',custom]])});
  runInContext("let selectedContext = 'page', pageContext = {label:'Recorded',status:'done'}, failed = false;\n" +
    source.slice(source.indexOf('  function node('), source.indexOf('  const number')) +
    source.slice(source.indexOf('  function table('), source.indexOf('  async function poll(')), ctx);
  runInContext('paintModules()', ctx);
  assert.equal($('processes-content').hidden, true);
  runInContext("selectedContext = 'classroom:1'; paintModules()", ctx);
  assert.equal(custom.slot, 'inactive', 'recorded content must disappear when inspecting a live classroom job');
  assert.equal(clock.slot, 'inactive', 'a recording clock cannot label a classroom job');
  assert.equal($('processes-content').hidden, false);
  const flatten = e => [e.textContent, ...e.children.map(flatten)].join(' ');
  assert.match(flatten($('processes-content')), /studio-safety.*gate_pass.*0.5s.*2/);
  assert.match(flatten($('parts-content')), /Not reported/);
  runInContext('failed = true; paintModules()', ctx);
  assert.equal($('context').value, 'classroom:1', 'disconnect must not silently switch to a recording');
  assert.doesNotMatch(flatten($('processes-content')), /studio-safety/, 'stale live rows must clear on disconnect');
  assert.match(flatten($('log-content')), /connection lost/);
  runInContext('failed = false; paintModules()', ctx);
  assert.match(flatten($('log-content')), /studio-safety/);
  runInContext("selectedContext = 'page'; pageContext = {label:'Harness',mode:'simulation',parts:{tools:'current'}}; paintModules()", ctx);
  assert.match(flatten($('parts-content')), /Simulation journey states.*Tools.*Current step/);
  runInContext("pageContext.parts.tools = 'visited'; paintModules()", ctx);
  assert.match(flatten($('parts-content')), /Tools.*Visited/);
  runInContext("selectedContext = 'classroom:1'; paintModules()", ctx);
  assert.doesNotMatch(flatten($('parts-content')), /Simulation journey|Current step|Visited/);
});


test('panel shortcuts leave Tab available to the containing dialog focus trap', () => {
  let handler, stopped = 0, closed = 0;
  const ctx = createContext({host:{addEventListener:(type, fn) => { handler = fn; }}, setOpen:() => closed++, $:() => ({focus(){}})});
  const start = source.indexOf("  host.addEventListener('keydown'");
  runInContext(source.slice(start, source.indexOf('\n', start)), ctx);
  handler({key:'Tab',stopPropagation:() => stopped++});
  assert.equal(stopped, 0);
  handler({key:' ',stopPropagation:() => stopped++});
  assert.equal(stopped, 1, 'Space inside a module must not trigger the Harness play shortcut');
  handler({key:'Escape',stopPropagation:() => stopped++});
  assert.equal(closed, 1);
});

test("the machine's own media services are named, whichever class started their work", () => {
  // Before the fix: a clip rendered for ten minutes while the panel showed nothing running, because
  // the class that asked for it had ended and the panel only ever knew that class's requests.
  const ctx = createContext({words: (zh, en) => en});
  runInContext(source.slice(source.indexOf('  function spell('), source.indexOf('  // The Spark\'s terminal monitor')), ctx);
  const line = service => runInContext(`serviceLine(${JSON.stringify(service)})`, ctx);
  assert.equal(
    line({slots:['video.animation'], answering:true, busy:true, phase:'running', model:'wan2.2-i2v-a14b'}),
    'video.animation · wan2.2-i2v-a14b · running');
  assert.equal(
    line({slots:['mesh.portrait'], answering:true, busy:false, phase:'standby', model:'trellis2'}),
    'mesh.portrait · trellis2 · standby', 'how long the last job took comes from the chip list, not from here');
  assert.equal(
    line({slots:['image.edit'], answering:false, busy:null, phase:null, model:null}),
    'image.edit · not answering', 'a service that is down must say so, not disappear');
});

test('the chip list says what the Spark monitor says: a cancelled job is cancelled, not the last one that finished', () => {
  // Before the fix: the panel said "standby · last took 11m 17s" while the monitor showed the latest
  // clip cancelled after 17 min 41 s. Both now read deploy/spark/dashboard_jobs.py.
  const ctx = createContext({words: (zh, en) => en});
  runInContext(source.slice(source.indexOf('  function spell('), source.indexOf('  function paintChip(')), ctx);
  const at = 1790307060;
  assert.equal(runInContext(`chipNowLine(${JSON.stringify({group:'class', what:'Video clip (Wan)', started:at, started_clock:'11:31', running_s:243,
    usual_s:671, reported_s_ago:null, held_gb:72.4, stuck:false})})`, ctx),
    'class · Video clip (Wan)\n   started 11:31, running 4m 3s · usually 11m 11s, about 7m 8s left · holding 72 G');
  assert.equal(runInContext(`chipNowLine(${JSON.stringify({group:'service', what:'Safety checker', started:at, started_clock:'11:31', running_s:188,
    usual_s:null, reported_s_ago:null, held_gb:9, stuck:false})})`, ctx),
    'service · Safety checker\n   started 11:31, up 3m 8s · holding 9 G', 'a service waits for work: no time left, no report age');
  assert.match(runInContext(`chipNowLine(${JSON.stringify({group:'test', what:'Blender', started:null, started_clock:null, running_s:700,
    usual_s:null, reported_s_ago:null, held_gb:0, stuck:true})})`, ctx), /has reported nothing yet · looks stuck/);
  assert.equal(runInContext(`chipFinishedLine(${JSON.stringify({at, clock:'11:31', group:'class', what:'Video clip (Wan)', outcome:'cancelled', seconds:1061})})`, ctx),
    '11:31 · class · Video clip (Wan) · was cancelled after 17m 41s');
  assert.equal(runInContext(`chipFinishedLine(${JSON.stringify({at, clock:'11:31', group:'class', what:'3D model', outcome:'refused', seconds:0.4})})`, ctx),
    '11:31 · class · 3D model · turned away, the service was busy');
  assert.deepEqual([...runInContext(`chipTodayLines(${JSON.stringify({jobs:[{what:'Video clip (Wan)', done:1, refused:0, cancelled:1, failed:0}],
    tests:{finished:116, stopped:2, error:0}})})`, ctx)],
    ['Video clip (Wan) · 1 done · 0 turned away · 1 cancelled · 0 did not finish', 'Tests and checks · 116 finished · including 2 stopped']);
  assert.deepEqual([...runInContext(`chipTodayLines(${JSON.stringify({jobs:[], tests:{finished:116, stopped:0, error:3}})})`, ctx)],
    ['Tests and checks · 116 finished · including 3 with an error'], 'as the terminal says it');
  assert.equal(runInContext('spell(179.6)', ctx), '3m 0s', 'rounded before splitting, never "2m 60s"');
});

test('the closed toggle drags anywhere, while a tap that barely moves still opens it', () => {
  const handle = {classList:new Set(), captured:new Set()};
  handle.classList.remove = handle.classList.delete;
  handle.setPointerCapture = id => handle.captured.add(id);
  handle.hasPointerCapture = id => handle.captured.has(id);
  handle.releasePointerCapture = id => handle.captured.delete(id);
  let clock = 0, saved = 0, started = 0;
  const ctx = createContext({handle, host:{getBoundingClientRect:() => ({right:1264, bottom:704, width:160, height:44})},
    document:{documentElement:{clientWidth:1280}}, window:{innerHeight:720}, performance:{now:() => clock}, Math,
    applyPosition:() => {}, savePosition:() => saved++, startInteraction:() => started++, stopInteraction:() => {}});
  const body = source.slice(source.indexOf('  let tapBlockedUntil'), source.indexOf('  movable(titlebar, false);'));
  runInContext('let preferredPosition = null, moving = null;\n' + body + '\nmovable(handle, true);', ctx);
  const at = (x, y) => ({button:0, isPrimary:true, pointerId:1, clientX:x, clientY:y, target:{closest:() => handle}, preventDefault() {}});
  handle.onpointerdown(at(1200, 690)); handle.onpointermove(at(1203, 688)); handle.onpointerup(at(1203, 688));
  assert.equal(runInContext('preferredPosition', ctx), null, 'a wobble of a few pixels is a tap, not a move');
  assert.equal(started, 0);
  assert.ok(clock >= runInContext('tapBlockedUntil', ctx), 'the tap still opens the console');
  handle.onpointerdown(at(1200, 690)); handle.onpointermove(at(600, 300)); handle.onpointerup(at(600, 300));
  assert.deepEqual({...runInContext('preferredPosition', ctx)}, {right:616, bottom:406});
  assert.equal(saved, 1, 'the new place is remembered');
  assert.ok(clock < runInContext('tapBlockedUntil', ctx), 'the click that ends a drag does not open the panel');
  assert.equal(handle.captured.size, 0);
});

test('a closed console asks the studio every 15 s, an open one every 2 s', async () => {
  let asked = 0, now = 0;
  const ctx = createContext({document:{hidden:false}, Date:{now:() => now}, AbortSignal:{timeout:() => null},
    fetch: async () => { asked++; return {ok:true, json: async () => ({jobs:[]})}; },
    setTimeout:() => 0, paint:() => {}});
  runInContext('let open = false, snapshot = null, failed = false, updated = null, timer, suspended = true, lastAsked = 0;\n'
    + source.slice(source.indexOf('  async function poll('), source.indexOf("  $('context').onchange")), ctx);
  now = 20000; await runInContext('poll()', ctx); assert.equal(asked, 1);
  now = 22000; await runInContext('poll()', ctx); assert.equal(asked, 1, 'closed: no ask 2 s later');
  now = 35000; await runInContext('poll()', ctx); assert.equal(asked, 2, 'closed: asks again after 15 s');
  runInContext('open = true', ctx);
  now = 37000; await runInContext('poll()', ctx); assert.equal(asked, 3, 'open: asks every time');
});
