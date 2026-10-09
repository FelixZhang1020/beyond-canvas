# The "explain one visible choice and its effect" sentence, measured

**Question.** The colour reply prompt gained three sentences telling the
writer to *explain one visible choice and its effect*. Soon after, the reply beat was
refused about one time in six, always by rule 14 (the machine never tells the story), and
that sentence was the suspect: an effect the child did not describe reads as the machine
telling the child's story. Before deleting it from a prompt the operator owns, measure it.

**Method.** `docs/measured/scripts/effect-sentence.py`. Five real colour
drawings from the sample set, each with an opening written live by the studio and one
child sentence written for that drawing. Two arms built in memory from the same prompt:
WITH the three sentences, and WITHOUT them (everything else identical, including the
safety lines that follow). Three first attempts per arm, no retry, graded by the same
fourteen-rule grader the classroom uses, with the opening shown to rule 14 as the
classroom now does. StepFun First deployment (`step-3.7-flash` writes and judges).

| Drawing | Child said | WITH | WITHOUT |
|---|---|---|---|
| 100 (snow cabin by a river) | 小木屋里住着一个爷爷，河水结冰了他就去山上砍柴 | 3/3 | 3/3 |
| 102 (pink cat, fireworks, cake) | 这是我的猫在过生日，天上放烟花，蛋糕是给它的 | 3/3 | 2/3 |
| 104 (pink flying dog over a castle) | 粉色的狗狗会飞，它飞过城堡去找黑猫 | 3/3 | 3/3 |
| 108 (village, red car, ambulance) | 红色的车在追救护车，因为里面有我的朋友生病了 | 3/3 | 3/3 |
| 110 (village, flying fish, animals) | 天上的鱼会飞，它们在找下面的马和绵羊玩 | 3/3 | 3/3 |
| **Total** | | **15/15** | **14/15** |

The one refusal was WITHOUT the sentence, rule 14: the reply gave the cat a birthday
hat the child had not mentioned. One WITH reply on drawing 108 drew a rule-10 note for a
61-unit sentence; that is not a red line and the reply passed.

**Reading.** The sentence is not the lever. With it in place the writer's first attempt
was accepted fifteen times out of fifteen; the earlier rate is not reproduced. What
changed in between is the rule-14 judge: since commit a3e4386 it is shown the opening,
so a detail the studio itself named a minute earlier no longer counts as the machine
inventing story. The earlier refusals were that, not the prompt. **The sentence
stays**, and the open item on it closes.

Fifteen per arm is a small sample; a difference of one is noise. What it rules out is a
large effect in either direction, which is what the decision needed.

**What the run cost.** 5 openings + 30 replies + their judge calls, about 20 minutes of
model time in total. The first run, five drawings in parallel, was stopped by StepFun
with `request limited RPM reached, current: 11, limit: 10`; see below.

## Found on the way: the StepFun account is on the free tier

StepFun's pricing page ties the request rate to cumulative top-up: tier V0 at ¥0 allows
**10 requests a minute**; V1 at ¥100 allows 1,000; V2 at ¥500, 5,000. This account is
V0. One child's reply is a screen, a reply and three or four judge calls — five or six
requests — so two tablets talking at once, or a teacher review running while a reply is
written, can cross ten in a minute. The provider raises `ModelUnavailable` on the 429,
the harness retries once with no wait, and the teacher is told the model is unavailable.
Recorded in the acceptance report as an open decision: top up ¥100 before any demo with
more than one device, and optionally add a wait-and-retry on 429.
