# painting-to-figure on the four colour samples

**Question.** Can Step 3.7 Flash make a 3D toy figure of a colour painting that a teacher would show a child,
and does the studio hold back the ones it should not show?

**Setup.** StepFun First on the subscription (`https://api.stepfun.com/step_plan/v1`): `vlm.creation` writes
the parts and runs the look check, `safety.image` screens the painting and the preview, both
`step-3.7-flash`. Run through the real classroom — `Classroom(profile="stepfun")`, a colour class,
`request("painting-to-figure")`, `run_request`, `follow` — from a scratch driver on the Mac, the four
paintings in parallel, one class each. No GPU is involved. Paintings are from `Image Sample/Color Artwork/`
and went to Step 3.7 Flash as in any class; the previews stay on this machine and none are committed here.

## Results

| Painting | Outcome | Writings | Parts | Seconds |
|---|---|---|---|---|
| 114 · dog beside a house | shown | 1 | 30 | 140 |
| 112 · corgi and dog house | shown | 1 | 36 | 136 |
| 69 · savanna animals and a tree | shown | 1 | 98 | 198 |
| 87 · shark, rocket and turtle in space | held back (`figure_held_back`) | 2 | 41, then 62 | 254; 261 on the logged re-run |

Three of four were shown on the first writing, each passing the safety screen on its preview and the look
check. Each is recognisably the painting's subject as a toy of simple solids: the corgi white with brown
ears, black eyes and a pink tongue beside a blue house with a purple roof, red door and a sign; the savanna
a spotted giraffe, a striped zebra and a tree on a brown floor.

**The shark was held back, which is the right answer.** The painting floats everything in space; settled
onto a base, the swimming shark stands on its tail. On the logged re-run both writings were readable and
passed the safety screen, and the look check refused both: first *"Shape the gray animal like a shark with a
big toothy smile, and add the smiling yellow character on the left"*, then that the shark, rocket and turtle
were not recognisable. The first run was held back after two writings as well, without reaching the look
check; that run was not logged, so whether the reply was unreadable or the preview was refused is not
known. Either way nothing was shown.

The earlier prototype (same prompt, direct calls) gave the same split: dog, corgi and
savanna passed, the shark was held back by the look check.

## What changed because of this run

- **The preview's base is painted first.** Sorted together with the parts, the base's top cut a painted
  floor into light and dark wedges, and that picture is what the safety screen and the look check were
  shown. Nothing sits below the base, so it is now drawn before anything is sorted
  (`test_a_painted_floor_is_drawn_over_the_base_not_cut_into_wedges`). The viewer the child sees uses a depth
  buffer and never had the fault.

## Known limits

- Tiny details can hover. Settling folds a group under 3% of the figure's volume into its nearest
  neighbour and moves it with that neighbour, so a cheetah's spot drawn beyond its body stays in the air
  beside it. The look check passed the savanna with two such spots.
- Scenes whose subject floats — space, sea, sky — settle badly, because everything drops onto the base. The
  check catches the result; it does not fix it.
- About two to three minutes a figure on the subscription, most of it the model's hidden reasoning; the
  page's typical wait was set to 180 s here, and to five minutes after the Spark runs below.

## Twelve paintings on the Spark

The Spark's own classroom code (`Classroom(profile="stepfun")` on the node, the other session's deployed
version, which carries this feature), twelve colour samples, six at a time; every call timed and every check
picture kept on the node under `~/spark-tests/figure-test/`.

| Outcome | Paintings |
|---|---|
| Shown, first writing (106–154 s) | 7 — corgi 112, dog 114, savanna 69, 84, 96, 100, 136 |
| Held back by the look check after two writings | 3 — shark 87 (read as a seal), sea scene 124, zoo 78 |
| Answer unreadable twice | 1 — 118; readable on a re-run, then fairly held back (no dinosaur, no kites) |
| Model call timed out | 1 — 72; on a re-run shown after its second writing |

