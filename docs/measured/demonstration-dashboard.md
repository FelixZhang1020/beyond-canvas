# The demonstration dashboard, measured

All on this Mac (Apple M-series, Chrome in the desktop app's browser pane, viewport 960 to 1280 px
wide), against the exhibit on port 7090. Numbers read from the page's own DOM through the pane's
script tool; the commands and the runs are named so they can be repeated.

## The smooth page (commit e289be7)

Replaying a finished run at 4x: rows grew from 9 to 16 in 3 s, the first row stayed the same DOM
element throughout (no redraw), four long printouts were folded, the page stayed at scroll 0 with
the "new step" pill showing.

## Typing, popping, the live screen (c652d00, 8ace32f)

A live take-apart run on the stack model started from the page ("Take this little building apart
from the top down"): at 0:58 the status read "rendering explode · frame 97 of 180", the bar 54 %,
the big screen showed `explode/f0097.png`, joint-reveal ticked active; at 1:45 the run finished
with the pull-apart picture judged pass on the big screen. The burst fired at step 14 of 17 of the
same run replayed at 4x (fourteen dots); the glow was seen on a live fly-around run at frame 98
of 480.

## The live 3D view (f04be07, 320b830, 5e1aef9)

```bash
blender -b output/foguang-east-hall/foguang-east-hall-v25.blend --python-exit-code 1 --python studio/showpiece/glb.py -- .studio/showpiece/runs/models/foguang-east-hall-v25.glb --light
```

| export of the hall | nodes | size | time |
|---|---:|---:|---:|
| everything, textures as JPEG | 9,064 | 111.7 MB | 69.5 s |
| light: ground joined, covering thinned, JPEG textures | 9,064 | 85.7 MB | 32.2 s |
| light, no textures | 9,064 | 75.7 MB | 31.6 s |
| light, positions and colours only (shipped) | 8,017 | 18.2 MB | 15.8 s |

In the page, the hall's recorded construction run:

| drawing | load | frames per second |
|---|---:|---:|
| one mesh per piece (9,064 draw calls) | 571 ms | 1 |
| merged by what moves together (25 meshes) | 671 ms | 61 |

The stack: eleven pieces found by name, the screen switched to 3D at step 12 of its run when
`explode.json` landed, a drag turned it. The hall's four other showpieces on the recorded runs:
pull-apart 74 meshes, load 3 (frame tinted, roof lifted), tour 5, settle 3.

## The three-part demonstration (cad3ab0)

Pressing 盖起来 showed the recorded build-up in 3D 265 ms after the press. Clicking the first
prompt chip: at 2 s the status read "thinking…" with driver and model lit on the monitor; at 16 s
the judge step, driver and judge lit, five rows drawn, 180 frames counted, the pull-apart playing
in 3D. The build-up prompt: at 9 s "running bearing…" with driver, skill and Blender lit and the
link skill → Blender pulsing; the whole six-step run, whose tools took 891 s, finished in about 40 s.
The monitor read this machine's host name and a CPU load of 37 % at the time.

## What these numbers are not

Nothing here measures the model's judgement or the skills; that is in the benchmark record. The
five temple runs on the page are recordings assembled from the results in the other measured
documents on the hall; they are marked "recorded" on the screen. The GPU gauges have not been
seen working: this Mac has no NVIDIA tool to read.

## The five recordings, made by the tools themselves

The hand-assembled `20260917-hall-*` runs made earlier were replaced by recordings the
tools made under `studio/showpiece/record.py`, one folder per showpiece, on this Mac:

```bash
for k in tour raise load explode settle; do
  .venv/bin/python -m studio.showpiece.record --model output/foguang-east-hall/foguang-east-hall-v25.blend \
      --runs .studio/showpiece/runs --kinds $k --timeout 7200 > .studio/showpiece/runs/record-$k.log 2>&1 &
done; wait
```

**The tool limit was too short for the hall.** The first attempt ran the five side by side under
the catalog's 900 s limit per tool: only the take-apart finished (412 s); the tour, build-up,
load flow and settle were killed at 900 s. Alone, the hall's tour already takes 1,353 s (the
section above). The limit is 3,600 s now (`catalog.BLENDER_TIMEOUT`), `record.py --timeout`
overrides it, a recording is built as `recorded-<kind>.part` and renamed only when whole, and the
exhibit does not list a run folder that has no `events.jsonl` yet.

The second attempt ran the four missing ones side by side (35 min 55 s from start to finish);
the settle was then remade alone beside the tour's last minutes (798 s) after the recorder
was changed to keep the tool's whole printed tail, so its card shows the result line.

