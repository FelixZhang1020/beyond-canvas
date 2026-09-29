// The two entrance photographs used to travel inside the page as base64:
// 437 KB, 47% of the file, and base64 of a JPEG gzips to nothing.
// They are their own files now, which the browser can keep between visits.
import test from 'node:test';
import assert from 'node:assert';
import { readFileSync, statSync } from 'node:fs';

const page = readFileSync(new URL('../../studio/page/index.html', import.meta.url), 'utf8');

test('no picture is written into the page itself', () => {
  // Not a search for "data:image": two script lines hold that as a regex, to check
  // an image a model sent back. What must not be here is an embedded payload.
  assert.ok(!page.includes('src="data:'), 'a picture is still inlined in the page');
  const blob = page.match(/[A-Za-z0-9+/]{1000,}/);
  assert.equal(blob, null, `something ${blob?.[0].length} characters long is embedded in the page`);
});

test('both photographs are asked for by name, and both files are there', () => {
  // Named one by one: a sweep that passes over an empty set passes for the wrong reason.
  for (const name of ['colour-painting', 'sketch-study']) {
    const src = `src="assets/entrance/${name}.jpg"`;
    assert.equal(page.split(src).length - 1, 1, `${name} is not asked for exactly once`);
    const file = new URL(`../../studio/page/assets/entrance/${name}.jpg`, import.meta.url);
    assert.ok(statSync(file).size > 0, `${name}.jpg is missing`);
  }
});

test('the path stays relative, so it works wherever the page is mounted', () => {
  assert.ok(!page.includes('src="/assets/entrance/'), 'an absolute picture path would break under a prefix');
});

test('the page is small enough to arrive before a teacher gives up', () => {
  // 928,450 bytes while the photographs were inside it, which gzipped
  // to 464,758 because base64 does not compress. The ceiling is a ratchet, not
  // a target: it may fall, and a change that pushes it back up says why here.
  // Raised to 605,000 for the 3D tab's make buttons, viewer controls and first-build
  // progress (the page went 592,407 -> 601,570; about 3 KB of it gzipped).
  // Then raised to 607,000 for the storybook fixes (a reopened class opens on its saved book, stories
  // are written fresh, the reader's stop and arrow keys) and the sketch class's missing storybook tab: +3.2 KB,
  // with their comments already cut down (the page went 603,037 -> about 606,240).
  // Raised to 608,000 after that for fitting a long passage to its page and showing the drawing while its
  // clip loads: about 1.1 KB on a page main had taken to 606,539.
  // Raised to 608,500 for the figure card's picture of the toy: 453 bytes, comments cut (607,696 -> 608,149).
  // Then lowered to 560,000: comments stay in the source and leave the page (studio/page/lean.py), which
  // took it from about 608,100 to about 546,600 with no line of code changed.
  // Raised to 560,500 for reading each storybook page in the child's own voice: 464 bytes of code, its
  // comments moved off the code lines so they leave the page (559,754 -> 560,218).
  // Raised to 561,500 for delete and recording notes that say what the backups still hold (operator:
  // "fix the words"): 797 bytes of Chinese, which the page carries twice (560,218 -> 561,015).
  // Raised to 564,000 for a finished class's review (operator: "the module pages are not good"): the
  // whole chat with each speaker named, each drawing's clip and figure as slots, no empty storybook tab. 2,570 bytes
  // of code and CSS, comments already off the page (561,015 -> 563,585).
  // Raised to 567,000 next for two things. System management showing today's studio (main 0053058) took
  // the page to 565,907 with this line left at 564,000. A book page's voice before its clip, and saved clips at their
  // own address (operator: "voice loading and video loading are still slow"), add 865 bytes of code (-> 566,772).
  // Raised to 567,500 for a clip's description the check still refuses after three writings (operator: a press of
  // 重新生成描述 must end in something usable): confirm stays open and one note says so (566,861 -> 567,099).
  const bytes = Buffer.byteLength(page, 'utf8');
  assert.ok(bytes < 567_500,`the page is ${bytes} bytes; it was 482,392 when this was written`);
});
