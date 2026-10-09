# Rule 12 refused the question it asks for, fourteen times in seventy-four

Rule 12 is the rule about the closing question: on the colour entrance it
must reach inside the picture, on the sketch entrance it must ask the student about their own
work. It decided by marker list — a list of Chinese and English words a good question was
expected to contain. Across one day's live runs it graded 78 closing questions and refused 18;
of those, 75 and 15 carry a question that can be read back (three refusals were of an opening
with no question in it at all, which is a different fault). **Fourteen of the fifteen were
exactly the question the entrance asks for**, and one run ended with no opening for the child,
because a third refusal ends the beat.

The lists were widened on five occasions over two earlier days — five commits, some
carrying more than one widening — each time by a question a person would pass.
`entrance-live-run.md` recorded the limitation rather than solving it and named the
two options — a judge fallback, or measuring the rate — as the operator's call. The operator
chose the fix.

## What was refused

| Entrance | Question | Asks what the entrance wants? |
|---|---|---|
| sketch | 你在画的时候是怎么决定人物和狗的大小的？ | yes — how they decided the sizes |
| sketch | 你画的时候是怎么想到给怪兽加尖牙的呢？ | yes |
| sketch | 你在绘制时是如何决定嘴巴位置和形状的？ | yes |
| sketch | 你在画尖牙时是怎么决定它们的大小和倾斜角度的？ | yes |
| sketch | 你是怎么确定眼睛之间的间距的？ | yes |
| sketch | 你在画这个球的时候是怎么考虑明暗关系的？ | yes |
| sketch | 你画这些同心线条的时候，是怎么控制每一圈间距的呢？ | yes |
| sketch | 你在画螺旋时是怎么决定开口的位置和大小的？ | yes |
| sketch | 你是怎么确定光源方向的？ | yes |
| sketch | 你在画这幅画时，是怎么决定高光的具体形状和大小的？ | yes |
| sketch | 你在画这个怪兽时，最想要传达的是什么感觉？ | **no** — asks what they meant, not what they did |
| colour | 这座桥的那边有什么？ | yes — inside the picture |
| colour | 广场上的人在看什么呢？ | yes |
| colour | 它翅膀里带着什么呢？ | yes |
| colour | 广场上的风从哪边吹来呢？ | yes |

Nine of the eleven sketch refusals ask 怎么 or 如何 with a verb of deciding — 决定, 确定, 考虑,
控制 — a tenth uses 怎么想到, and the list held 怎么画 and none of those. A sixth widening would
have to guess the seventh.

## The fix

`evalkit/rubric/loop.py`: the marker list stays as the fast path and nothing reaches a model
while the words are familiar. When no marker matches, and only then, the question goes to the
same director model the other judged rules use, with one prompt per entrance. A judge that
cannot answer leaves the markers' verdict alone, so an outage cannot turn the rule off. Without
a client — offline, and in every test that supplies none — behaviour is exactly as before.

`run_rubric` now forwards its client into the opening rules, so the judge is reachable on every
beat that grades a question — the rung included. `studio/gates.py` is unchanged: it already
handed its director to the rubric, and a rung wrongly refused costs the child the same answer
an opening does.

The judge runs in line rather than in the pool that holds the other judged rules. On a marker
miss that adds one round trip to that attempt; on the other four questions in five it adds
nothing. Pooling it would hide the wait behind rules 3, 4 and 14, at the cost of making the
order of a beat's model calls depend on thread scheduling.

## The same questions, judged live

Every question the rule graded in those runs, put back through it with `step-3.7-flash` on `stepfun`
as the judge (`scripts/rule-12-probe.py`, corpus from the same runs):

| | Markers alone | Markers, then the judge |
|---|---|---|
| colour, 51 questions | 47 pass, 4 refused | **51 pass, 0 refused** |
| sketch, 23 questions | 12 pass, 11 refused | **22 pass, 1 refused** |

The judge is asked only where the markers refuse, so this table can move a question from
refused to passed and never the other way: it measures false refusals removed, not accuracy.
Nothing the markers passed was re-examined — see "What this does not fix".

The probe's corpus is one question short of the 75 above: a colour question the markers passed
「如果你站在下面的城市里，你会听到什么声音？」 did not reach it. Every refusal is in, so only the
colour denominator moves — 51 of the 52 that entrance offered.

The one still refused is 「你在画这个怪兽时，最想要传达的是什么感觉？」 — the question in the table
above that is not about process. The judge and a person agree on it.

## Through the real class code

The seven eval fixtures on the sketch entrance, each with a subject lesson line, before and
after the fix:

| Fixture | Before | After |
|---|---|---|
| blank-page | refused by safety | refused by safety |
| cat-shaded | 1st attempt | 1st |
| dog-sun | 1st | 1st |
| monster | shown on the 3rd, rule 12 refusing all three | **1st** |
| named-drawing | 2nd, rule 12 | **1st** |
| scribble | **stopped, no opening** — rule 12 on all three, and the middle attempt was a "this is a digital image" reply that failed rules 3, 9 and 11 as well | **1st** |
| sphere-study | 3rd, rule 12 twice | **1st** |

Six openings, six first attempts, and the judge was asked in three of them. The other three
matched a marker and cost nothing.

## The judge is not a rubber stamp

Four questions that should be refused, three live runs each
(`scripts/rule-12-negatives.py`). Two of them miss the markers and so reach the
judge; it upheld both refusals every time:

| Question | Reaches the judge? | Refused |
|---|---|---|
| sketch: 「石膏后面住着谁呢？」 — who lives behind the plaster, a story on the sketch entrance | yes | 3 of 3 |
| colour: 「你用的是什么颜料和画笔？」 — which paints and brushes, the artifact not the world | yes | 3 of 3 |
| sketch: 「你这幅素描画的是哪个石膏像？」 | **no** — see below | 0 of 3 |
| colour: 「这幅画你打算取什么名字？」 | **no** | 0 of 3 |

## What this does not fix

The markers are loose in the other direction too, and the judge never sees those, because it
is asked only when no marker matches. The last two rows above pass the list outright:

- sketch: 「你这幅素描画的是哪个石膏像？」 — asks which cast it is, not what the student did. The
  list holds 哪个.
- colour: 「这幅画你打算取什么名字？」 — asks what the child will name the drawing, which is the
  artifact, not the world inside it. The marker that lets it through is 打算.

Both were already passing before this change, and both are deterministic: the same three runs
compute the same answer, so the three prove repetition rather than sampling. Closing them means
asking the judge on every question rather than only on a miss — one model call per opening
instead of roughly one in five — which is a cost decision, not a code one, and is the
operator's.

## Cost

One extra judge call per question whose words are unfamiliar, and none otherwise: 3 of 6
openings in the sweep above, 15 of 74 in the probe. Not metered separately here — the ledger
prices a whole stage, not one judge — so the rate is a fifth of a call per question and the
money is whatever a judge call costs.
