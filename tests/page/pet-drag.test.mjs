import test from 'node:test';
import assert from 'node:assert/strict';
import { loadStudio } from './load.mjs';

function setup(saved, key, page = {}) {
  const values = new Map(saved ? [['beyond-canvas.pet-position-v1', JSON.stringify(saved)]] : []);
  const events = {}, windowEvents = {}, classes = new Set();
  const face = {
    offsetWidth: 56, offsetHeight: 56,
    classList: { add: name => classes.add(name), remove: name => classes.delete(name), contains: name => classes.has(name) },
    style: { left: '', top: '', removeProperty(name) { this[name] = ''; } },
    addEventListener(name, fn) { events[name] = fn; },
    contains() { return false; },
    setPointerCapture() {},
    getBoundingClientRect() { return { left: classes.has('floating') ? parseFloat(this.style.left) : 500,
      top: classes.has('floating') ? parseFloat(this.style.top) : 16, width: 56, height: 56 }; }
  };
  const S = loadStudio({ files: ['src/26a-pet-drag.js'], globals: {
    innerWidth: 800, innerHeight: 600,
    localStorage: { getItem: key => values.get(key) || null, setItem: (key, value) => values.set(key, value), removeItem: key => values.delete(key) },
    addEventListener(name, fn) { windowEvents[name] = fn; },
    ...page
  } });
  S.pet.init(face, key);
  return { face, events, windowEvents, values, classes };
}

test('the companion moves freely, stays on screen, remembers its position and can return home', () => {
  const { face, events, values, classes } = setup();
  const pointer = (x, y) => ({ pointerId: 4, isPrimary: true, button: 0, clientX: x, clientY: y, preventDefault() {} });
  events.pointerdown(pointer(510, 26));
  events.pointermove(pointer(210, 160));
  assert.equal(face.style.left, '200px'); assert.equal(face.style.top, '150px');
  events.pointermove(pointer(910, 710));
  assert.equal(face.style.left, '732px'); assert.equal(face.style.top, '532px');
  events.pointerup(pointer(910, 710));
  assert.deepEqual(JSON.parse(values.get('beyond-canvas.pet-position-v1')), { x: 732, y: 532 });
  events.dblclick();
  assert.equal(classes.has('floating'), false);
  assert.equal(values.has('beyond-canvas.pet-position-v1'), false);
});

test('saved positions are clamped on restore and keyboard movement is available', () => {
  const { face, events, windowEvents, values } = setup({ x: 5000, y: -100 });
  assert.equal(face.style.left, '732px'); assert.equal(face.style.top, '12px');
  events.keydown({ key: 'ArrowLeft', shiftKey: true, preventDefault() {} });
  assert.equal(face.style.left, '700px');
  windowEvents.resize();
  assert.deepEqual(JSON.parse(values.get('beyond-canvas.pet-position-v1')), { x: 700, y: 12 });
  events.keydown({ key: 'Home', preventDefault() {} });
  assert.equal(face.style.left, '');
});

test('a pet that would rest on a button goes home, and one resting on the page stays', () => {
  const button = { closest: selector => (selector.includes('button') ? button : null) };
  const paper = { closest: () => null };
  let under = paper;
  const { values, windowEvents, classes } = setup({ x: 600, y: 20 }, undefined, { document: { elementsFromPoint: () => [under] } });
  windowEvents.resize();
  assert.equal(classes.has('floating'), true, 'over plain page the remembered spot is kept');
  assert.ok(values.has('beyond-canvas.pet-position-v1'));
  under = button;   // the screen turned, and the same spot is now a button
  windowEvents.resize();
  assert.equal(classes.has('floating'), false, 'the pet went home instead of covering the button');
  assert.equal(values.has('beyond-canvas.pet-position-v1'), false, 'and the spot that covered it is forgotten');
});

test('on a touch screen the pet is not dragged: it keeps its place and forgets a remembered spot', () => {
  const touch = { matchMedia: query => ({ matches: query.includes('pointer: coarse') }) };
  const { face, events, values, classes } = setup({ x: 31, y: 124 }, undefined, touch);
  assert.equal(classes.has('floating'), false, 'a spot a swipe left behind is not restored');
  assert.equal(values.has('beyond-canvas.pet-position-v1'), false, 'and it is forgotten');
  assert.equal(events.pointerdown, undefined, 'no drag is listened for, so a swipe scrolls the page');
  assert.equal(face.style.touchAction, 'manipulation');
});

test('the home buddy keeps its own place, and letting go after a drag is not a poke', () => {
  const { events, values } = setup(null, 'beyond-canvas.home-pet-position-v1');
  const pointer = (x, y, type) => ({ type, pointerId: 7, isPrimary: true, button: 0, clientX: x, clientY: y });
  const click = () => { let stopped = false; events.click({ stopImmediatePropagation() { stopped = true; } }); return stopped; };
  events.pointerdown(pointer(510, 26));
  events.pointermove(pointer(310, 226));
  events.pointerup(pointer(310, 226, 'pointerup'));
  assert.deepEqual(JSON.parse(values.get('beyond-canvas.home-pet-position-v1')), { x: 300, y: 216 });
  assert.equal(values.has('beyond-canvas.pet-position-v1'), false);
  assert.equal(click(), true, 'the click that ends a drag is swallowed');
  assert.equal(click(), false, 'only that one');
  events.pointerdown(pointer(310, 226));
  events.pointerup(pointer(310, 226, 'pointerup'));
  assert.equal(click(), false, 'a tap without moving still pokes');
  events.pointerdown(pointer(310, 226));
  events.pointermove(pointer(110, 426));
  events.pointercancel(pointer(110, 426, 'pointercancel'));
  assert.equal(click(), false, 'a cancelled drag is followed by no click, so a later Enter still pokes');
});
