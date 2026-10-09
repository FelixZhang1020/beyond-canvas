# The subject-first lesson line, and the naming judge that refused it

Live runs against real models. What prompted them: 080976d (PR #5, landed shortly
before) changed the class form so the lesson line asks for **what the children are drawing
first** — 「今天画在广场上放风筝」 — because a teacher report that cannot tell what a picture
shows describes the wrong thing. A review of that commit found the same line also reaches the
**child-facing opening**, whose prompt tells the writer to notice it, while the rule 4 judge
("presumes nothing", a red line) was never shown it. This file is the evidence that the risk
was real, that the fix removes it, and what the fixed judge still refuses and still lets by.

## Models

| Slot | Profile | Model |
|---|---|---|
| `vlm.studio` (writes the opening) | `stepfun` | `step-3.7-flash` (StepFun) |
| `vlm.director` (every judge, rule 4 included) | `stepfun` | `step-3.7-flash` (StepFun) |
| `vlm.teacher` (teacher report) | `stepfun` | `step-3.7-flash` (StepFun) |

Chinese classes throughout. Six real colour drawings from `Image Sample/Color Artwork`
(sent to StepFun with the operator's approval, as in [the colour-sample run](colour-feedback-stepfun.md)), and the seven eval fixtures
on both entrances. Scripts and inputs: `scripts/lesson-line-check.py`,
`scripts/naming-probe.py` and the three JSON files beside them (`lesson-lines.json`,
`fixture-lines.json`, `naming-probe-cases.json`). The
checking logic is what ran, but the saved files do not reproduce any single run: they were
tidied afterwards (the check script gained an `entrance` field and lost a debugging `trail`;
the retry on a dropped connection existed only from the last probe on), and the cases file
gathers the cases of four probe runs under the letters used below.

Every run goes through the real `Classroom` → `Conversation` → gates path; `run_rubric` is
wrapped only to keep each attempt's report. An opening gets at most three attempts — one
retry, then a repair — and the last is shown despite ordinary rule failures, but never across a
red line. Model judges vary run to run, so repeats are reported as counts.

## 1. Before the fix: a named subject can cost a child their opening

Colour entrance, each drawing twice: blank lesson line, then a subject line written the way a
teacher would. "1st" means the opening reached the child on the first attempt.

| Drawing (file number) | Subject line | Blank | Subject |
|---|---|---|---|
| 103 night flight | 今天画夜空里骑着独角兽飞过城市，用丙烯颜料 | 1st | 2nd — rule 4: "calls the rider a knight" |
| 135 red ship, bridge | 今天画港口里的雪龙号科考船和跨海大桥，用水彩和油画棒 | 2nd — rule 12 | 2nd — rules 2, 10 (began in English) |
| 87 shark in space | 今天画玩具总动员的太空世界，用丙烯颜料和金箔 | 2nd — rule 4: "gray fish a sea turtle" | 1st |
| 110 fields, village | 今天画从山上看到的田野、小路和村庄，用马克笔和彩铅 | 1st | 1st |
| **120 girl flying kites** | 今天画在广场上放风筝，用马克笔勾线 | 1st, calling the kite "a big red bird" | **stopped, no opening** |
| 75 flamingos, zebra | 今天画非洲草原水边的火烈鸟和斑马，用丙烯颜料 | 1st | 1st |

The kite drawing with its subject, attempt by attempt:

1. "一只红色的大风筝" — rule 4 passed; refused on rules 9 and 12 (the question).
2. Retreated to "一只红色的大鸟" — refused on rule 11: touches nothing of the lesson.
3. "一只红色的大风筝" again — **rule 4: "calls the red winged shape a kite"**. This was the last
   attempt, and a red line is refused even there, so the teacher was shown the gate message
   「出了点小问题。过一会儿再试试这张照片吧。」 and the child got no opening.

Follow-ups on the same drawing: the old technique-style line 「练习冷暖色的搭配」 passed first
time; the subject line twice more passed once first time (hedged: "a red kite that looks like a
big bird") and once on the third attempt, after a rule 4 refusal naming three shapes as kites,
when the writer retreated to "a red shape… a purple shape". Through the real page, with the line
「今天画在广场上放风筝，用马克笔勾线；练习线条的疏密」: three rule 4 refusals — "a kite", "a hot
air balloon", "a kite" — and the teacher saw the same gate message.

**Across three script runs and one page run, rule 4 refused "kite" four times.** The judge
also disagrees with itself: with no line, sentences A and B in section 3 each passed once and
were refused twice, and B had passed rule 4 when it was written live.

The rest read well. No opening named a material from the photograph, and the subject helped:
on 110 the subject version noticed the yellow bands around the fields while the blank version
called fish-shaped clouds "three white birds".

## 2. The fix

`evalkit/rubric/assisted.py`: rule 4's judge is shown the teacher's line (`LESSON_CLAUSE`)
whenever there is one. Naming a shape as what the class was drawing is reading the drawing in
its lesson, not presuming — but not where the drawing shows none of what would make it that,
or plainly shows it as something else. Where the child has also spoken, the child's word
outranks the teacher's line (`CHILD_OUTRANKS_LESSON`). `run_rubric` passes the line to rule 4,
and `studio/gates.py` now passes it on the rung gate too (rule 11 stays skipped there).

The first wording lacked the last two limits. An independent review found both gaps: a reply
saying "bird" back to a child in a kite class could be refused, and a reply calling the child's
bird a kite could pass. The probes below separate the two wordings.

## 3. The judge, probed directly

Three runs per case, same drawing and sentence each time. Sentence A is an opening rule 4
refused live (the follow-up run in section 1). Sentence B is the kite opening from section 1,
step 1, which rule 4 passed live; it is here because with no line the judge refused it two
times in three.

| Case | No lesson line | First wording | Final wording |
|---|---|---|---|
| A: "a big red kite… flower-shaped kites… dragonfly kite" | refused 2/3 | passed 3/3 | passed 2/3 (one refusal: "the purple shape a flower-shaped kite") |
| B: "a big red kite… a dragonfly-shaped kite" | refused 2/3 | passed 3/3 | passed 3/3 |
| C: kite drawing, "a hot air balloon and an octopus" | — | refused 3/3 | refused 4/5 (a dropped connection cut one run to two) |
| D: flamingos called "kites", kite line | refused 1/3 | refused 2/3 | **refused 3/3** |
| E: child said "bird", reply says "bird", kite line | — | — | passed 3/3 |
| F: child said "bird", reply says "kite", kite line | — | — | refused 3/3 |

A third sentence (section 1, step 3) passed 3/3 both with and without the line in the first
probe, so it could not show anything; it is left out. The judge refused A's purple shape as a
"flower-shaped kite" with no line too, so that one refusal is not the new wording's doing. D is
the judge's own leniency, older than this change — flamingos called kites passed two runs in
three with no line at all — and the final wording is the strictest of the three.

## 4. After the fix: the same openings, on the final wording

| Drawing | Subject line |
|---|---|
| 103 night flight | 3rd — rule 9; then rule 4: "the brown blobs at the bottom small houses" (the line said 飞过城市) |
| 135 red ship | 1st |
| 87 shark | 3rd — rule 4 twice, the judge's notes: "a flying craft", "a yellow round ball friend" |
| 110 fields | 1st |
| **120 kites** | **1st — 「我注意到中间有一只很大的红色风筝」**, rules 4 and 11 both passed |
| 75 flamingos | 1st |

Kite repeats: 3rd (rules 12, 11; no rule 4); first; and one that stopped after two judged
attempts — the second refused on rule 4 for "the orange shape in the top left a dragonfly", not
the lesson's subject. Its third attempt never reached the rubric, and the record kept for it
cannot show why: either the model call failed, or the reply came back in English, which the
wrong-language check refuses before the rubric runs. Reading the harness for this found that a
model error on the repair attempt is reported as `rubric_failed` rather than
`model_unavailable` (`studio/harness.py`, the repair branch of `_one`); that defect stands on
the code alone and is filed separately.

**Rule 4 refused "kite" on the kite drawing zero times in four runs, against four before.**

Eval fixtures with a subject line each (`scripts/fixture-lines.json`), including two
deliberately loose ones — 「今天画蜗牛和草地」 on the spiral scribble, 「今天画我最喜欢的玩具球」 on the
blue circle:

| Fixture | Colour | Sketch |
|---|---|---|
| blank-page | refused by safety (blank_page) | refused by safety (blank_page) |
| cat-shaded | 1st | 1st |
| dog-sun | 1st | 3rd — answered in English (refused before grading), then rule 8 ("简单") |
| monster | 1st | shown on the last attempt, rule 12 failing; the first attempt began in English |
| named-drawing | 1st, "a blue circle"; the written name not read back | 3rd — rules 3, 9, 12, then 2, 3, 9, 12 |
| scribble | 1st, "curling lines… like a little tunnel", never "a snail" | 1st — **「橙色螺旋线构成了壳的基本形态」**, rule 4 passed |
| sphere-study | 1st | 3rd — rules 2, 10, then 2 |

No fixture opening, on either entrance, was refused on rule 4. **The one result that cuts the
other way:** under the loose snail line, the sketch opening called the spiral "a shell", and
rule 4 let it by. A spiral with nothing else of a snail is close to "shows none of what would
make it one". There was no run of that fixture without the line, so it cannot be put down to
the fix; it is the case to probe first if rule 4 is ever found too lenient under a lesson line.

## Also found

- **The lesson box never showed its example.** The textarea held ten spaces between its tags
  from 80fbf63d on, so the placeholder — the subject-first example included — never
  appeared on a fresh class. Fixed in f6b4caa with a page check; found by driving the real page.
- **The form and the teacher report work.** Through the page: the new question, example and
  hint in both languages; the line saved with the course, shown in course info, editable
  mid-class. The teacher report on the kite drawing named 「广场放风筝的场景」 and took up 疏密
  from the edited line.
- **English slips into Chinese openings with a subject line.** At least 9 of 51 attempts under
  a subject line began in English (one refused before grading and absent from the attempt
  records), against 0 of 9 without one. The gates catch them at the cost of a retry. Too few
  attempts without a line to call it caused by the line; worth a targeted run.
- **Rule 12's Chinese process markers miss real process questions.** Refused on the sketch
  entrance: 「你在画的时候是怎么决定人物和狗的大小的？」 and 「你画的时候是怎么想到给怪兽加尖牙的呢？」.
  The keyword-list limitation recorded earlier, still open.

## Cost

Not metered per run here. From the per-attempt costs the class ledger records for these
openings (about $0.011–0.017 an attempt, rising with retries), the whole exercise — 41 script
openings (59 graded attempts), one page opening and one teacher report, and 48 direct judge
calls — is an estimate of about a dollar.
