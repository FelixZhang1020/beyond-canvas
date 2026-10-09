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
  // Two exceptions, 2.5 and 6.6 KB: the tab icon, which Chrome on an iPhone or iPad fetches apart from the page and
  // refuses over the class's own certificate, and the home-screen icon, which the class door refuses to "Add to Home
  // Screen" for want of the password. As files of their own neither ever showed (logo.test.mjs).
  const icons = page.match(/<link rel="(?:icon|apple-touch-icon)" href="data:image\/png;base64,[^"]+"/g) || [];
  assert.ok(icons.length <= 2 && icons.every(tag => tag.length < 8000), 'more than the two small icons is inlined');
  const blob = icons.reduce((rest, tag) => rest.replace(tag, ''), page).match(/[A-Za-z0-9+/]{1000,}/);
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
  // Raised to 572,000 for iPhone and iPad (operator: "make system compatible with iPad and iPhone screen"; on
  // the iPhone the picture first and every control under it): a phone on its side written into all 41
  // breakpoints (~1 KB), the picture-first order for the room, the planner, Review and the book, and the pet
  // that leaves a button it would cover; comments already off the page (567,187 -> 571,855).
  // Raised to 573,500 after the same day's spoken-answer and logo commits took main to 572,108 with this line left at
  // 572,000, and for the iPhone's chat right under its drawing (operator: "the conversation are not linking with
  // image"): the picture box in the drawing's shape, the rail hidden, an add button by today's drawings (-> 572,863).
  // Raised to 574,000 for the iPhone's compact title rows and the picture that stays pinned while the chat scrolls
  // (operator: "compact titles in iPhone version and make image always stay in the middle when rolling") (-> 573,500).
  // Raised to 574,500 for the logo heading the home screen's title, because a phone's browser shows no tab icon
  // (operator: "i can't see the project logo in iPad and iPhone chrome browser"): one picture, two rules (-> 574,126).
  // Raised to 577,000 for the tab icon written into the page, which a phone's Chrome never fetched as a file
  // (operator: "in iPad & iPhone, there is still no browser tab logo"), 2.5 KB, and the slogan's row (-> 576,792).
  // Raised to 577,500 after main reached 576,960, for the pet that a touch screen no longer drags out of its place
  // (operator's iPad home page: "it shows bad"): 228 bytes (-> 577,188).
  // Raised to 584,500 for the home-screen icon written into the page, which "Add to Home Screen" fetched without the
  // class password and the door refused (operator: "icon shows in Safari but not show in Add to Home Screen") (-> 583,817).
  // Raised to 585,500 for the touch screens' one-row home header the operator chose ("Use A"): icon buttons for the
  // showcase and system management, a smaller pet, the phone's actions in one row (-> 584,899).
  // Raised to 586,500 for a chat that plays with no "正在准备声音…" before its first line or between lines (operator):
  // each next line, and the first when the chat opens, is fetched ahead and kept, 1.8 KB of code (584,344 -> 586,134).
  // Raised to 587,000 for the storybook's last page: its question always shown, no scrollbar or empty bar, Record
  // before the ending, the microphone let go with the page, the ending read back once given (586,200 -> 586,802).
  // Raised to 588,500 for a picked sample that stalls on the slow link: asked for again after eight seconds of
  // nothing, the note saying so, thumbnails still coming set aside for it, called off when the sheet is closed;
  // 1.5 KB of code (586,802 -> 588,314).
  // Raised to 590,000 for a 3D model sent at its own address and fetched by the same stall-proof download, after a
  // head stalled inside the "done" and a finished job was called a failure (operator: "fix the 3D download"): the
  // sample's download shared rather than copied, and the workbench and the review fetching the model before the one
  // on screen goes, so a failure ends in their retry (code review); 1.4 KB (588,314 -> 589,685).
  const bytes = Buffer.byteLength(page, 'utf8');
  assert.ok(bytes < 590_000,`the page is ${bytes} bytes; it was 482,392 when this was written`);
});
