# Designing the Foguang hall from a written brief: what Step 3.7 Flash made of it

The four from-nothing rebuilds gave the builder our Blender model of
the Foguang East Hall to measure: its first act was always `hall-carpenter survey`, which turned the
model into a sheet of numbers, and "alike" was judged against the same model. That is reconstruction
by measurement, not design. The operator asked the next question — does it build from
zero, or copy? — and chose to find out (option C): the same builder, the same tools and the same
limits, but **no model of the hall at all**, only what a book and a photograph would give a person.

## What the builder was given

- **The brief** (`evalkit/briefs/foguang-east-hall/brief.md`), the request of every turn: the hall's
  name; built in 857, Tang dynasty, on Mount Wutai (snow, earthquakes); single storey on a stone
  platform; seven bays by four, 34 m from the first column to the last across the front and 17.7 m
  deep; an outer and an inner ring of columns; bracket sets on every column head about half as high as
  the column, carrying deep eaves; a single hipped roof with gentle slopes. The facts are Wikipedia's
  ("Foguang Temple"). No heights, spans between columns, column sizes or roof levels.
- **One photograph** of the real hall (`photo.jpg`, Wikimedia Commons, CC BY-SA 4.0, credited in
  `CREDITS.md`), shown with the first turn and set above the hall in every brief check's picture.
- **The same tools and instructions** as the rebuilds (`skills/hall-carpenter`), with `survey` and
  `likeness` refused in a sentence before anything runs, and a protocol of its own
  (`studio/showpiece/prompts/designer.txt`) that says every number is the builder's to choose and asks
  it to say where each came from.
