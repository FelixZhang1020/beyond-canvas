# Beyond Canvas studio page

The teacher-facing studio, one HTML file in plain JavaScript, built from the parts in `src/`.

## Image model status

No image model is offered. **Make it move** makes the Wan clip, or in a colour class the 3D figure:
the FLUX.2 Klein still pose, its place in the output choice and its picture-model line were removed
(operator: Wan makes the real animation). Pose previews saved before then still open from the Portfolio. StepFun image
models and hosted or local Step1X were never shown. Historical measurements remain evidence of
past runs, not currently selectable models.

## Course portfolio

The Portfolio is part of the classroom at **http://127.0.0.1:7060/**. The classroom brand's **Course portfolio**
action (「课程作品集」) returns here. The saved-course profile also has the same brand action
and an **All courses** button.

Home now opens a persistent course shelf above the existing class entrance. Teachers can
name a new course, search by name or lesson topic, filter by class type, rename a saved course,
and open its drawings, confirmed words, responses and completed creations. Large 3D and
image-edit results are loaded on demand and use the existing viewers; opening history makes
no image/vision model calls. Saved books retain their confirmed ending, export as before,
and can use the resident voice without creating a new classroom session.

`studio.serve` enables `studio.classroom.portfolio.Portfolio` at `.studio/portfolio.sqlite3` by default.
The `--portfolio` option selects another private local database; no new package is required.
Course metadata, uploaded originals and completed outputs are written before successful
responses. Closing the live class releases temporary files, audio and diagnostics while
keeping the Portfolio. SQLite transactions provide durable restart behavior. This supersedes
earlier descriptions of "forget everything". No per-child identity profile is kept, and of the
recordings only one per drawing is: the child's first spoken answer, at most ten seconds, for the storybook
to read that drawing's page, and the chat to play the child's answers back, in the child's voice.
**Finish class** is a visible classroom action that makes all content read-only, including renaming and story endings. **Reopen course** restores its artwork,
confirmed words and saved feedback in the same course; new model work screens the drawings again.
Unfinished courses open directly in creation; finished courses open directly in review.
Leaving, switching courses and server shutdown only release editors; they do not mark the saved
course ended. A fresh editor ID prevents
an older tab's unload or late result from affecting a reopened course. Existing ended courses stay ended.
Courses erased by older versions cannot be recovered by this feature.

Frontend: `05-portfolio.css`, `24c-portfolio.js`, and the existing class/book/voice wiring.
The Portfolio shares the classroom brand, warm background token, primary buttons and entrance
card material; its filter bar and conversation panel reuse the existing quiet glass. Do not
give course cards the `.pick` class: that class also binds the new-class action.
Backend routes are in the [page contract](../../docs/specs/studio-page-contract.md).
Verification and the running development address are recorded in
[the portfolio measurement](../../docs/measured/course-portfolio.md).

The rest of this guide includes earlier implementation records; their original temporary
class cleanup still applies to working state, with persistent course history now added.

## Classroom interface

The user selected **A · 通透画室**; the implementation landed the next day.
The warm paper layout keeps the drawing between a left tool rail and Splat, with activities above
and the drawing dock below. Narrow screens put these in document flow so longer speech stays readable.
The opening, teacher confirmation, settings, media viewer, book and ledger share this direction.
See [the selected design rules](../../docs/design/DESIGN-PRINCIPLES.md).

The two opening cards use generated gouache and graphite illustrations. Originals, compact JPEGs
and generation prompts live in [assets/entrance](assets/entrance/README.md). The build embeds the JPEGs
into the page, so both the classroom server and the standalone preview need no extra asset routes.

`24b-dialogs.js` keeps focus inside open sheets and restores it on close. The heard-text field
accepts multiple lines; confirm with its button or Ctrl/Cmd+Enter. The main button cancels an active
request, including its visible running state. Preview mode uses sample responses; real media
availability still follows the classroom service. Do not infer service or hardware validation from the UI.

The brand includes **Back to home**; **Back one step** sits below the header. Returning home keeps
the class and offers **Continue class**. **Start a new class** creates a separate course even for
the same entrance; continuing is an explicit action. Back closes an answer form first, then returns through visited activities, then
home. Feedback and unsent answer drafts can be restored when returning to the conversation.
Navigation stops frontend waiting, recording and playback; late callbacks cannot replace the view.
These are in-page controls: refreshing or closing the browser still ends the in-memory class.

Switching to the other class type with existing drawings opens a confirmation sheet, with the
close action focused first. Closing or Escape keeps the class. Discard starts the new course
and drops only unsaved input; saved courses remain in All projects. Save and start preserves
answer drafts separately from confirmed words and restores them when editing the old course. A failed end-session
request retains local drawings and answers; a successful end resets the activity history and drafts.
Navigation checks cover the mock browser flow at desktop and 390px widths; the session transition
failure and success paths are covered in `tests/page/navigation.test.mjs`.