| Showpiece | Tool seconds (inventory + bearing + the rest) | Frames kept (every third) | Folder |
|---|---|---|---|
| take-apart (`explode`) | 24.8 + 150.4 + 237.0, five sharing the GPU | 60 | 94 MB |
| tour | 14.2 + 90.7 + 2,050.5, four sharing | 160 | 263 MB |
| build-up (`raise`) | 14.2 + 89.9 + stages 0.1 + 1,164.7, four sharing | 99 | 154 MB |
| load flow | 14.2 + 89.2 + weights 3.2 + 1,029.5, four sharing | 80 | 121 MB |
| settle | 17.0 + 115.4 + 666.1, two sharing | 32 | 55 MB |

The settle under four-way sharing had taken 1,148.9 s; the build-up's `RAISE 24 scenes 296 frames`,
the flow's `LOADS 8170 pieces total 9.229 MN ground 8.302 MN` and `FLOW 6264 pieces 240 frames`,
the tour's `TOUR 4 segments 480 frames`, the take-apart's `EXPLODE 78 pieces 24 tiers 180 frames`
and the settle's `SETTLE 6264 pieces fell 0 shifted 0` match the earlier hand runs.

Verified on the page after each landed: every one-press button shows its recording whole with
the 3D hall in that showpiece's state (`3D 模型 · <kind> · 8017 / n`), and each of the four prompt
chips replays its recording as if live. The hand-assembled folders were then removed; the exhibit
lists five recorded runs. The recordings stay on this Mac (`.studio/` never leaves it); the Spark
makes its own on day zero.

## Operation gaps, found by driving the page and closed in the same sitting

Measured at a projector's size (1920×1080, emulated in the desktop app's browser pane), pressing
through the presenter script. Rendering was never the problem: 60 frames a second through a whole
replay, no layout shift, one 72 ms stall. The page asked the presenter to scroll.

