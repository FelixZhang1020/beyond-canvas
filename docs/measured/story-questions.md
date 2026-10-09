# Story questions in the colour chat

**Question.** The operator found the companion's follow-up questions in 聊聊你的画 "very
stupid": after a child said the ship was sailing to the South Pole, it asked what kind of snow
there would be, and then how the ship would get past the icebergs. They asked for questions
that get the child telling the story of their own picture. Does asking for the next part of
the story, and never a small fact, change what the companion asks?

**Change.** `skills/art-feedback/assets/prompts/colour-reply.txt`, rule 5: a story has four
parts (who and what is happening; why; what happens next; how it ends); the reply finds the
first part not yet told and asks for it, growing out of what the child just said; never a small
fact (what kind, what colour, how many, how long, how one action is done). A first try at the
same story wording in the opening made three of seven opening questions worse (two offered a
choice of two ready-made answers, one invented a trip), so the opening was left alone at first;
it was then changed on its own (below).

**Method.** Seven saved colour conversations on the Spark (the ship class and six showcase
classes), the first two or three child answers in each: 20 replies. At each point the class
writer (Qwen3.6-35B-A3B, thinking off, through the front voice) wrote the next reply twice
from the same drawing, opening and conversation so far: once with the old prompt, once with
the new. Writer only: the classroom's gates, which refuse or rewrite a closed question or an
invented motive, were not run, so these are first drafts. One run each side.

| 20 replies | old | new |
|---|---|---|
| Question ends in 吗 (yes or no) | 8 | 1 |
| Small fact (什么样, 什么颜色, 多久, 怎么接/穿/找/瞄) | 2 | 0 |

Read one by one, most new questions ask for the next part of the story:
"到了那里之后，船上的人打算做什么呢？", "它们吃完早饭之后，接下来去哪里了呢？",
"他买完面包回来之后，会把面包分给谁呢？", "那士兵被吓到之后，接下来发生了什么呢？".
The old ones of the same turns asked "这罐橘子酱，是好朋友最喜欢的味道吗？",
"小篮子里的胡萝卜蛋糕是什么颜色的呢？", "它们打算怎么把门撞开？".

Four new drafts still fail, each in a way the classroom's gates already refuse and rewrite:
two 是不是 questions carrying a purpose of their own ("是不是为了照亮它们分蛋糕的地方？"),
one 吗 question offering a reason ("是因为外面太冷了吗？"), and one that treats the mice's
plan as done ("大炮轰开了城堡的门之后"). "接下来发生了什么" recurs across drawings;
within one conversation the questions vary.

## The opening: the child says what they drew first

**Question.** With the story questions live, the operator found the first question "very
subjective": it read the picture for the child ("这艘船正准备开往哪里呢？", "你觉得城堡里的人
正在为哪一个特别的节日做准备呢？"). The child should first say what they drew, and the
questions after build on that.

**Change.** `colour-opening.txt`: one or two plain sentences about what is visible (colours,
shapes, how many, where), no guess at what is happening or what anything means, and a closing
question that invites the child to tell what they drew. Rule 12 refused exactly that question
on every opening, so a colour opening, and only an opening, now passes when it asks what was
drawn (`rule_12_opening_hands_over_the_picture`); "这是什么" still fails, replies and the silent
child's smaller questions keep the world rule. The fallback line became "我看到你的画啦。跟我说
说，你画了什么呀？".

**Method.** The same seven drawings, the class writer as above, each opening written once with
the old prompt and once with the new, and the new one graded by the classroom's rubric as
changed (every rule, with the picture and the judging model).

| Seven openings | old | new |
|---|---|---|
| Reads a meaning or an event into the picture | 7 | 0 |
| Passes every rule of the classroom's rubric (new rubric) | n/a | 7 |

Old: "让这只熊看起来像是世界的中心。你觉得它手里提着的那个棕色的箱子，里面装着什么？"
New: "我看到蓝色的外套，红色的帽子，还有黑色的线条。跟我说说，你画的是什么？"
Every new opening ends in nearly the same question; that is the change asked for. One said
"蓝色的山和白色的房子" for a picture whose blue is mostly a river; the rubric's grounding judge
passed it.

## Asking until the story ends, and saying each thing once

**Question.** On the class page a reply said the child's party and penguins three times over,
worded three ways, and asked nothing (operator: "it stopped ask, on purpose?"). Ten replays of
that exact moment never repeated it, so the repetition is rare, and nothing in the classroom's
checks caught a sentence said again in other words. The reply rule had allowed no question "once
they have told their whole story", and a party read as an ending.

**Change.** The colour reply now allows no question only once the child has said in their own words
that the story is over (然后他们就回家了, 完了, the end); a party, a place or a sight is the middle.
It ends with a question about the newest thing said, in words no earlier question used, since a
bare "然后发生了什么" turn after turn sounds like nobody listening (a first version that offered that
phrase as a fallback made three questions of one conversation versions of it). And
`chat_beats._said_once` now drops a statement made mostly (60%) of an earlier sentence's character
pairs, the class page's triple shared 68% and 100%; a question is never dropped.

**Method.** The same seven conversations plus the class page's own, 24 replies, live prompt against
the new one, writer only.

| 24 replies | live | new |
|---|---|---|
| No question at all | 0 | 0 |
| A sentence said twice (new check) | 0 | 0 |
| Bare "what happens next" | 1 | 0 |
| Ends in 吗 (yes or no) | 3 | 1 |
| Small fact | 3 | 0 |

At the moment that went wrong the new reply asks "开完 party 之后，他们准备做什么？". Some
questions still ask how one step is done ("他怎么把小篮子接过来呢？").

**What this does not show.** One run per side, and the same code varies run to run; the
counts are a direction, not a rate. The child answers were given to the old questions, so a
real class with the new questions will take a different path. No child heard these.