A review of that implementation found and fixed two class-transition races. Ending a class now shares one
pending request, releases only that class's artwork URLs, and cannot clear a newer class or its view.
Image preparation, the light check and upload keep the originating session ID, including delayed
camera/sample results. Stale results and errors are ignored and unused image URLs are released;
active-class errors still surface. Transition controls stay disabled until ending/starting settles.
The 17 transition/import checks pass, with six failures reproduced before the fix; all 93 frontend
checks and the page build also pass. The mock browser was checked for import, home and resume.
Its native end confirmation blocked automation, so the end success/failure evidence is from unit
tests, not a completed browser end flow. No real model, camera or microphone was used for this fix.
The shared-workspace count includes parallel features. The isolated frontend commit passes its
66 frontend tests, 16 classroom HTTP tests (scripted models), and the page structure/build check.

```bash
sh deploy/spark/test-on-spark.sh sh studio/page/build.sh   # on the Spark: writes index.html, brings it back
sh deploy/spark/test-on-spark.sh node --test tests/page/portfolio.test.mjs   # page checks, on the Spark
sh deploy/spark/sync.sh                    # then try it by hand on the standard studio, https://{spark-address}:7100
```

Nothing runs on the Mac and no extra service runs on the Spark: tests run on the Spark, and the page
is tried by hand in Chrome on the standard studio (operator): after the change is sent
with `sync.sh`, in a course made for the purpose whose drawings are deleted afterwards, with real
clicks at the widths teachers use (a phone and a laptop). What follows about `studio.serve` describes
how it behaves where it runs, which is the Spark.

`studio.serve` serves the page and the harness together on http://127.0.0.1:7060/, so a tablet on
the studio wifi needs one address. Pass `--host 0.0.0.0` to reach it from another device and
`--port` to move it to a free port allowed by the [project port convention](../server/ports.py).

HTTP pages require the real classroom service by default. A failed health request stays a
visible connection failure rather than silently switching to sample responses. Add
`?transport=mock` for an explicit UI preview, or open the file directly. The sample library
requires the classroom service even in previews; choosing a local photo remains available.

## The four beats on screen

Feedback arrives with the one question to ask the child, and under it the two things that can
happen next. **They answered** opens a field with two ways to fill it: the teacher types what the
child said, or presses **Let them say it** and the child says it out loud. **Nothing yet** asks a
smaller question instead, twice at most, because there is no fourth rung.

Where listening happens decides where a child's recorded voice goes, and under **StepFun First**,
the only deployment, it is bought from StepFun's `stepaudio-2.5-asr`: in every
class a child's voice reaches a company. Local First, which heard on the 4090, was archived
with this consequence stated. Say that plainly to anyone who asks: this file used to promise the
opposite, and the old wording is quotable and still widely quoted.
`studio/voice/transcribe.py` carries the reasoning.

Hearing on this Mac is a route no deployment chooses; the development profiles use it. It needs
whisper.cpp plus ffmpeg, and one script starts it alongside the studio model:

```bash
sh studio/ops/localmodels.sh
```

Its models were deleted from this Mac, so the script now stops and names the file
it wants; download the Whisper model again to use this route. With nothing hearing, the button
reports that nothing is listening and typing still works.

Whoever hears, two things hold. A recording is kept only if it is the first spoken answer about its
drawing (at most ten seconds, for the storybook voice); every other one lives in memory for as long as it
takes to transcribe. A spoken answer in the chat goes into the conversation at once (operator),
where the teacher sees it before the reply and takes a misheard one back; a file and the book's spoken ending
appear in their field for the teacher to read and correct before any of it is sent to a skill.

The contract with the harness is `docs/specs/studio-page-contract.md`.
Interface rules are `docs/design/DESIGN-PRINCIPLES.md`. Chinese strings live only in `locales/zh.js`.

## Sketch light studies

Choose the sketch entrance, upload a geometric, fruit or single-head study, then choose **Light and
motion → Stand the form up**. The viewer compares the drawing with approximate
box, ellipsoid and upright-cylinder geometry, measured mixed fruit, or a generated
head / fruit-study mesh. Drag to orbit; choose **Place the
light** and tap the tabletop, or drag the light in the top view. The sliders set
light position, height and brightness. Reset restores the initial view; export
saves the current lighting as PNG. Narrow screens offer **Show original**.

This needs the HTTP classroom and a vision endpoint. The mock explicitly refuses
3D recognition. It does not simulate a rotating photograph as a 3D result.
For the local Step3 model use the `local` profile's `vlm.sketch` request alias;
it shares the resident Step3 endpoint rather than loading another vision model.
Basic geometry does not load a mesh model. Heads and fruit-only studies need the
local TripoSG worker in [portrait_runtime](../portrait_runtime/README.md), configured
as `mesh.portrait` (the compatible slot name now serves both subjects). The generated
mesh has no baked shading texture: its surface and cast shadows respond to the lamp.
Hidden surfaces and fine detail remain approximate.
The renderer caps the mesh at 60,000 triangles, reuses shadow maps while orbiting,
and releases GPU resources on close. Generation and browser rendering are separate.
The local profile still uses its configured safety service; it is not fully
offline. See [verification and Spark limits](../../docs/measured/sketch-relighting.md).

