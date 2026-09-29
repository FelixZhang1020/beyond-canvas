# Every page on an HD screen

Measured against the studio running on the Spark
(`https://{spark-address}:7100`), from the operator's own Chrome.

## How the numbers were taken

The page was opened with `?transport=mock`, which the page's own `chooseTransport()`
accepts, so every screen below was reached without a model call, without touching a
saved course and without disturbing the class service. Sizes other than the window's
own were measured by loading each page into a same-origin iframe of that size: an
iframe is a real CSS viewport, so media queries, `dvh` and percentage heights resolve
exactly as they would in a window of those dimensions, and no window resize is needed.

For each surface: the element that frames the content, whether the page runs past the
bottom of the viewport, and which controls sit outside it. A bounded list that scrolls
is not a fault; a primary action that starts off the screen is.

**The height that matters is not 1080.** A maximised Chrome window on this 1920×1080
display reported between **700 and 800 CSS pixels** of viewport height over the course
of the session, depending on whether the bookmarks bar was showing. Two pages had
layout gated behind `min-height: 760px` and so changed layout across that line on one
machine. Everything below is measured at 720 and again at 794.

## What was wrong, and what it is now

| Surface | Before | After |
|---|---|---|
| New-course entrance | panel needed 802px, was given 652; 写一句今天的课程说明 cut off | needs 639 at a 720px window, 695 at 794; nothing hidden at 700/720/794/940 |
| Animation planner (让画动起来) | panel ended 55px past the bottom; 生成描述 and 确认描述，生成动画 off screen at 720 | panel ends at 685 of 720; no control off screen |
| Storybook planner (做本故事书) | panel ended 124px past the bottom; 下一步，生成故事情节 off screen at 720 | panel ends at 685 of 720; scrolls inside itself, actions pinned to its bottom edge |
| Status board `/board` | content 1250px wide, page 1933px tall | 1600px wide, 4 card columns on a wide screen, 1648px tall |
| Showpiece `/showpiece/` | below `min-height:760px` it fell out of its one-screen layout into a 1383px column | one screen at 720; frame 1600 centred |
| Harness `/harness/` | 856px tall in a 720px window | one screen at 720; frame 1600 centred |
| Four-model comparison `/showcase/3d/` | content 1850px wide, 35px of gutter | 1600px wide |
| Course portfolio (home) | frame 1504 | frame 1600 |
| Classroom with a drawing | fits | fits, unchanged |
| Teacher review, conversation | fits at 720 | unchanged |
| Sketch light study (create) | 3D study and original 590px fixed, ending 156px below the screen; the companion started at y1088 of an 850px window, a screen and a half down | study and original size to the room left (370px at 850); companion beside them; nothing off screen; workspace scroll 1234px → 18 |
| Course review, all five tabs, zh and en | frame 1504 | frame 1600; no control off screen in either language |
| Dialogs: lesson, menu, end class, switch class, system management, sample library | fit | fit, and each now gets its real height budget |

