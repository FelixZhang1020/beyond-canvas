# Judge calls need their own token budget

Measured on the cloud profile, `stepfun/step-3.7-flash` via OpenRouter, provider
pinned to StepFun, `reasoning.effort=low`.

## What was measured

The two rubric rules that need the drawing send a short prompt and expect one line of
JSON back. Against `dog-sun-6-8.png` and a four-sentence piece of feedback:

| Call | max_tokens | completion tokens | reasoning tokens | Result |
|---|---|---|---|---|
| grounding (rule 3) | 1600 | 1562 | 0 | JSON returned, 38 tokens of headroom |
| presumption (rule 4) | 1600 | — | 0 | empty content |
| presumption (rule 4) | 4000 | 3524 | 0 | `{"presumptive": []}` |

## What it means

Two things, and the second is the surprising one.

**A judge's visible answer is tiny and its real cost is not.** Nineteen characters of
JSON cost 3,524 completion tokens. Sizing a judge call by the length of its answer is
wrong by two orders of magnitude.

**`reasoning_tokens` reported 0 in every case.** The hidden thinking is billed as ordinary
completion tokens with no breakdown, so the field cannot be used to detect this. The only
visible symptom is `content: null`, which the studio raises as `EmptyCompletion` — and
whose message says to raise `max_tokens`, which is right but understates by how much.

The grounding call passing with 38 tokens to spare is the part to worry about. It was not
a pass, it was a near miss, and a slightly busier drawing or a longer piece of feedback
would have flipped it.

## What changed

`evalkit.rubric.assisted.JUDGE_MAX_TOKENS` is 6000 and is passed explicitly on every
judge call, so judges no longer inherit the profile's chat budget. A regression test in
`tests/test_rubric_assisted.py` asserts the budget is at least 4000.

After the change, the same feedback graded 100% across all ten rules on a live run.

## It is not only judges

Recorded later the same day. With the judge budget fixed, the first full benchmark run
failed on the **writer** call — the ordinary feedback request — which was still inheriting
the profile's 1600. It failed on `scribble-3-5.png` after the same prompt had succeeded on
`dog-sun-6-8.png` minutes earlier.

That is the important shape of this bug. A marginal ceiling does not fail consistently; it
fails on whichever input happens to make the model think a little longer, so it looks like
flakiness rather than a settled misconfiguration. The near miss at 1562 against 1600 was
the warning.

The profile ceilings are now 8000 for `vlm.director` and 6000 for `vlm.studio`, roughly
twice the largest figure measured. The reasoning that makes this cheap: **`max_tokens` is a
ceiling, not a spend.** Tokens are billed as generated, so headroom costs nothing and
truncation costs a failed run. There is no reason to tune this number tightly.

## Still open

The figures are headroom over a handful of measurements, not a measured ceiling. Worth
re-measuring against a busy drawing and against the smaller studio model once the profiles
differ, since its hidden reasoning may cost differently. Chinese feedback is unmeasured;
character-dense output may change the arithmetic. And nothing here has been measured on the
Spark, where the local model does not go through OpenRouter at all.