| Gap | Before | After |
|---|---|---|
| The page is a scroll, not a stage | 2,218 px tall; the monitor 1,876 px down, runs and gallery a screen down | 1,080 px: one screen; the conversation scrolls in its own box, the screen and its controls at 180–741 px, the monitor a strip at 910–1,066 px; also one screen at 1440×900 |
| The answer lands off-screen | the final row at 1,058–1,129 px of 1,080; the "new step" pill scrolled the screen out by the top | the final row ends at the box's bottom edge (833–881 of 245–881); nothing on the page moved in 27 s of replay; the pill is for live runs only |
| Language switch kills the 3D view | 0 canvases after EN, never back | 1 canvas after each switch, captions in the new language; the viewer is disposed and remade |
| The replay controls disagree | 4x dropped the heartbeats and ended in 4 s; scrub then play left "running inventory…" at 5 / 5; play at the end did nothing | one engine: 4x keeps the heartbeats (running → rendering → thinking → finished, 7 beats seen) and ends in 4 s; a scrub clears the status; play from 2 / 5 reaches 5 / 5 "finished"; play at the end starts over |
| The screen is small | a 500 px pane in a 1,320 px column | a 1,720 px stage, 16 px type from 1,600 px wide, and a theatre button: the panel over the whole window (the model at 1,862×920), full screen on top where the browser allows it (this pane refuses: "Permissions check failed"); Escape leaves |
| Every run switch pulls the whole film | 16 MB tour.mp4 fetched at load | no film fetched at load; gallery films load when played |
| Small things | no keys; the run button silent on an empty box | space plays or pauses, the arrows step, Escape leaves the theatre (proven with key events; the pane's key tool sends no space); the run button is disabled until there are words |

Two more, found by the same numbers: the 3D model was fetched twice on load and two viewers were made
(two updates arrived while the module and the model loaded); now one viewer and one fetch, the
model on screen 825 ms after navigation, a run switch 193 ms and 1.3 MB with the piece roles cached
per model instead of 6.5 MB of anatomy per run. In the emulated 1080p tab the 3D view ran at 6
frames a second while the picture view ran at 61 and the same 3D view at the pane's native size ran
at 61: the pane's scaling of a large emulated viewport, not the page; the renderer's pixel ratio is
capped at 1.5 all the same.

## The rail on the left (operator's choice, made afterwards)

Asked where the backend monitor should live, the operator chose, from three drawn layouts, a
vertical rail and put it on the left: backend on the left, the buttons over the conversation in
the middle, the agent's screen on the right. Measured at 1920×1080 after the change: one screen
(1,080 px), the rail 250 px wide with the flow map drawn top to bottom and the six skills under it,
the screen 753×660 px (it was 894×426 with the monitor as a bottom strip), and during a replay the
rail's skill, Blender and screen nodes lit with the Blender-to-screen link pulsing. From 1100×860
to 1399 px wide the rail folds into a strip under the stage; from 640 px wide it is a strip above
the stage on a small pane; narrower than that it goes to the bottom, one column.

## The rail as a console (operator's choice: "B + LOG in A")

From three drawn designs the operator chose the process table
and pipeline tree of B with the log tail of A. The rail is now the one dark block on the page,
320 px wide, in mono type: the machine as block-character bars with a history (cpu, mem, gpu,
fps); a process table with four components (driver, step-3.7-flash, blender, ffmpeg) and the six
skills, each with state, time and calls, the busy rows lit; the pipeline as a tree with the branch
the work is on lit; and a log tail, one line per step with its elapsed stamp, and a live line for
the heartbeat with a blinking cursor. The flow-map monitor is retired; `flow.mjs` keeps the pure
state, `ops.mjs` the pure rows, tree and lines (tested), `console.mjs` the DOM. Measured at
1512×850 during the tour replay: the rail 320×761, driver, blender and structure-tour lit,
`blender tour 94/480` on the tree and the log's live line, the page one screen; at 1280×800 the
console lies across the bottom in four parts, 240 px tall.

## The switch above the conversation (operator's choice: B)

The one-press buttons, the prompt chips and the live chip were three rows of pills that read as
one thing. From three drawings the operator chose a three-way
switch, 一键演示 / 提示词 / 现场: one kind of control on show at a time, its caption beneath, the
choice remembered in the browser. Measured at 1512×850: the control block is 118 px with the
buttons or the live chip and 207 px with the four chips (they wrap to three lines in the middle
column), against 194 px for the two rows before; the conversation box is 633 px tall with the
buttons on show.

## The walk-through's five, and the conversation as a chat

A full walk-through (load, header, the switch's three kinds, the screen's buttons, replay
controls and keys, the runs list, the console, both languages, two sizes, one real live run on
the small model: 61 s, 17 steps, two stumbles recovered) rated the demonstration 8 of 10 and
named five gaps; all five are closed: a replay resumed after its finale no longer keeps the film
view (the finale flag clears on resume and scrub; a film view with no film falls back); the runs
list shows the recordings and the three newest live runs with an "all N" toggle (9 listed of 43);
a file read is a card that says the file and its size, not its contents; a stopped or scrubbed
replay says "paused · step n" and the jump button on a recording says "to the end"; an empty
thought draws no row; films start muted; the caption follows a view flip at once; the switch
opens on the one-press buttons every time. The conversation is laid out as a chat: the request
as the reader's bubble, the agent's turn under its avatar and name, thoughts in a quiet voice
with a rule, tool cards with a green or red mark, the answer as a bubble, and a typing indicator
with dots while the model thinks or a tool runs (seen 16 of 20 s through a replay, 13 naming the
tool).

## Two removals (operator)

The run list and the gallery under the screen went first ("this is a demonstration module"), then
the replay row: play, the scrub bar, the step count, the pace menu and the jump button, with the
space and arrow keys that drove them and the `pace` helper nothing called any more. A button shows
its run whole, a chip replays its run as if live, and that is all the replay there is. The agent's
screen fills its column: 581×638 px at 1512×850, against 581×448 with the two panels and the row.

## Live scenarios on the little building, and cards that show what really ran

The 现场 row grew from one chip to a list of scenarios in `strings.json` (`live.items`, both
languages, each with its words and its expected minutes). Each candidate was run once, live,
through the exhibit on the eleven-piece stack with Step 3.7 Flash (the run folders are on this
Mac):

| Scenario | Seconds | Steps | Ended | Film |
|---|---|---|---|---|
| know the pieces (认构件) | 18 | 10 | answer | no |
| take it apart (拆开来) | 115 | 17 | answer | explode.mp4 |
| build it (盖起来) | 127 | 22 | answer | raise.mp4 |
| let it settle (松开手) | 160 | 17 | answer | settle.mp4 |
| show the load (看载荷) | 423, cut off | 29 | still going | none |
| tour it (转一圈) | not measured | | | |

The load scenario came off the chips: the model called `load-path/flow` before `weights` and kept
looping; the tour's measurement was ended by the exhibit restart and its chip carries the
benchmark's five minutes. A second, unrequested take-apart run had started meanwhile and looped
through close-ups for thirteen minutes until the restart; its origin is not known.

The operator then read a tool card as "fake information" (a one-line summary, a file name, 0.5 s).
Every tool step now records the exact command it ran (`driver.command_line`: the binary by its
name, paths relative to the repository, arguments quoted; the recorder writes it too and
`--reword` fills it into older recordings), and the card shows it under `$`, the tool's last real
output lines with the summary in bold, `exit 0` with the seconds, and each written text file as a
button that opens its real contents under the card. The five hall recordings were refreshed to
carry their commands.

## Everything is the temple: live runs on the hall, in colour

The operator: "everything needs to be related to our temple". The exhibit now starts on the
hall with `--quick` (a machine-local launch file): a live run renders at 960×540, 10 frames a
second, 3 s a shot, unless the model asks otherwise (`catalog.QUICK`, `quick_args`; the model's
own values always stand). The little test building is gone from the page. The live chips are
five temple questions with minutes:

| Chip | Live on the hall | Steps | Note |
|---|---|---|---|
| 认构件 | 123 s, measured | 12 | one wrong first call corrected; answered in words |
| 拆开来 | 254 s, measured | 21 | two wrong bracket-set names, then the pull-apart in 22.5 s (the full-size recording: 237 s), the judge's pass, a film |
| 盖起来 | about 5 min, estimated | | from the recording's 1,165 s at a quarter of the pixels and a third of the frames |
| 转一圈 | about 6 min, estimated | | from 2,050 s the same way |
| 松开手 | about 13 min, estimated | | the physics, not the render, is the time |

Colour: every piece now wears the colour of its role on every 3D view (`plans.roleTint`: timber
warm, rafters darker, the roof's tiles grey-blue, walls plaster, the ground stone), the load tint
and the settle marks drawn over it; the roles come from the run's anatomy, so a live run is
coloured once it has counted its pieces. The idle caption after a finished run without a
showpiece now says so instead of asking for a button.

## A live run's finale, and watching a run again

The operator pressed 认构件 and the model, this time, chose to film the build-up as well: 24 scenes
rendered quick in 237 s at 1.7 s a frame (the pieces, not the pixels, are the cost), two judged
stills, an answer, six and a half minutes in all against two the first time. Three changes from
it: a live run's film goes large by itself when the run ends, as a replay's does; a 重播 button on
the screen's status row replays the run on screen as if live, film finale included, at no cost
(it hides while a run or replay is going); and the 认构件 chip says "约 2–7 分钟" with a note on
hover that the model may film. The heartbeat's frame total now counts with the quick settings:
a live take-apart read "共 30 帧" through its render, ended at 260 s and 19 steps, and finished on
its film with the button shown.

## 一键演示 plays the steps

The operator: "一键演示 should have steps simulation rather than directly shows the results". Until
now a one-press button filled the conversation in one go and put the 3D showpiece on the screen;
only the prompt chips replayed a recording step by step. Now both play the steps, at two paces
(`stream.mjs PACES`, `player.replay(events, pace)`): the buttons briskly, a tool's wait 1.5–8 s
and a thought 1.2 s, ending on the 3D showpiece moving; the chips as before, 2.5–20 s a tool,
ending on the film. 重播 keeps the pace of whatever was pressed, across a language switch too.
While the 3D turns before the run has written its plan the caption now says so
(`view.hint.working`) instead of "waiting for a press".

How long each recording takes to play, from the events on disk (`node` over
`replayPlan(events, PACES.replay)` and `PACES.brisk`; the script is in the session's scratchpad,
the numbers are the plan's last `at_ms`):

| Recording | Steps | 提示词 chip (s) | 一键演示 button (s) |
|---|---|---|---|
| raise | 6 | 34.7 | 19.2 |
| tour | 5 | 31.4 | 16.9 |
| explode | 5 | 18.6 | 16.4 |
| load | 6 | 34.6 | 19.2 |
| settle | 5 | 28.4 | 17.5 |

Verified in the pane on the exhibit: 盖起来 pressed, the conversation grew 1, 2, 3, 4 rows over
the first 8 s, the screen painted the raise frames 19 → 238 of 296 between 10 and 16 s, the raise
card landed at 18 s with the 3D view on, the answer at 20 s with 完成 and the 3D caption; the first
提示词 chip finished at 22 s on its film with 重播 shown. The presenter script's rows for the three
buttons and the chip say what is now seen, and its English live row no longer names the small
building.