Content widths across the system before this: **1250, 1320, 1504, 1720, 1850**. Now one
`--page-frame` of `min(1600px, calc(100% - 64px))`, declared in each of the four
stylesheets that are separate documents and share nothing (the classroom's tokens, the
showpiece's, the board's, the comparison page's).

## The entrance scrolled again on the operator's own screen

The table above was measured with no class in progress, and at 1920 wide. The operator's
screenshot the next day showed a scrollbar on the entrance: a class was waiting to be
continued, so the 74px 继续当前课堂 bar sat above the cards, and the window was about
1000×653. Neither condition had been measured. Re-measured on the standard studio, through
same-size iframes, with the bar shown and hidden:

| Window | Before, no bar | Before, with bar | After, no bar | After, with bar |
|---|---|---|---|---|
| 1000×653 | 39px hidden | 125px hidden | fits, pictures 88px | fits, pictures stepped aside |
| 1280×720 | fits | 69px hidden | fits, pictures 124px | fits, pictures stepped aside |
| 1366×768 | — | — | fits, pictures 172px | fits, pictures 86px |
| 1440×800 | fits | 48px hidden | fits, pictures 200px | fits, pictures 118px |
| 1920×795 | fits | — | fits, pictures 199px | fits, pictures 113px |
| 1920×940 | fits | — | fits, pictures 200px | fits, pictures 200px |
| 1920×1080 | — | — | fits, pictures 200px | fits, pictures 200px |

The two pixel-tuned tiers were replaced by one rule: the card pictures are the only part
that gives, they take the height left after the fixed parts (less the bar when it shows),
and below about 70px, where a strip stops reading as a picture, they are hidden and the
cards stay as words. The phone layout (under 761px wide) is untouched and still shows them.

### Then review found a third case, and the heights stopped being predicted

A code review of that fix found what the twelve-size matrix had not tried: on a window
just wider than a phone the card descriptions wrap to two lines, and at 768×800 the sheet
ran 7px over (11px with the bar). Twice now a predicted height had broken on a case nobody
measured, so the prediction was removed. The sheet is a column with a height limit, every
row keeps its own height, and the row of cards is the one that gives; within each card the
picture gives, from 200px down. The browser measures whatever wraps or appears.

Measured on the standard studio, with and without the bar: 761×650, 768×800, 800×700,
820×720, 1000×653, 1280×720, 1366×768, 1440×800, 1920×795, 1920×940 and 1920×1080 — nothing
hidden in any of them. At 768×800 the picture gives up exactly the 7px the wrapped text
took (200 → 193). The phone layout is untouched (390×844: one column, pictures 160px).

## Two causes worth keeping

**`max-height:100%` on an overlay panel does nothing useful.** `.overlay` is a grid whose
row is sized to its own content, so a percentage height against it is circular and the
browser settles it short — the entrance panel was handed 652px in a window that owed it
730. The budget is now `calc(100dvh - 2*var(--overlay-inset))`, derived from the same
place the safe space is set, and it applies to every `.sheet` and `.viewer` on the page.

**`100dvh` is the wrong measure inside a panel that does not start at the top of the
window.** `#creation-planner` lives in `#creation-workspace`, which is positioned 128px
down; its cap is a share of that parent, not of the viewport.

## The four the first pass could not reach

The operator opened the real page for these, so they were measured
against saved courses rather than the demo transport. Two turned out to be layout
faults, now fixed; one is a deployment fault; one is open.

- **The sketch workbench with a real 3D model** — measured on a saved Pixal3D study,
  and it was the worst surface in the system. Fixed, numbers in the table above.
- **Course review on a saved course** — measured on a nine-drawing course and on the
  English one, every tab. No stranded control in either language. The art collection
  scrolls, which is what a gallery of nine drawings should do.
- **English** — the entrance needs 703px against Chinese's 695 and fits at 700, 720 and
  850. Review reads wider but strands nothing.
- **The four-model comparison with models loaded** — see below; its models are not on
  the Spark at all.

## A deployment fault found while checking those: the 3D viewer was dead on the Spark

`studio/showcase_3d/assets/` is excluded from `sync.sh`, to keep 23 MB of texture PNGs
off a capped link. But that folder also holds **`assets/materials/scanned.js`**, which
`viewer.js` imports. On the Spark it answered 404, so the viewer's module never ran and
**every 3D surface showed an empty panel**: the classroom's light study and the
four-model comparison alike. The file is 5 KB and its textures load lazily, so it was
copied to the node by hand; the comparison page then drew its four cards and controls
correctly, and the classroom viewer began answering `scene-ready`.

Both remaining questions were answered the same day:

- ~~The comparison page's models are not on the node.~~ **Sent** by
  `deploy/spark/send-exhibit-assets.sh`: 31 MB of models, 23 MB of material textures and
  8.5 MB of source sketches, rate-capped, all 25 files verified byte-identical on both
  sides. The page now loads all four models on the 三几何体 sample, and three of four on
  石膏头像 — TripoSG is recorded `status: "blocked"` with no display file for the portrait
  and fruit samples in the 3D bake-off manifest, so there is nothing to send for
  it. `studio/showcase_3d/originals/` (411 MB) stays on the Mac; it backs only the
  download links.
- ~~The classroom study still paints nothing.~~ **Withdrawn the same day — this was the
  way it was being looked at, not a fault.** The viewer renders only while its page is
  visible: `requestRender()` will not schedule a frame when `document.hidden`, `render()`
  returns immediately if it is, and a `visibilitychange` handler resumes when the page
  comes back (`studio/showcase_3d/viewer.js:538,541,642`). Deliberate, and right on a
  shared GPU. Every measurement above was taken by driving a Chrome window that macOS
  reported as `is_off_space: true` — on another Space — so the page read
  `visibilityState: "hidden"` throughout and no frame was ever drawn. The evidence that
  settles it: the model's "正在读取模型" overlay is hidden, so the GLB loaded; the viewport
  is 602px and present; and `.viewport[data-orbit]`, which the render loop writes at the
  end of every pass, was never set. Nothing is wrong with the renderer. Faking
  `document.hidden` from the console does not test it either — the browser suspends
  `requestAnimationFrame` in a hidden tab whatever the page believes.

`sync.sh` still excludes the folder, so the next full send will drop `scanned.js` again.

## Checks

`sh deploy/spark/test-on-spark.sh` on the node. `tests/page/showpiece-harness.test.mjs`
pinned the `min-height: 760px` string and went red when the breakpoint moved; it now
reads the breakpoint out of the demo's own stylesheet and asserts the harness answers
the same one, which is the invariant it was there to protect. That red is this change's
proof the check can fail.
