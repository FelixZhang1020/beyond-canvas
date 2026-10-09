# A night of 2D to 3D on the Spark

**Question.** On every sample drawing, how good is the studio at turning a drawing into something in three
dimensions, and do the obvious fixes help?

**Setup.** A runner on the node (`~/spark-tests/overnight`, not in this repository) put every sample through
the class's own code: 68 colour paintings through `painting-to-figure`, 8 pencil sketches through
`sketch-to-3d`, and 41 Wan 2.2 clips through `painting-to-animation`, in its own copy of a given commit, six
figures at a time and one GPU job at a time. It paused while a class worked and stopped at 07:30. Each result
was scored 1 to 5 by Step 3.7 Flash against the drawing, twice, with one fixed question held apart from the
code under test. 10 h 41 min in all; 819 figure attempts, 447 toys scored, 41 clips, 15 sketches.

## The measurement moves more than the fixes did

The same commit (1444e0a), run six times through the night:

| Run began | 20:53 | 03:36 | 04:19 | 05:03 | 05:46 | 06:29 |
|---|---|---|---|---|---|---|
| Shown | 26 of 62 | 37 of 68 | 34 of 68 | 33 of 67 | 41 of 67 | 32 of 68 |
| Likeness | 3.00 | 2.77 | 2.85 | 3.00 | 3.09 | 3.03 |
| Poor shown (≤ 2) | 5 | 12 | 11 | 7 | 7 | 7 |
| Median seconds | 159 | 158 | 155 | 145 | 153 | 137 |

Nothing changed between them. The share shown swings 42% to 61%, and poor-shown more than doubles. The look
check's inconsistency on borderline toys (recorded in [painting-to-figure.md](painting-to-figure.md)) is the likely cause and is not fixed by
judging twice. **No fix measured once can be called proven against that spread.**

## The six fixes, each measured once

| Change | Shown | Likeness | Median s | Poor shown |
|---|---|---|---|---|
| Join each creature's parts (5bbd805) | 36/68 | 3.14 | 172 | 6 |
| Rewrite sees the failed toy (766727a) | 38/68 | 2.88 | 149 | 12 |
| Figure slot at low reasoning effort (c7d2fcb) | 38/67 | 2.95 | 134 | 7 |
| Three writings instead of two (8403b91) | 46/68 | 3.04 | 184 | 8 |
| Writer's instructions in Chinese (25d8ebf) | 33/68 | 2.94 | 200 | 6 |
| Writer and look check in Chinese (7349aef) | 35/68 | 2.91 | 172 | 7 |

Only three writings (46) sits above the repeat band, by 5. Everything else is inside it.

## Chinese instructions, asked for by the operator

Step 3.7 Flash and Wan 2.2 are both Chinese models, so the instructions were translated faithfully (field
names left English, the judge left English) and measured.

- **Figures:** both Chinese rounds landed inside the luck band; the writer-only version was 26% slower
  (200 s against 137–159 s). Answers lost to format stayed at 6, so Chinese did not make the format safer.
- **Clips:** worse. The same six paintings gave 6 of 6 shown in English and 3 of 6 in Chinese, the three
  lost held back by the hand-and-tool check. The corgi clip scores 5.0 in English and was held back in Chinese.

## Clips

41 clips, 734–776 s each. In English 31 of 35 were shown, likeness 4.0 to 4.88 by batch — the strongest part
of the studio. One clip was shown that should not have been: painting 96 (a house by a canal, no animals)
came back with dark shapes entering from the bottom in frames 2 to 4, which the likeness judge read as hands
or added animals and scored 2. The standing action asked for "one foreground animal" because the child said
nothing, and that painting has no animal.

**The hand-and-tool check is not blind; it is inconsistent.** Asked again on that same clip the next morning
it found hands three times out of three ("hands" with "tools" twice, with "people" once). Asked three times
each on clips the night had passed, it cried wolf twice in nine (c112 and c087, both clean to the eye and
scored 5.0 by the judge). A second look on every clip would therefore hold back good clips more often than
it would catch a bad one; the answer to painting 96 is to stop asking for an animal that is not there.

## Sketches

All 8 came out on every run: the four geometry sketches as clean solids (5 of 5), heads and fruit through
TRELLIS.2. Likeness 4.25 and 4.31. Nothing to fix.

## Why figures are held back

Of the 36 held back in the first run: eyes missing on a main character (the commonest), crowded scenes where
the writer is told to build at most three subjects and the check then asks for the rest, about 6 lost to
format alone, and abstract paintings with no subject to build.

## What changed because of this run

- **The reader keeps what arrived.** Of 75 answers the night threw away, 14 were simply cut off mid-part, 24
  named a colour the list lacked (lavender, peach, light blue, dark_brown, lightgray, medium blue), whole
  answers wrote colours as three numbers from 0 to 1, and small parts came as 0.005 against a floor of 0.01.
  With those four repairs **60 of those 75 answers now read** (`test_an_answer_cut_off_mid_part_keeps_the_parts_that_arrived`,
  `test_the_reader_takes_the_colour_names_the_model_actually_writes`, `test_a_colour_written_as_three_numbers_is_read`,
  `test_a_part_as_small_as_an_eyelash_is_kept`). A colour is still a closed list; free text never becomes one.
- **The clip's standing action names nothing that might not be in the painting**
  (`test_a_clip_with_no_words_from_the_child_asks_only_for_what_is_already_painted`).

## Not settled

Whether any of the six fixes helps. The next run should measure each one three times, alternating with the
unchanged commit in the same hours, and compare only against a run from the same part of the night.
Three writings was measured that way on a later night and adopted ([figure-three-writings.md](figure-three-writings.md)).
