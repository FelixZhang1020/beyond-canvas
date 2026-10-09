// The review screen was once designed as a bare desk and switched the drawing tools off.
// A teacher reading one review still reaches for the next drawing, so the tools stay — and
// because the rail sits in the far-left column, the framed artwork has to begin clear of it.
import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';

const layout = readFileSync('studio/page/src/03-layout.css', 'utf8');

// One rule that names both the review screen and the rail, and switches it off. The search
// crosses newlines, because a selector list is often broken over several, but never a brace,
// so it cannot wander from one rule into the next.
function hidesTheRail(css) {
  const found = css.match(/\[data-mode="teacher"\][^{}]*\.rail[^{}]*\{[^}]*display:\s*none/);
  return found && found[0];
}

// Everything between a breakpoint and the next one, so a width-specific number is read from
// the band it actually applies to rather than from the first match anywhere in the file.
function band(query) {
  const start = layout.indexOf(query);
  assert.notEqual(start, -1, `${query} is no longer a breakpoint in the stylesheet`);
  const next = layout.indexOf('@media', start + query.length);
  return layout.slice(start, next === -1 ? undefined : next);
}

function number(text, pattern, what) {
  const found = text.match(pattern);
  assert.ok(found, `could not read ${what} from the stylesheet`);
  return Number(found[1]);
}

// A check that has never gone red on a known-bad case cannot be told apart from one that
// cannot go red at all, so the two shapes it has to catch are put to it on every run.
test('the check goes red on a stylesheet that hides the rail', () => {
  assert.ok(hidesTheRail('.studio[data-mode="teacher"][data-has-drawing="true"] .rail{display:none}'),
    'the exact rule this change removed slips past the check');
  assert.ok(hidesTheRail('.studio[data-mode="teacher"] .rail,\n.studio[data-mode="teacher"] #buddy{display:none}'),
    'a rail hidden through a multi-line selector list slips past the check');
  assert.equal(hidesTheRail('.rail{display:flex}\n.studio[data-mode="teacher"] #buddy{display:none}'), null,
    'the check fires on a stylesheet that hides no rail');
});

test('the review screen keeps the drawing tools', () => {
  assert.equal(hidesTheRail(layout), null, 'the review screen hides the tool rail again');
});

// Every tab shares one frame now, so the picture card's left edge is the frame's.
test('the framed artwork on the review screen begins clear of the tool rail', () => {
  const rooms = [...layout.matchAll(/#app\{--frame-left:(\d+)px/g)].map((m) => Number(m[1]));
  assert.equal(rooms.length, 2, 'expected a left edge for the wide band and for the mid band');
  assert.match(layout, /#creation-workspace \.room\{left:var\(--frame-left\);/,
    'the picture card no longer takes its left edge from the frame');
  const [roomWide, roomMid] = rooms;

  const railWide = number(layout, /\.rail\{position:absolute;[^}]*width:(\d+)px/, 'the rail width');
  const gutterWide = number(layout, /\.studio\{position:fixed;[^}]*--gutter:(\d+)px/, 'the page gutter');
  const mid = band('@media(max-width:1100px) and (--side-by-side)');
  const railMid = number(mid, /\.rail\{width:(\d+)px\}/, 'the rail width at mid widths');
  const gutterMid = number(mid, /--gutter:(\d+)px/, 'the page gutter at mid widths');

  assert.ok(roomWide >= gutterWide + railWide,
    `the artwork starts at ${roomWide}px, under a rail that ends at ${gutterWide + railWide}px`);
  assert.ok(roomMid >= gutterMid + railMid,
    `at mid widths the artwork starts at ${roomMid}px, under a rail that ends at ${gutterMid + railMid}px`);
});
