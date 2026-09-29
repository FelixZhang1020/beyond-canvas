# Beyond Canvas design principles

The standing design rules for the children's art studio built for the DGX Spark hackathon.
This file is the canonical spec. The user selected direction A, **通透画室**,
from the design alternatives drawn for the studio. The current implementation is `studio/page/`; the older
`beyond-canvas-lookbook.html` preserves the original material exploration.

## Selected direction A

**Unified storybook reader:** static and animated books use one paper spread and the same
visual/copy columns. Media type never chooses a different layout. Keep title/export/close
above the spread, page count/read/previous/next below it, with a reserved narration-status
row. Desktop uses left artwork/right text; narrow screens use top artwork/bottom text.
Long text scrolls within its page; core controls stay in view. Animation has its own small
play/pause control, separate from narration. Page-turn faces reuse the reading layout and
freeze the current video frame. Keep manual corners, keyboard navigation and reduced-motion
support, with a dedicated text-only ending page. Do not rewrite the story or its original art.
As requested, opening and manual turns start narration; successful playback
completion turns to the next written page and reads it. Stop at the final page or unanswered
ending. Stopping, unavailable audio and playback failures never advance the book. Keep a soft,
directional paper transition without a blank back-face flash; reduced motion skips animation.

**Course-wide visual consistency:** Create, Review and the course shelf share warm ink,
paper surfaces and the existing rounded segmented-control treatment. Use one selected-state
treatment (paper pill, subtle shadow, stronger ink), not separate underline and outlined-tab
systems. Original-gallery and comparison cards use the same border and radius as course cards;
artwork keeps its aspect ratio on an uncoloured surface. Body copy follows the companion's
15px / 1.85 rhythm. Keep disabled states, keyboard focus and 44px minimum navigation targets.

**Course navigation refinement:** the original course space used **Create / Review**
views and a shared course title, status and All courses action. Open courses defaulted to Create;
completed courses defaulted to read-only Review and required explicit reopening. Preserve drawing
selection and the current activity when returning to a live editor. Review results belong
to the selected drawing; multi-drawing storybooks have their own course-level section. Review is
a page view, not a modal, so course navigation remains keyboard-accessible. Earlier separate
profile / Edit course navigation below describes the preceding design. The course phases rule
below supersedes the Create / Review switch.