- **The same limits**: 80 actions, 6 repair laps, 3 refused hand-overs.
- **The same model**, Step 3.7 Flash on the StepFun subscription, thinking at low effort, for the
  builder and for the eyes (`--slot vlm.sketch`: `vlm.studio`, which the rebuilds used, had
  moved to Qwen on the Spark with the class chat, and a design must not load the class's model).

## How a design is judged

Everything a rebuild must pass except likeness, which needs the temple: nothing hanging (bearing), no
column over what its timber can bear with snow and slenderness (weights), nothing falling or shifting
when let go for 3 s (settle), nothing coming down in the design earthquake and a sideways pull (shake).
In likeness's place, **`hall-carpenter brief`** (`skills/hall-carpenter/scripts/brief.py`) measures
the hall against the brief's own numbers (`brief.json`), and only those the brief gave in words
(`tests/showpiece/test_design_brief.py` holds the two to each other):

| brief | measured on the hall | passes when |
|---|---|---|
| seven bays by four | column lines across the front and deep | exactly 8 and 5 lines |
| 34 m by 17.7 m | distance between the corner columns' centres | within 6 % |
| an outer and an inner ring | rings of the column grid the columns fill | 2 |
| bracket sets on every column head | ≥ 3 timber pieces over each column head (the survey's own ruler) | every column |
| about half as high as the column | bracket sets' height over the column tops ÷ column height | 30 % to 70 % |
| a timber hall | tie beams at every column-head span, roof rings, a ridge, rafters | all present |
| — | timber standing out through the roof | none |

The roof tools can only make a hipped roof, so "hipped" is not measured. The eyes (`shot-judge`, the
same model) then judge `brief.png`, the photograph above the hall, asked whether it is "the same kind
of building" and told to ignore colour, texture, trees and people. The gate is `adoption.Adoption`
with `look=adoption.BRIEF`; a rebuild's gate is unchanged (`tests/showpiece/test_adoption.py`).

What this cannot say: whether the design is the real Foguang hall piece for piece (nothing it was
given could tell it that), or whether a real building drawn this way would stand.

## The rehearsal

Before any live run, a scripted builder that says exactly the right things drove the real driver,
tools and gate on a small two-bay hall with a brief for itself: every tool ran, the brief check passed,
and the one thing still owed at the hand-over was the eyes, which need a model
(`test_a_scripted_design_runs_every_tool_for_real_and_only_the_eyes_are_left`). Two of the new tests
were broken on purpose and went red (the temple's likeness not refused; the eyes judging the wrong
picture).

## The runs

Run folders: `~/beyond-canvas-design/.studio/showpiece/designs/` on the Spark, one per run, started by
`~/beyond-canvas-design/run-design.sh` (`python -m evalkit.fromzero --brief evalkit/briefs/foguang-east-hall`).

### Run 1 — `20260926-090657-0bb846`: stopped at the column grid, thinking

Not adopted, 2 minutes, 1 action. The builder placed the platform from the brief at once (36 × 19 m
around the 34 × 17.7 m of columns, top 0.5 m, its own choice), then on its next turn — the columns,
where a rebuild copies eight x's and five y's from the survey and a design has to decide them — spent
the driver's whole budget thinking: 6,000 tokens, then the one retry's 12,000, and returned no text. The
driver stops a run that does that. **The first thing designing costs that copying does not is thought.**
Fix before run 2: a design turn may think for 16,000 tokens and retry at 32,000 (`fromzero.THINK`), and
the connection waits 600 s instead of 180; a rebuild keeps 6,000 and 12,000. Also from run 2 on, a design
run keeps the hall after every placing call (`stages/step-N.blend`) and every picture and video by step
(`media/`), which a run otherwise overwrites; the replay needs them.

### Run 2 — `20260926-091244-01a82a`: a whole hall in seven minutes, then stuck under the roof

Not adopted: the cap of 80 actions was reached after 32 minutes and 1,480,194 tokens (28 placing calls,
20 reads, 23 tool calls that failed or were refused, 5 repair laps). It never reached weights, settle,
shake or the brief check: 8 bearing and 4 inventory runs were all it checked.

**What it designed.** From the brief alone, by step 46 (about 7 minutes): a 36 × 20 m platform; 36 columns
6 m tall on an even grid of 34 ÷ 7 by 17.7 ÷ 4 (x = ±17.0 … ±2.429, y = ±8.85, ±4.425, 0), two rings; tie
beams; walls on four sides; 58 bracket sets five tiers high, their top 9.35 m, 2.85 m over 6.5 m columns (the
brief's "about half"); a roof frame, three purlin rings, 360 rafters and a hipped roof topping out at
13.58 m. Every number came from the brief or its own reasoning; no tool measured anything for it.

**Where the actions went.** Three things the harness said badly, each a gap the rebuilds never exposed
because the survey handed over the number:

1. **The frames' own lowest beam.** 12 frames calls were refused with "leaves no room for posts above the
   beam below it (top 9.750)" (steps 14, 16, 24, 26, 60, 84, 88, 113, 133, 151, 153, 155). The beam below
   was the one the tool lays on the seat itself, which the sentence never said; the builder tried beam tops
   9.35, 9.75, 9.76, 9.77, 9.8 and 10.0, read `method.md` seven times and `hall.json` eight, and asked for a
   reference that does not exist. The rule is that beam 1's top must be more than seat + 2 × depth
   (10.15 here). Fixed after the run: the refusal now names the automatic beam and the least top
   (`roof_frame.too_low`, `test_a_beam_too_close_above_the_frames_own_lowest_beam_is_refused_with_the_least_top_it_may_have`, red on the old
   text first).
2. **A stale inventory crashed the bearing check.** After it removed a purlin ring it ran bearing without
   inventory; bearing crashed on the missing piece with a Python `KeyError` three times (steps 58, 64, 96).
   Fix under way: every check that reads `anatomy.json` says to run inventory again.
3. **The ridge's length.** It placed the ridge with `half_x` 0, a ridge of no length between king posts at
   x = ±2.429 and ±7.286; bearing reported it hanging 12 m above the platform, and it concluded a column was
   missing at x = 0 and added a ninth column line (steps 129–139), which breaks the brief's seven bays. The
   one ridge refusal it met (step 121, "the ridge is shorter than the top ring and higher than it") did not
   say what `half_x` is. Fix under way: purlins refuses a ridge no king post stands under, naming the posts
   and the least `half_x`.

Kept for the replay: 28 stage models in `stages/`. No picture was made (no check that renders ran).

### Between runs 2 and 3: three answers made clear, by agents working side by side

Each fix is a sentence the tool now says, with a test that failed on the old code first:

- **frames** (`ce3e95b`): "…the frames lay their lowest beam on the seat themselves, its top at seat + depth
  = 9.35 + 0.4 = 9.75, … so beam 1's top must be more than 9.75 + 0.4 = 10.15".
- **bearing, settle, shake** (`a8e6af6`, `1250563`): an `anatomy.json` older than the hall — pieces gone, or
  pieces added and not counted — is refused in one sentence ("…Run model-anatomy inventory again, then
  model-anatomy bearing.") instead of a traceback or a silent answer on the wrong pieces.
- **purlins** (`caca164`): a ridge no king post stands under is refused, naming where the posts stand and the
  least `half_x`; "shorter than the top ring and higher than it" now says what to give. The frames record
  where they put king posts (`hall.json` `kings`).

Runs 3 and 4 then started 30 s apart on the same code (`b5a3444`), side by side on the Spark; the added-pieces
half of the inventory fix (`1250563`) came after they started.

### Run 4 — `20260926-100206-02bf75`: adopted in five and a half minutes, with a flaw no check measured

**Adopted**: 22 actions (9 placing, 1 read, 5 refused or failed), 0 repair laps, 0 refused hand-overs,
194,880 tokens, 327 s. Every check passed first time: nothing hanging; no column over its timber's limit with
snow and slenderness; 1,659 pieces let go for 3 s, none fell or shifted; the design earthquake and a 0.07 g
pull, nothing came down, drift 0.06 m; the brief check (7 by 4 bays, corner columns 34.0 × 17.7 m apart, two
rings, 36 of 36 column heads with a bracket set, bracket sets 3.07 m on 5.0 m columns = 61 %, 36 of 36 spans
tied, 2 roof rings, a ridge, rafters, nothing through the roof); the eyes on `brief.png`, "pass".

What it chose, none of it given: a 36 × 20 m platform 0.3 m high; columns 5.0 m tall and 0.5 m thick (the real
hall's are 4.99 m and 0.54–0.57 m, Liang Sicheng's survey, which the brief did not contain); bracket sets three
tiers of 0.8 m with 1.2 m reach and a 1.5 m outrigger; a frame with one beam at 9.5 m and a king post to 11.0 m,
the four lines under the sloping ends named at once (it read the corrected instructions); a ridge of half_x 10
after one refusal whose sentence said "give half_x less than 12.143"; 208 rafters; a roof topping out at
12.08 m. Outline 41.6 × 25.3 m against our Blender model's 41.4 × 25.1 m, which it never saw.

**The flaw.** In `brief.png` the bracket-set arms and outriggers at both short ends stand out past the edge of
the roof into open air: it gave the eave ring at the outer columns themselves (half_x 17.0, half_y 8.85) and an
eave-out of 1.5 m, while its brackets reach 3 × 1.2 m plus a 1.5 m outrigger. On the real hall the eaves cover
every bracket set. Nothing measured it — the brief check counts bracket sets and timber *through* the roof, not
timber *beside* it — and the eyes, the same model as the builder, wrote that the picture showed "a matching
long low timber hall with a hipped roof, deep eaves and bracket sets under the eaves". This is the design's
version of rebuild run 2 (adopted with king posts through the roof, the eyes seeing nothing), and it gets the
same answer: a measured check ("timber beyond the eaves"), under way.

### Run 3 — `20260926-100136-abc476`: same code as run 4, checked as it built, out of laps before the roof

Not adopted: "all 6 repair laps are used and the hall still has faults", 45 actions (12 placing, 5 refused
or failed), 517,315 tokens, 684 s. It started 30 s before run 4, on the same code, and took the careful road:
after the columns and ties it ran inventory, bearing, weights, settle and shake on 72 pieces (all passed);
after the walls, the same again (all passed); then the brief check, which failed for want of bracket sets and a
roof. Every part placed after a check opens a repair lap in the gate's count (`adoption.laps_used`), passed
or not, so walls, brackets, frames, purlins and two roof-ring repairs used all six before the hall was done;
its last bearing still found 2 pieces hanging. Its design differed from run 4's too: columns 4.2 m, five
tiers of 0.35 m brackets, an eave ring outside the outer columns (18.5 × 10.35) with 0.6 m eave-out.

**Two runs of one code, two outcomes.** What decided them was the builder's habit, not the harness's code:
run 4 placed the whole hall and then checked it; run 3 checked a half-built hall five times. The rule that
punished run 3 was the gate's and was never said. Fixed after the runs (`8e5a498`): the designer's protocol
now says a lap opens with every part placed after any check, even one that passed, and the placing call that
opens one is told so at once ("(this change came after a check, so it opens repair lap 2 of 6: …)"),
`test_the_driver_says_so_with_the_placing_call_that_opened_the_lap`, red when the driver's line is removed.

### Between runs 3–4 and 5–6

- **Timber beyond the eaves** (`f078ed7`): `likeness.py` `beyond_the_eaves` finds timber above the column tops
  that has no covering over or under it and stands further from the middle than the covering reaches; the brief
  check (and a rebuild's likeness) fails on it in numbers. On run 4's own hall (`stages/step-28.blend`) the
  brief check now says: "240 timber pieces stand past the edge of the roof, with no covering over them: 96
  bracket arms, 96 bracket blocks, 48 outriggers; along the hall they reach 20.8 m from the middle and the
  covering ends at 18.5, and across it they reach 12.65 m from the middle and the covering ends at 10.35: the
  eave ring must stand further out than the bracket sets reach, or the eave-out be longer". So run 4, adopted
  under the checks it ran with, would not be adopted with this one in force — the same verdict the replay gives rebuild run 2.
- **Pieces added and not counted** (`1250563`): the other half of the stale-inventory fix.
- **The lap note** above.

Runs 5 and 6 started side by side on `086c406`.

### Run 6 — `20260926-104547-ed4fad`: adopted with the eaves check in force, a roof open at the hips

**Adopted**: 28 actions (10 placing, 3 reads, 8 refused or failed), 0 repair laps, 295,115 tokens, 547 s. It
placed the whole hall, then checked it once: nothing hanging, columns within their limit, 1,805 pieces let go
and none fell or shifted, 0 came down in the shake (drift 0.06 m), the brief met (bracket sets 70 % of the
column, the brief's upper bound; nothing through the roof and — the new check — nothing past the eaves), and
the eyes passed `brief.png`. In that picture the roof now covers every bracket set, but the covering is **open
at the hips**: dark triangles where the end slopes meet the long slopes. Nothing measures a roof's holes; the
eyes did not mention them. Being looked into: whether the roof tool makes the gap from numbers that are
otherwise valid (a tool fault) or run 6's numbers were impossible (a refusal owed), and a measured "the roof
has holes" check either way.

### Run 5 — `20260926-104517-c5da90`: the first run the eaves check caught, out of laps on a number it undid

Not adopted: all 6 repair laps used, 66 actions (37 placing, 9 refused or failed), 1,077,253 tokens, 1,303 s.
Its first brief check (step 52) found 70 bracket pieces past the eaves; it moved the eave ring and roof and
lengthened the eave-out to 2.0 m, and at step 124 the brief check said "unlike: nothing". On the way it had
put purlin ring 2 at 7.75 m, 0.085 m above the outrigger that carries it at 7.665 m; bearing named it, it
lowered the ring (step 98) and bearing found nothing hanging (step 100). Re-placing the frames later (step
116), it re-sent its older purlin string with 7.75 (step 118), the same piece hung again (step 128), and the
lap that fixed it was the sixth. Every lap was announced as it opened ("…opens repair lap 4 of 6: …"), which
is how the record shows where the six went: two on the eaves the new check found, the rest on the roof frame
and one purlin height it had already fixed once.

### Six runs, one brief

| run | code | ended | actions | tokens | wall | what decided it |
|---|---|---|---|---|---|---|
| 1 | first | stopped, thinking | 1 | 4,861 | 2 min | the column grid took more than 12,000 tokens of thought |
| 2 | + think budget | not adopted, cap | 80 | 1,480,194 | 32 min | three unclear harness answers (frames, stale inventory, ridge) |
| 3 | + three answers | not adopted, laps | 45 | 517,315 | 11 min | checked a half-built hall; each part after a check opened a lap |
| 4 | same as 3 | **adopted** | 22 | 194,880 | 5 min | built, then checked; bracket arms past the eaves, unmeasured |
| 5 | + eaves, lap note | not adopted, laps | 66 | 1,077,253 | 22 min | the eaves check caught it; it undid a fixed purlin height |
| 6 | same as 5 | **adopted** | 28 | 295,115 | 9 min | nothing past the eaves; roof open at the hips, unmeasured |
| 7 | same as 5 | not adopted, refusals | 56 | 781,864 | 21 min | lengthened the eaves, never laid the roof again |
| 8 | same as 5 | not adopted, laps | 57 | 818,301 | 19 min | placed the frames again, never the rafters |
| 9 | + closed hips, open-roof check, stale parts | **adopted** | 23 | 220,092 | 9 min | clean by every check and to the eye |
| 10 | same as 9 | **adopted** | 39 | 470,234 | 15 min | one repair lap; clean by every check and to the eye |

Counts from each run's `scorecard.json` (`python -m evalkit.fromzero` writes it from the run folder).

### Runs 7 and 8 — `20260926-111434-5a805e`, `20260926-111504-8a7211`: the eaves check held, the parts above did not follow

Both on `efad931` code apart from the replay (the same checks as runs 5–6), side by side. Neither adopted.

**Run 7** (56 actions, 781,864 tokens, 1,232 s; stopped after 3 refused hand-overs with all 6 laps used). Its
first brief check (step 40) found bracket sets past the eaves: they reached 18.2 m along the hall, the covering
ended at 18.2. It moved the eave ring out onto the outrigger tips (step 42), then — reasoning correctly that the
eaves had to reach further — lengthened the rafters' eave-out from 1.2 to 1.5 (step 56) and to 2.0 m (step 70).
The brief check still said "the covering ends at 18.2" both times, because the **covering had been laid by the
roof call at step 28 and nothing placed it again**: re-placing the rafters does not re-lay the roof. The builder
worked out that "increasing rafter eave-out did not affect the covering edge", concluded the covering followed
the eave ring, and spent its last laps moving the ring and the outriggers, which only moved the brackets out with
it (18.45, then 18.8 m). With every structural check passing, it tried to hand over three times; the gate refused
each time with the same sentence, and the run was stopped.

**Run 8** (57 actions, 818,301 tokens, 1,136 s; all 6 laps used, 3 pieces hanging). After its brief check
(step 56) named frame beams standing out through the roof at the sloping ends, it placed the frames again,
then the purlins and the roof — five times over — but never the rafters: the old rafters stood on purlins that
had moved, and bearing found purlins hanging over them by 2.5, 2.77, 0.06, 2.15, 0.21 and 0.33 m in turn.

**One gap, two ways.** Placing a part again replaces it, and no tool said which later parts had been built on the
old one: the roof on the rafters (run 7), the rafters on the purlins (run 8). In the rebuilds the survey's numbers
meant a lower part was seldom placed again. Fix under way: a part placed again names every later part that
stood on the old one, and the fault report lists them.

### The roof open at the hips was the roof tool's (`581194d`)

Run 6's dark wedges were not holes but pockets: the end purlins lie on the long ones, so each end slope's
covering sits a purlin's depth higher at the hip, and to hide the end-purlin tips the roof tool stretched every
end sheet flat past the hip at its own height. Where the rings step in unevenly under a long eave (run 6: 3.8 m
along the hall against 6.2 m across it, under a 1.8 m eave) the stretch reached 3.1 m and stood up to 1.01 m clear
of the long slope; from the picture's corner camera the air under it is the dark wedge. The small test hall had
the same defect (0.69 m), and so would the rebuilds' numbers (about 0.44 m). Fixed in the tool: the eave is its
own strip, the sheets meet edge to edge on the hip, and each hip is closed by a cap from the eave corner to the
ridge, as the real hall's hip ridges do; the arguments are unchanged. And a measured finding: `open_roof`
(`likeness.py`) drops rays over the covering's own outline and counts holes and pockets; the brief check and
likeness fail on it. On run 6's own final hall it now says "the roof is open at the hips: 35.04 m2 where one
covering sheet stands up to 0.97 m over another with open air between …"; the same numbers placed with the fixed
tool give a closed roof. So the replay now plays run 6, like run 4, as adopted under the checks of its day and
failed by a check added since — but run 6's fault was the tool's, not the builder's numbers.

### Runs 9 and 10 — `20260926-121601-5c755f`, `20260926-121631-2746aa`: two adopted in a row, clean

Both on the code with every fix above (`00d4cab`: the roof closes its hips under caps, `open_roof` and
`beyond_the_eaves` fail the brief, a part placed again names what still stands on the old one), side by side.
The operator's bar, set after run 6, was two runs in a row adopted with nothing wrong in the picture, looked at
by a person and not only by the eyes, which passed flawed halls in runs 4 and 6.

- **Run 9**: adopted, 23 actions (9 placing, 3 reads, 4 refused or failed), 0 repair laps, 220,092 tokens,
  538 s. Placed the whole hall, then checked it once; everything passed first time, the brief included
  (bracket sets 59 % of the column).
- **Run 10**: adopted, 39 actions (16 placing, 7 reads, 7 refused or failed), 1 repair lap, 470,234 tokens,
  911 s. Bracket sets 56 % of the column.

Looked at (`media/step-44-brief.png`, `media/step-74-brief.png`, and each right-hand hip cropped and enlarged):
the roofs are closed, with a cap along every hip; every bracket set stands under the eaves; nothing stands out
through the roof. Both are recognisably the photographed kind of building — a long, low, seven-bay timber hall on
a platform, two rings of columns, big bracket sets carrying deep eaves under a hipped roof — and neither is the
real hall piece for piece: plain walls in every bay where the real one has doors and windows (no tool makes
them), and a flatter roof than the real one's (the brief said only "gentle").

## What the path shows

Ten runs, one brief, one model. Four were adopted (4, 6, 9, 10); two of those (4, 6) were adopted under the
checks of their day and failed by a check their own flaw led to. Every run that failed found a gap in the
harness, not only in the builder: a thinking budget sized for copying, a refusal that did not say the tool had
laid a beam itself, a check that crashed on a stale inventory, a ridge whose length nobody explained, a lap rule
nobody said, no check for timber beside the roof, a roof tool that left its hips open, and parts left standing on
parts that had been replaced. Each was fixed with a test that failed first, and the next pair of runs went
further. The rebuilds taught the harness how to hold a builder to a measured building; the designs taught it what
a builder with no measurements needs to be told.