- **The time-out was a defect.** The chat client's limit was a fixed 180 s; writings measured 61–151 s with
  two running, and six at once pushed the second writing of 72 past it. The limit is now a slot option, and
  the figure has a slot of its own, `vlm.figure`, with 360 s; the scene and story drafts on `vlm.creation`
  keep 180, because a hung draft holds the class until it ends
  (`test_the_figure_writer_has_time_for_its_slowest_measured_writing_and_drafts_keep_three_minutes`).
- **The look check asked for something a toy cannot do.** On the zoo it first asked for "the word ZOO". Its
  second toy showed the giraffes, lion, building and birds; the check asked for eyes on the birds, and the
  re-judge below shows the giraffes, main characters, had none either — so under the rule kept below that
  hold-back was fair. The sea scene and the shark were held back fairly.
- Counting the re-runs, 8 of 12 were shown; crowded scenes (sea, space, zoo) are where it holds back.

## The look check, relaxed and re-judged

**Operator decision:** the check never asks for writing, and wants eyes only on the main
characters' faces, not on small background figures. To measure it, the seventeen toys the Spark's check saw
were judged again from their saved check pictures — the old wording and the new, twice each, the same call
`figure.look` makes — so the wording is the only difference.

| | Old wording | New wording |
|---|---|---|
| Passes, of 34 judgements | 13 | 17 |

- 84 and 96, both shown on the Spark, failed twice under the old wording and passed twice under the new.
- The zoo's second toy still fails under the new wording — its giraffes, main characters, have no eyes.
- **The check is not consistent.** The same picture with the same wording got different answers on repeat
  for the dog, the corgi, a zoo toy and a shark toy; which borderline figure is shown is partly luck. One
  shark toy that looks like a seal passed once under the new wording.
- **Operator decision: two looks, both must pass.** Because the verdict on the same toy changes on
  repeat, a figure is shown only when two independent looks pass it. A first fail decides alone and costs
  no extra look; a figure whose first look passes and second fails is rewritten, so one held back after two
  writings can have cost up to four looks. A shown one costs about 15 s more. Not yet measured on the Spark.
- **The final design, measured (Mac, main's code, same twelve paintings, six at a time):** own slot, relaxed
  check, two looks. Shown 7 of 12 — 84, 87 (a real shark this time: fins, teeth, in a blue sea beside the
  rocket and turtle), 96, 100, 112, 114, and the zoo 78 on its second writing — in 110–236 s, the zoo 402 s.
  Held back: 69, 72, 118, 124. One (136) lost to a dropped connection to StepFun after 5 s, reported as the
  model being unavailable.
- **Three of the held-back were thrown away for format alone.** Second writings wrote colours as words
  ("orange" 27 times, "black" 55), left four characters after the JSON, or gave a sphere one size number.
  The reader now takes common colour words (a fixed list; any other word is still refused), ignores what
  follows the JSON, and reads one size number as the same every way
  (`test_a_rewrite_that_loosens_the_format_still_reads`). All three answers read with it: 91, 62 and 42
  parts. Whether their figures would have passed the looks was not measured.
- **The final design on the Spark itself** (main 40bc2a0 deployed; the Spark's classroom code on the
  node, NVIDIA's safety model now looking at every preview on the way out, twelve paintings, six at a
  time): **shown 8 of 12** — 78, 84, 87, 96, 100, 112 (after one rewrite), 114, 136 — in 126–247 s. Held back
  4, each by the look check with a real miss: 69 (the cheetah's tail), 72 (the lions), 118 (the dinosaur),
  124 (a main character's eyes). Every answer read; every preview passed both safety screens, NVIDIA's
  included. The page's usual wait for a figure is now five minutes (was three), since three of the eight
  shown took longer than 180 s.
- One call in the first attempt at this re-judge returned nothing after spending all 8000 tokens on hidden
  reasoning; in a class that reads as the model being unavailable. `LOOK_TOKENS` is now 16000
  (`test_the_look_check_gets_room_to_think`).
