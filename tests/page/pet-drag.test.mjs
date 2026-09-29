import test from 'node:test';
import assert from 'node:assert/strict';
import { loadStudio } from './load.mjs';

function setup(saved, key) {
  const values = new Map(saved ? [['beyond-canvas.pet-position-v1', JSON.stringify(saved)]] : []);
  const events = {}, windowEvents = {}, classes = new Set();
  const face = {
    offsetWidth: 56, offsetHeight: 56,
    classList: { add: name => classes.add(name), remove: name => classes.delete(name), contains: name => classes.has(name) },
    style: { left: '', top: '', removeProperty(name) { this[name] = ''; } },
    addEventListener(name, fn) { events[name] = fn; },
    setPointerCapture() {},
    getBoundingClientRect() { return { left: classes.has('floating') ? parseFloat(this.style.left) : 500,
      top: classes.has('floating') ? parseFloat(this.style.top) : 16 }; }
  };
  const S = loadStudio({ files: ['src/26a-pet-drag.js'], globals: {
    innerWidth: 800, innerHeight: 600,
    localStorage: { getItem: key => values.get(key) || null, setItem: (key, value) => values.set(key, value), removeItem: key => values.delete(key) },
    addEventListener(name, fn) { windowEvents[name] = fn; }
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
