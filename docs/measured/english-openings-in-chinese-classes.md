# Chinese openings that began in English, and the two words that stopped it

While checking the subject-first lesson line
([lesson-line-and-naming-check.md](lesson-line-and-naming-check.md)),
at least 9 of 51 opening attempts under a subject line began in English — "I notice 画面里…",
"I see a purple circular face…" — against 0 of 9 without one. That comparison is from a
different corpus, and its second arm is 9 attempts; the A/B below is the measurement. Every
recorded one began with the words both opening prompts named as the opener, in English only:
「Open with a plain observation: "I see" or "I notice"」 on colour, 「begin it with "I see" or
"I notice"」 on sketch. The gates caught every one — no opening that began in English reached a
child — but not always for the price of a retry: one such attempt was a third of a beat that
ended with no opening at all, and another cost a wrong-language rejection and a further
refusal. A retry is also shown the English sentence quoted back in the refusal. This file
measures the cause and the fix.

## Models and method

`vlm.studio` on the `stepfun` profile: `step-3.7-flash` (StepFun). Writer only — the skill's own
`write_feedback`, exactly what a first attempt calls, with no judges — because whether an
opening begins in English is visible in its text. Six real colour drawings from `Image
Sample/Color Artwork` (sent to StepFun with the operator's approval) and three sketch fixtures
(`cat-shaded`, `monster`, `sphere-study`). Three lesson-line conditions per drawing: blank, the
subject line a teacher would write, and a technique line (「练习冷暖色的搭配」 on colour,
「练习明暗与结构」 on sketch). Conditions are interleaved within each repetition, so drift over
an arm hits all three equally — but the three arms below ran one after another (baseline, then
each candidate), not interleaved with each other. A call that failed five times on a rate limit
was left out and filled in by a rerun; counts are deduplicated on drawing, condition and
repetition, so a refilled call counts once. Script and inputs:
`scripts/english-openings-ab.py`, `scripts/english-openings-variants.json`,
and the lesson-line files beside them.

## 1. The lesson line that triggers it is the subject

Five runs per drawing and condition, prompts as they were before the fix:

| Lesson line | Colour (6 drawings) | Sketch (3 fixtures) | Began in English |
|---|---|---|---|
| Blank | 0 of 30 | 2 of 15 | **2 of 45** |
| **Subject** | 8 of 30 | 4 of 15 | **12 of 45** |
| Technique | 2 of 30 | 0 of 15 | **2 of 45** |

All sixteen began "I see" (8) or "I notice" (8). A subject line makes it about six times as
likely; a technique line does not; and it is not only the lesson line — two sketch openings
with a blank line did it too. The cause the numbers point at is the opener itself: the prompt
names the first words in English and nowhere in Chinese, and a line of Chinese scene words at
the end of an English prompt makes the model reach for them.

## 2. Two candidate fixes, one variable each

Each candidate rewrote the prompt in memory, never the skill's files; blank and subject lines,
five runs per drawing, 90 calls each:

| Prompt | Blank | Subject | Began in English |
|---|---|---|---|
| Before the fix (from section 1) | 2 of 45 | 12 of 45 | **14 of 90** |
| **Opener named in Chinese**: `"I see" or "I notice" (in Chinese, 我看到 or 我注意到)` | 0 of 45 | 0 of 45 | **0 of 90** |
| "Reply in Chinese and in nothing else." repeated at the very end | 2 of 45 | 7 of 45 | **9 of 90** |

The first removes it: 64 of its 90 openings began 我看到 and 24 我注意到, and none carried the
instruction's own words into the text. The other two were sketch refusals of the `monster`
fixture as a digital image, which the unfixed prompt does too, at rates this measurement was
not designed to compare and does not report. Repeating the language instruction barely helps, and on blank colour
lines it did worse than no change (2 of 30 against 0 of 30).

## 3. The fix, as shipped

`skills/art-feedback/assets/prompts/colour-opening.txt` rule 2 and `sketch-opening.txt` rule 1
now carry exactly the measured wording. `tests/test_feedback_script.py` checks that a Chinese
class's prompt names at least two of the openers rule 2 accepts
(`evalkit/rubric/lexicons.py`), so the prompt and its grader cannot drift apart; it failed on
both entrances before the edit. The replies and rungs name no opener and are unchanged.

Run again against the edited files, not the in-memory rewrite:

| Class | Calls | Result |
|---|---|---|
| Chinese, subject line, 9 drawings × 2 | 18 | 0 began in English; 10 began 我看到, 8 我注意到 |
| English, blank line, 9 drawings × 3 | 27 | all English, no Chinese character anywhere; 23 began "I see" or "I notice", 4 were sketch refusals of two fixtures (`cat-shaded`, `monster`) as digital images |

And through the real class code — safety screen, opening, every gate — the seven eval
fixtures with a subject line on both entrances, Chinese:

| Fixture | Colour | Sketch |
|---|---|---|
| blank-page | refused by safety, as it should be | refused by safety |
| cat-shaded | 1st attempt | 1st |
| dog-sun | 1st | 1st — three attempts before the fix, the first of them in English |
| monster | 1st | shown on the last attempt, rule 12 failing each time |
| named-drawing | 1st | 2nd — rule 12 |
| scribble | 1st | **stopped, no opening** — rule 12 three times |
| sphere-study | 1st | 3rd — rule 12 twice |

No attempt on either entrance began in English. What remains is rule 12's marker list, which
refused 11 of 23 sketch questions across these runs and once cost a child an opening
altogether; that is measured and fixed separately in
[rule-12-questions.md](rule-12-questions.md).

## Cost

Not metered. 360 writer calls were recorded (135 + 180 + 45), plus the classroom sweep, and the
ledgers these runs wrote hold no writer-only row to price them from, so no figure is given here.
A classroom opening — writer plus every judge — ledgers at $0.011–0.017, which is an upper
bound on a writer call, not a measurement of one.
