# A clip's description the check keeps refusing

**Question.** Teachers pressed 重新生成描述 again and again on one painting and every press ended on
"草稿复核未通过…请重新生成并通过复核后再确认", with 确认 locked. Can a rewrite get past the check, and
if not, what should a press end on?

**The painting.** A nativity scene (drawing `305d7ec55413`): a pink castle, a stable, three robed
figures with camels on a golden dune under a night sky. The child's confirmed words include "那些人把礼物
给了马棚里的人，并且亲吻了他" and "非常的开心，发出了耀眼的光芒".

## What was measured (on the Spark, Qwen3.6 with thinking off as both writer and check)

| Replay | Result |
|---|---|
| The description teachers saw refused, checked again under the check's rules as they stand | refused 5 of 5 |
| The same, with a sentence telling the check that leaving something out is not a conflict | refused 5 of 5; not adopted |
| One press writing up to three times, each try told the last refusal and its notes | passed in 1 round of 4 |
| A description built from the child's words (the gift, the kiss, the glow), rules as they stand | passed 1 of 5 |
| The same, with a sentence saying the child's own story is never an invented visible fact | passed 0 of 5; not adopted |
| A deliberately wrong description (daytime, green grass, a tower, five horses, a car), either rule | refused 5 of 5 each time |

The check refuses the wrong description every time, so it is not asleep. But on this painting it
also objects to almost anything, often mistakenly: asked about a description that said "左侧是粉色城堡"
it answered "原图中左侧的建筑物是粉红色的城堡，并非褐色", objecting to a colour the description never gave
the castle. Changing its instructions moved which objection it raised, not whether it raised one.

## What the studio does since

One press writes the description up to three times and stops at the first the check passes. If the
third is still refused, the teacher gets it in the box with the check's notes as advice, a sentence
saying so, and 确认描述，生成动画 usable. No red failure line, no lock
(`studio/conversation/drafting.py` `SCENE_TRIES`, `studio/page/src/29a-creation.js`). A storybook's
draft is unchanged. The clip is still screened after it is made, as every clip is.

**Replay method.** Read-only against the node's Portfolio: the drawing and its dialogue rebuilt from
its activities, the check's system text taken from `drafting.REVIEW_SYSTEM` with the clause swapped,
five calls per case. Nothing was written to the Portfolio.
