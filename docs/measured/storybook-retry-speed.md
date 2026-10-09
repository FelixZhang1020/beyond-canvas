# Story outline retry: before and after timing

Historical snapshot while storybook drafts still used independent Step review.
The operator later selected [direct generation](storybook-direct-generation.md),
so rerunning the linked harness on the current checkout follows the newer path.

The operator asked for an elapsed-time comparison after the storybook optimization.
Measured on the Spark **isolated test copy**, with the unchanged pre-optimization
`_creation_draft` from commit `613590f` against the current working implementation.
Both arms ran sequentially with the same two public fixture drawings
(`dog-sun.png`, `cat-shaded.png`), Qwen3.6 on port 7160 as writer and Step 3.7
Flash on the subscription as independent reviewer. Nothing was deployed to the
live classroom or written into a course.

## Method and limits

The first press generated and independently reviewed both scenes, then received
the **same injected outline outage** before any outline model call. This creates
the retry boundary without paying for two unrelated failed outlines. The second
press used the normal outline generation and review path. The Qwen scene calls
really ran and were timed; for a comparable review, their scene text was replaced
after return with the same two grounded fixture descriptions in both arms. The
image safety gate was answered by a fixture, so these numbers cover draft
generation and independent review, not photo screening or the browser-to-classroom connection.
The second run also supplied the same fixed outline text after each real Qwen
outline call; Step still reviewed it against the actual images and source. The
first run left Qwen's outline output unchanged, which caused different fallback
counts. Both final requests completed successfully.

This is a two-run illustration, not a latency distribution. Step review times
varied substantially between arms. In particular, the first press is not
consistently faster. Under the new overlap, ledger stage durations can count
the same waiting interval twice; the elapsed column below is a monotonic timer
around the complete request.

| Run | Press | Before | After | Difference |
| --- | --- | ---: | ---: | ---: |
| Unfixed outline output | First, then injected outage | 20.86 s | 20.78 s | 0.08 s faster |
| Unfixed outline output | Retry to completion | 68.51 s | 38.74 s | **29.77 s faster (43%)** |
| Fixed outline text after real Qwen call | First, then injected outage | 14.44 s | 31.27 s | 16.83 s slower |
| Fixed outline text after real Qwen call | Retry to completion | 49.19 s | 16.10 s | **33.09 s faster (67%)** |

The retry wrote and reviewed **two scenes again before**, and **zero scenes
after**. In the fixed-outline run, those repeated scene stages took 25.90 s.
The remaining difference in total retry time comes from variation in the Step
outline review (and, in the other run, different outline fallback counts). Across
these two retries the mean was 58.85 s before and 27.42 s after, an illustrative
31.43 s reduction (53%). The sample is too small for a production speed claim.

For context only, the live anonymous ledger contained one earlier request with
five scene calls and two outline calls: 183.3 s elapsed. Its input and fallback
path differ, so it is **not** an arm of the comparison above.

The original harness is [tools/bench_story_speed.py](../../tools/bench_story_speed.py).
It prints only aggregate timing and call counts; it does not print prompts,
model text, images, drawing IDs or credentials. Its current `after` arm now
follows direct generation, so rerunning it will not reproduce this historical
reviewed-path comparison.