**Review content correction:** preserve the original three-layer meaning in
[the product design](../specs/art-studio-skill-pack-design.md):
expression and feedback, transformation, then storytelling. Painting and sketch are entrances
within the first two layers, not successive stages. Use the established experience labels
“聊聊你的画”, “让画动起来” / “形体与光影”, and “今天的故事书”; the newly added original
gallery is “画作集”. ~~The first view pairs the original with the latest confirmed words and
feedback, not the whole chat log.~~ **Superseded** (operator, reviewing the ended
showcase classes: "the module pages are not good"): the first view shows the whole conversation,
both voices in order, in the chat panel's bubbles. The transformation view pairs the original with saved
image/video or 3D output: the drawings row lists each drawing once, the work card offers its clip and
figure as result slots and says what the chosen one shows (the clip's movement), never the child's words
again. A class with no book, and every sketch class, shows no storybook tab. The art collection shows
small pictures and links the full drawing. Storybooks stand alone. Never regenerate on review; stop playback
and dispose the comparison viewer when leaving its section.

Creation activity labels are “聊聊你的画”, “让画动起来”, and “做本故事书”,
as explicitly refined by the user; the sketch entrance retains “形体与光影”.

**Creation confirmation:** use the user-approved
[content-first creation flow](../specs/creation-flow.md). Automatically draft editable scene
descriptions from the earlier dialogue; create animation only after confirmation. For books,
choose and order drawings, draft editable story passages from their scenes (supply missing
scenes automatically), then create the book after confirmation. Reader-only preservation
above still applies to completed books; it does not prohibit editing during creation.

**Course portfolio addition:** the user requested a persistent course-level
portfolio above the existing class entrance. Home now opens the course shelf; a course
profile shows its originals, confirmed words, responses and saved creations. Use the same
warm paper and ink, quiet rectangular artwork cards, readable dates and teacher-sized
controls. Starting a new class retains the manual colour/sketch choice. Ending saves the
course locally and releases its working session; earlier "forget everything" navigation
copy is superseded. There is no child identity or cross-course child profile. Implementation
and verification are in [the portfolio record](../measured/course-portfolio.md).

**Visual alignment:** the user found the Portfolio inconsistent with the studio.
Reuse the studio's Splat brand, paper background, heading scale, primary buttons and entrance
card material. The portfolio's filter bar and saved conversation panel use the same quiet
glass as the classroom tools and companion; artwork stays separate, with no glass stacking.
The brand's home action explicitly names the course portfolio so the entry is discoverable.

**Explicit completion:** a standalone **Mark class ended** action in both classroom
and profile makes a course read-only. Viewing never reopens it. The profile offers **Reopen course**
to resume editing and add artwork to that same course; open courses offer **Edit course**.
Refreshing, leaving or switching courses must not mark them ended automatically. Completed
profiles hide content-editing controls, while saved artwork and result viewers remain available.

**HD screen standard:** every page must look good on an HD screen — a 1920×1080
display, which leaves a browser page of about 1920×800–950. It is judged from a screenshot, by
eye, not from measurements alone: two rounds of fixes reported every number
in range while the operator's screen still looked broken.

- Nothing is cut off, covered or overlapping: no text, picture, list row or button sits under
  another element or past an edge of the screen or of its panel.
- The main action of a screen is visible without scrolling. Content that is genuinely long (a
  course shelf, a sample library, a status list) scrolls the page or its own list; a panel never
  scrolls inside itself with its buttons pinned over the content.
- Use the width. A panel fills the space between the tools and Splat (or the 1600px page frame);
  a screen is never left half empty.
- The child's drawing or its 3D study is the largest thing on its screen. When height runs short,
  the pictures shrink first and decorative lines (an eyebrow, a subtitle) step aside next —
  never the controls.
- Check at 1920×795, 1920×851 and 1920×940, with and without a class waiting to be continued.
  Phones keep their stacked layout.

**One layout:** every tab and every step of a course is the same frame, in Create
and in Review (operator: "a consistent experience through all pages rather than diff pages in
diff steps"; the approved samples are the "One Layout Samples" canvas). From a laptop up:

- The course header and tabs, centred on the window, never move.
- The **picture card** on the left holds the drawing, or what stands for it on that step (the
  sketch's 3D study, the storybook's picks). Today's drawings sit in one row directly under it.
- The **work card** on the right holds the tab's own content: the teacher's review, the chat, the
  clip or story planner, the saved result in Review. Its heading is at the top, its main button
  at the foot, and only its middle scrolls when a list is genuinely long.
- In **让画动起来**, show the video and 3D figure as separate result slots at the top of the work
  card. Opening either editor leaves both slots visible; each finished result has its own viewer
  action, and making one never removes the other. The figure slot follows service availability,
  but a saved figure remains viewable if generation is no longer offered.
- Both cards keep their place and size across tabs, steps, choices (生成视频 ↔ 做立体小雕塑) and
  the transition to Review after class completion; only what is inside them changes. Screens with
  no single drawing (the storybooks and the art collection in Review) use both cards' room as one.
- One colour for a main action everywhere: accessible coral. Violet is kept for secondary
  generative extras, never for the button a screen is for.
- The frame is defined once, in `studio/page/src/03-layout.css`; every card places itself from it.

**Sketch viewer selection:** “形体与光影” keeps the original drawing and the 3D
study equally wide. Every saved drawing uses the same compact control layout in the right card:
one standalone **重新生成** button by the title; orbit, move light, restore/keep the comparison
angle and auto rotate; direction and elevation sliders; all eleven GLB surface and structure
choices visible together; grayscale and ground/shadow switches. Older analytic results show the
same options but disable scanned surfaces they cannot render. The result never exposes a
version/model menu. Older analytic studies cannot show a triangle mesh they do not contain,
so the wire option remains in place but disabled for those results.

**Course phases:** an unfinished course shows only Create; a completed course shows
only Review. Remove the Create / Review switch and the course-list header from the review page.
The prominent **完成课程（下课）** action confirms completion, then opens Review directly; **重新打开课程**
explicitly returns a completed course to Create. While either phase loads, show a neutral status
without displaying the other phase. If opening an editor fails, return to a retryable course list.
Course cards and the workspace header label the saved phase only: **未下课** until `ended_at` is set,
then **已下课**. An active editor does not change that label. Keep the completion confirmation visible
until the save succeeds; if it fails, explain that the course is still open and allow a retry.
The class-type dropdown is absent from the workspace header. The teacher still chooses the type
when starting a class; lesson settings, course completion and the run log retain their own entries.

**Creation header:** the user selected the single-row header from the navigation layout samples.
Put the four creation
activities in the course header. Place the same round, two-eyed mascot as the course home
immediately to their right by default. It may be dragged anywhere in the visible window;
remember its position in this browser, keep it on screen
after resizing, and allow a double-click to return it to the header. Keep the drawing and work
cards directly below the header. On narrow screens the same header may use two rows so the
activity targets remain readable. Likewise, Review's five tabs take the same place in the
course header, so a finished course's cards also start directly below it.

**Plain chat:** the user chose a plain chat for 聊聊你的画 ("too complex, that's why
we can never fix it... make it like a real chat conversation panel"). The companion's turns sit on
one side with its face and a read-aloud icon, the child's on the other, and one row takes the
child's words: record, type, send, with a small "还没想好，换个小问题" above it once something has been
asked. There is no separate "现在问孩子" card: the question to ask ends the companion's own turn.
While the companion writes and its words are checked, the thread shows one typing bubble (after
the child's words it carries the quick line "我听到啦！让我再好好看看你的画。"); the checked turn then
appears whole. Nothing unchecked is ever on the screen or spoken. Pressing Send never moves the
row: Stop sits under the typing bubble, not where Record is.

The following refinements take precedence over the original exploration below:

- Warm paper, generous space, a quiet header, tools on the left, Splat on the right,
  and drawings plus the main action along the bottom. Preserve the original drawing's
  proportions and leave room around it so neither the tools nor Splat cover the subject.
  Let a very faint trace of the drawing's colours reach the edges; never blur or recolour the original.
- Interface ink is warm charcoal (`#403832`, secondary `#6D6057`, muted `#7E7065`).
  The companion uses soft coral; primary actions use accessible coral (`#B95741`),
  and secondary generative extras use muted violet (`#76668F`) — never a screen's main button. The child's paint keeps its original colours.
- Glass is a light paper-tinted layer, with an understated white rim, 12px blur and a
  soft warm shadow. No chromatic displacement, continuous sheen, or coloured haze behind text.
  Use glass only for the tool rail, companion and dock. Sheets and viewers use opaque paper.
- Keep the rounded local type stack; Chinese headings breathe at 26–32px and body copy
  at 15–17px. Avoid all-caps labels and excessive tracking. Secondary captions stay readable.
- Every active control has a visible name or accessible label and keyboard focus. Child-facing
  primary buttons reach 76px on touch; other touch targets reach 44px. Short and narrow screens
  reflow vertically and allow scrolling instead of cutting off controls or covering the artwork.
- Splat's name and face precede the observation. The question is the largest text in the
  companion panel; teacher confirmation has its own field and action. Detailed steps can be
  expanded, and failures remain visible. No invented progress percentages.
- Modal sheets focus their first control, keep keyboard focus inside, and return focus on close.
  The opening, lesson settings, camera, media, book and teacher views share the same visual system.
- Keep a labelled home entry beside the brand and a visible back action below the header.
  Home preserves the current class in page memory and offers resume. Back returns from an answer
  to its question, then through visited activities, then home. Neither action ends the class.
  Switching the class type with existing drawings requires an explicit in-page choice to end it;
  focus the option that keeps the current class. Closing the prompt keeps all current work.
- Keep interface assets local. Capability labels must follow the actual service response;
  an attractive preview is not proof that a backend skill or full offline operation is available.
- Retain reduced-motion support; movement belongs to the child's requested animation and
  explicit interactions. No idle blob animation or endless mascot wobble.

The still pose preview (a FLUX.2 Klein image edit, added early on) was later retired:
**Make it move** offers the Wan clip, or in a colour class the 3D figure,
and never a still picture or a picture model. Pose previews already saved in a course still open, labelled as still pictures and
compared with the original.

A storybook's third step chooses its pictures: **the originals**, each page the
drawing or its clip, or **a picture-book style**, every page redrawn in one of seven looks the
teacher sees on page 1 first. The originals are always offered and are chosen when she opens the
step; a page whose redraw may have changed the child's picture is named for her to look at.
Reserve the **Light and motion** tab for sketch classes.

The remaining sections record the product principles and original exploration. Where material,
layout, palette or motion details differ, use the selected direction above.

The product is 画里画外 Beyond Canvas. The companion name "Splat" is a placeholder until the team chooses.

---

## 1. Philosophy

Seven sentences. Everything below follows from them.

1. **The child's picture is the room.** The drawing fills the screen. The interface floats on it and
   never covers, frames or competes with it.
2. **Colour comes from paint, not from the interface.** The interface is glass and ink. The only
   saturated colour on screen is the child's, plus one tinted action button.
3. **Glass the Apple way: one layer, clear, lensed, alive.** Apple's Liquid Glass is the material.
   Light bends at the rim, a glint follows the hand, paint bleeds through. Never glass on glass.
4. **Big, round, springy, spoken.** Hands are small and many users cannot read yet. Targets are
   large, letters are round, things squash and spring back, and every control can be said aloud.
5. **Splat is a character, not a chat box.** The agent has a face, a mood and a voice. Its
   work is shown as steps a child can follow, never as a log.
6. **Calm for grown-ups.** Parents and teachers get a few numbers on plain tiles, the same
   palette, no glass, no charts.
7. **Everything stays on the box.** No network for fonts, scripts, images, voices or pictures.
   The interface says so in plain words.

---

## 2. Tokens

### Paint (the child's colours; also the only accents)

| Name | Hex | Use |
|---|---|---|
| Coral | `#FF6F61` | primary action tint (with Tangerine), companion body |
| Tangerine | `#FF9F43` | action tint end |
| Sunflower | `#FFC93C` | stickers, praise |
| Leaf | `#5ED6A6` | positive moments, privacy badge |
| Sky | `#4FB3FF` | secondary tint (with Violet) |
| Violet | `#9B7BFF` | secondary tint start, magic button |
| Rose | `#FFB3C7` | paint dock only |
| Ink | `#26224A` | all text; the eighth paint |

Paper is `#FFFDF8`. Secondary ink `#3A3560`, muted ink `#5A557A`. No grey grounds anywhere.

### Status (reserved; never used as accent, never borrowed from paint)

| Role | Hex |
|---|---|
| good | `#0CA30C` |
| warning | `#FAB219` |
| critical | `#D03B3B` |

Status always ships as icon plus label, never colour alone.

### Glass

| Property | Regular | Clear |
|---|---|---|
| white tint | 11 % | 4 to 5 % |
| backdrop blur | 8 px | 2 px |
| saturation | 1.9 | 1.9 |
| rim | inset 1 px white 70 %; top edge 2 px white 95 %; left edge 2 px white 55 % | same |
| inner glow | 26 px white 28 % | same |
| drop shadow | 0 18px 40px -18px rgba(60,40,120,.32) | same |
| specular | radial highlight whose centre follows the pointer | same |
| sheen | one diagonal band drifting across every 9 s | same |
| lens | SVG displacement at the rim, band 22 % of the panel, red/green/blue bent by 84/72/60 | same |

Clear is for panels sitting over the picture and needs a dimming layer (a scrim) under any text.
Never mix Regular and Clear in one context. At most three glass panels on a screen.

Text on glass: ink colour, with a soft white glow (`0 0 9px` white 70 %) and, for paragraphs,
a scrim of white at 30 % with a hairline.

### Shape

Panels 28 px radius, bars 30 px, pills 999 px, grown-up tiles 20 px. Nested corners are concentric:
inner radius equals outer radius minus padding. Round every corner; no square boxes.

### Type

One rounded family, bundled locally (Safari's system rounded face is not reachable from Chrome).
Fallback stack: `ui-rounded, "SF Pro Rounded", "Arial Rounded MT Bold", "Nunito", "Avenir Next", sans-serif`.

| Role | Size | Weight |
|---|---|---|
| studio labels and buttons | 15 px | 600 |
| companion speech | 15 to 17 px | 500 |
| big child buttons | 22 px | 700 |
| stickers | 26 px | 800 |
| grown-up hero figure | 44 px, one per view | 700 |
| small captions | 12.5 to 13 px | 600 |

Sentence case everywhere. No all-caps labels. No numbered markers unless the content is a sequence.

### Targets

Touch screens used by children: primary controls at least 2 cm on the glass, about 76 px.
Mouse and pen: at least 48 px. Nothing important is smaller than 44 px. Icon plus spoken label on
every child control; no control depends on reading.

### Motion

One spring curve for presses and morphs: `linear(0,.35 12%,.8 24%,1.06 38%,1.02 52%,.99 66%,1)`,
0.5 to 0.6 s. Presses scale to 0.90 to 0.94 and spring back. The selected pill in a segmented control
slides and stretches; it never jumps. One orchestrated moment per screen (the paint reveal sweep,
about 2.4 s), nothing else moves on its own except the 9 s sheen. `prefers-reduced-motion` gets a
still page with the same content.

---

## 3. Rules

**Layout**
- The picture is the ground and reaches every edge. Controls are absolutely positioned glass over it.
- Tools left, companion right, paints and the one big action bottom centre. Keep this map on every
  studio screen so a child learns it once.
- Three glass panels maximum. The segmented control inside a bar is a translucent track, not a pane.

**Colour**
- The interface uses ink, paper and glass. The child's paint is the only saturated colour, plus one
  tinted primary action (Coral to Tangerine) and one magic action (Violet to Sky).
- Green is for "good" only. Never use NVIDIA's green as an accent; the studio must not look like a
  settings page for the box it runs on.

**The companion**
- Splat speaks first, in one short sentence a seven-year-old can follow, then offers two choices.
- Its work appears as a short list of steps in plain words ("Found a sun, a house and a tree"),
  each with a tick. Never a log, never a percentage.
- Every line Splat writes can be said aloud with the local system voice.
- Errors are Splat lines: what happened and what to do next. No apologies, no vagueness.

**Words**
- Active voice, plain verbs, the same word through a flow: the button that says "Paint it" produces
  a sticker that says "Painted!".
- Name things by what a child recognises (paints, stickers, Splat), never by how the system works.

**Grown-ups**
- Four numbers, a list of colours learned, a plain privacy statement, and the trail of what Splat
  did today. Plain white tiles on the paper ground. No glass, no charts, no jargon.

**Offline and performance**
- No fonts, scripts, images, voices or pictures from the network. Voices are local system voices.
- Edge refraction renders in Chromium only. It must degrade to frosted glass without breaking
  anything. Pin the demo machine to Chrome or Edge.
- Blur under 22 px, three blurred panels at most, pixel ratio capped at 1.5 to 2 on canvases,
  one canvas per scene, and every animation loop pauses when off screen. Measure on the box at 4K.

---

## 4. What we do not do

- Dark or grey grounds. The reference screenshots were a dark map; only their material survived.
- Rainbow gradients on interface chrome. Gradients belong to paint and to the two action buttons.
- Glass on glass, or a fourth glass panel.
- Emoji as icons. Icons are single-weight line drawings.
- Motion on every card, fade-and-slide-up entrances, hover effects everywhere.
- Tiny targets, text-only buttons, anything that requires reading to proceed.
- Cloud speech recognition. Listening is a model on the box, and belongs in the schedule.
- Charts for children. Numbers for grown-ups are four tiles, not a dashboard.

---

## 5. Before you call a screen done

- Screenshot it at 1920×795 and 1920×940 and look: nothing cut off or covered, no half-empty
  screen, the main action visible without scrolling.
- The picture fills the screen and nothing sits between the child and it except glass.
- Count the glass panels: three or fewer, none stacked, Regular and Clear not mixed.
- Read the text over the brightest part of the picture. If it strains, add a scrim; do not
  thicken the glass.
- Every child control: at least 76 px on touch, an icon, a spoken label.
- Press each control: it squashes and springs. Change a segment: the pill slides.
- Turn on reduced motion: the screen is complete and still.
- Pull the network cable: everything, including the voice, still works.
- Open it in Safari: the glass is frosted but nothing is broken.
- Run it on the box at 4K and watch the frame rate with three panels open.

---

## 6. References

- Live demonstration: `docs/design/beyond-canvas-lookbook.html` (one self-contained file).
- Apple, Human Interface Guidelines, "Materials" (Regular and Clear, dimming layer, no glass on glass).
- Apple, WWDC25 session 219 "Meet Liquid Glass" (lensing, specular highlights, adaptive colour).
- WebKit bug 245510: SVG filters in `backdrop-filter` not yet shipped in Safari (still open when this was written).
- Nielsen Norman Group, "Design for kids based on their stage of physical development": 2 cm targets.
- Source material: four screenshots of a transit control-room concept by RON Design, shared on
  rednote by subvecta. Their dark palette is deliberately not used.

Written from the lookbook work. Change this file first, then the lookbook.