Mixed still life keeps fruit kinds separate from solids. Pear neck and stalk
measurements produce an approximate surface on the CPU, then the existing mesh
renderer handles all mutual shadows. No new weights or dependencies are needed.
Missing fruit fields get at most one additional vision call; invalid results
remain failures. See [the supplied pear study verification](../../docs/measured/mixed-still-life.md).

A study consisting only of apples, pears and/or oranges instead uses one local
TripoSG generation for the whole image, with bounded surface smoothing and the
original image aspect ratio in the viewer. Missing services and failed meshes
remain explicit failures; successful results are cached within this drawing.
See [the apple-and-pear image-to-3D verification](../../docs/measured/fruit-image-to-3d.md).

## Drawing pose previews

In a colour class, choose **Pose preview → Generate short video preview**. The
classroom calls the configured Wan slot directly from the original drawing,
screens five frames from the returned clip, and saves the result for storybook
pages. One generation runs at a time. The mock refuses the action instead of
simulating generated media.


## Integrated classroom

Historical: the Mac no longer runs a class or any service; the class runs
on the Spark (`deploy/spark/start.sh`). Kept for how the launcher behaves.

On the prepared Mac, `.venv/bin/python -m studio.start` builds the page, checks private
configuration, starts/reuses Step3 sketch vision and Whisper, starts/reuses the prepared
TripoSG worker, and runs the classroom with VoxCPM2 on **7060**. `--check` only reports local
readiness and whether online credentials exist; it does not prove hosted inference works.
Startup performs no downloads or installs and never stops existing experimental pages.
`--port` selects a different free page port under the [same port convention](../server/ports.py),
including for temporary previews. Keep the launcher process running.

The launcher uses the existing isolated Python 3.11 voice environment at
`scratch/voice-candidates/vox-venv`, with its pinned VoxCPM2 source and weights. That environment
also needs the classroom's already-declared `httpx`, `Pillow` and `PyYAML` dependencies.
Pillow 12.3.0 was added there during integration; no new project dependency was introduced.
The regular project test environment remains Python 3.13. See the
[VoxCPM2 setup record](../../docs/measured/voxcpm2-voice-lab.md) and
[3D worker setup](../portrait_runtime/README.md) for model installation.
A fresh machine must prepare these runtimes first. The launcher supports the existing
`scratch/portrait` installation and the documented `.studio/portrait` installation.

The voice is part of the classroom process and is warmed before HTTP opens. Settings offer
local female and male preset voices. Feedback, questions, replies and book pages use the same
streaming player as the voice lab. Complete audio is cached per classroom/text/voice, bounded
to 12 lines and 16 MiB on the server; recordings and reference voice cloning are not used for
classroom synthesis. One speech request accepts up to 400 characters. Autoplay refusal leaves
a manual audio player; unavailable synthesis preserves text and reports the problem.

Recording, navigation, a new drawing and end-session stop playback. Async recording results
remain bound to the originating classroom and drawing. Transcription uses 16 kHz mono WAV
and explicitly bypasses environment HTTP proxies for the local worker. The transcript lands in
the confirmation field, and the chat's spoken answer is then sent at once; a homophone error in
the live sample was corrected in the field, and would now be taken back and said again.
Changes to lesson intent and language now also update existing backend conversations.

**Sample library** opens an entrance-specific thumbnail gallery: 69 colour artworks and eight
sketch samples in this installation. Images stay in the `Image Sample/` folders on the machine that runs the class and are never committed;
the built HTML contains no copies. Session-scoped image routes return resized JPEGs without
metadata, reject unknown IDs and paths outside the selected directory, and stop serving the
class after it ends. An absent library stays empty instead of drawing a synthetic fallback.

**Storybook** assembles 2–8 selected original drawings with their teacher-confirmed words.
Each page is screened separately. Silence leaves a picture-only page; no model invents a
caption or ending. The last page belongs to the child. The reader uses the local preset voice;
HTML export contains the images and text and opens offline, without embedded narration.
Next-child navigation preserves earlier drawings' answers for this collection.

Stop now also reaches the backend. It cancels subsequent stages and prevents late output;
a synchronous vendor/GPU call already running may finish before the worker is released.
Another activity in that class reports busy until the previous work releases its slot. Ending clears
the class and late ledger writes are removed when outstanding work returns.

Measured integration evidence and remaining limits:
[the integrated classroom measurement](../../docs/measured/classroom-integration.md).


## 3D comparison exhibit

The portfolio home links to `/showcase/3d/` in a new tab. The application server
serves the archived viewer and allowlisted files directly; no model worker is
needed to view it. See [the portable exhibit project](../showcase_3d/README.md)
for standalone startup, local binary backups and the two missing TripoSG display files.


## Cloud sketch classroom

The local and cloud profiles now use TRELLIS.2 by default, with Pixal3D selected
manually under **Other 3D options** in the right-hand sketch panel. No local 3D weights are loaded. Existing saved
GLBs reopen from the course database through `/viewer/3d/classroom.html`.
See [integration and local verification](../../docs/measured/sketch-classroom.md)
for startup, credential names, memory boundaries and the outstanding live acceptance.
