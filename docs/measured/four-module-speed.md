# Four classroom modules: isolated before/after timing

Historical snapshot from **before** the operator switched storybook drafts to
[direct generation](storybook-direct-generation.md).

The operator requested a timing comparison for the four tabs shown in the
creation UI, and explicitly excluded Wan 2.2. The benchmark ran on the Spark
**isolated test copy**, using public fixture drawings and real Qwen3.6,
Step 3.7 Flash and online Wan 3.0 calls. Every request below completed. No
live course was opened or written, and the storybook optimization was not
deployed to the classroom.

## Results

`Before` uses the pre-optimization `_creation_draft` from commit `613590f`;
`after` uses the current working implementation. The rest of the code and
profile are identical in both arms. Times are monotonic wall-clock seconds
around each backend request, not the sum of model call times.

| UI module | Backend action | Before | After | Change in this optimization |
| --- | --- | ---: | ---: | --- |
| Teacher review | `teacher-review` | 3.68 s | 4.43 s | None |
| Chat about your painting | `art-feedback` opening | 61.03 s | 21.97 s | None |
| Make the painting move | `scene-description` | 7.37 s | 6.68 s | None for this standalone request |
| Make the painting move | `painting-to-animation`, **online Wan 3.0** | 90.30 s | 90.50 s | None |
| Make a storybook | `story-outline`, two missing scene descriptions, first successful press | 38.41 s | 87.91 s | One-page Qwen lookahead; no stable first-press improvement |
| Make a storybook | `drawings-to-storybook` binding | <0.01 s | <0.01 s | None; no model call |

The two requests under "Make the painting move" took 97.67 s before and
97.18 s after when added as sequential backend requests. The video phase
dominates that path and did not use Wan 2.2. The storybook first-press
difference is **not** evidence of a slowdown caused by the optimization:
Qwen's three calls took 0.79/0.74/2.76 s before and 0.90/0.72/2.89 s after,
while Step's three independent reviews took 11.66/4.82/17.64 s before and
9.37/46.00/28.75 s after. The second page's Step review alone varied from
under five seconds to 46 seconds. The only repeated speed gain established
for this patch is the separate, two-run **retry** comparison:
[68.51/49.19 s before → 38.74/16.10 s after](storybook-retry-speed.md).

For teacher review, Qwen wrote the report in both arms (one call each); no
Step independent review was invoked. For chat, Qwen wrote in about 0.9 s in
both arms, while Step rule checks were on the critical path. The chat code
path did not change in this optimization, so its 61.03 → 21.97 s difference
is service variation, not a measured improvement. For the animation
description, Qwen wrote in 1.06/0.63 s and Step reviewed in 6.31/6.05 s.

## Method and limits

The image safety gate used the same fixed allow verdict in both arms to isolate
the requested model and media stages. These numbers exclude real input and
output safety screening, browser transport, and page rendering. For storybook
and the animation description, real Qwen calls ran, then their returned text
was replaced with identical short fixture text before Step's real independent
review. The story outline was likewise fixed after the Qwen call. Chat and
teacher-review text was not substituted. This controls the review input but
is not a production latency distribution. There is one before/after run per
module here; the linked retry comparison has two runs.

The video stage explicitly sent `clip_maker=online`. The benchmark asserted
that the deployed profile offered only the online choice; it would fail rather
than select Wan 2.2. The online key was read into the test process from the
existing private node configuration, never printed or copied. The returned
video bytes, model text, drawing IDs and credentials were not logged by the
benchmark. The command used was `sh deploy/spark/test-on-spark.sh sh
tools/bench_feature_speed.sh`, with implementation in
[tools/bench_feature_speed.py](../../tools/bench_feature_speed.py). Its
current storybook `after` arm now follows direct generation, so a new run
will not reproduce this historical reviewed-path timing.
