# Direct storybook generation on the Spark

The operator chose to remove Step 3.7 Flash's independent **draft review** from
storybook generation. `story-outline` now uses Qwen3.6 to write missing scene
descriptions and the ordered outline directly. Image safety, scene length,
outline page count/order/text checks, teacher editing and confirmation, and
final binding remain. Standalone `scene-description` for animation still uses
Step's independent draft review. If Qwen is unavailable, the existing
`FrontFirst` writer can fall back to Step; that is generation, not a separate
review. Invalid Qwen outline structure stops instead of triggering a Step
rewrite in the same press.

## Spark isolated-copy timings

The paired runs used two public fixture drawings. Qwen calls really ran; their
returned scene and outline text was replaced with the same short fixture text
after each call so Step in the reviewed baseline saw comparable input. The
image safety gate used the same fixed allow verdict in each arm. `Before` uses
the pre-optimization reviewed `_creation_draft` from commit `613590f`; `after`
uses the current direct implementation. On a first press no scene cache exists,
and the old lookahead could overlap only the next Qwen call (under a second), so
the main difference is removal of the independent reviews. Times are monotonic
wall-clock seconds around the complete backend outline request.

| Pair | Reviewed baseline | Direct generation | Step draft-review calls after |
| --- | ---: | ---: | ---: |
| 1 | 100.86 s | 4.38 s | 0 |
| 2 | 53.78 s | 4.20 s | 0 |

All four paired requests completed and bound the two-page book. Binding itself
took under 0.01 s and made no model call. The first baseline had a refused
outline that Step rewrote once; its 100.86 s is an observed fallback path, not
the typical first-press time. The second baseline had three Step reviews and no
rewrite. In both direct runs, Qwen made three calls and Step made no draft-review
call. The sample is too small to estimate a production latency distribution.

One additional **raw Qwen output** run made no text substitution. Its two
scenes, outline and binding all succeeded in 4.47 s, with three Qwen calls and
zero Step draft-review calls. This verifies one real output parses and binds;
it does not establish the rate at which Qwen's unscreened content is accurate.

The command was `sh deploy/spark/test-on-spark.sh python
tools/bench_feature_speed.py storybook storybook`, followed by
`sh deploy/spark/test-on-spark.sh python tools/bench_feature_speed.py
storybook-raw`. Both ran on the Spark isolated test copy, not the Mac or the
live classroom. The harness prints only timing, status and call counts, never
model text, images or credentials. No Wan model was invoked.

These timings exclude real input/output image safety, browser transport and
page rendering. In the classroom, a drawing that has not yet been screened
still uses the Step image-safety service, so a first-use click may take longer
than the numbers above. The five scoped runtime and skill files were deployed
to Spark after matching the live files by hash and preserving a
newer, unrelated 3D change in `studio/classroom_runs.py`. The `studio` service
was restarted, and its log showed successful authenticated classroom API
requests afterward. These isolated timings are not live classroom timings.

Focused Spark tests for creation and role reviews passed (46). The full Spark
check reported Python 1815 passed, 6 failed, 1 skipped, 8 deselected; the six
failures were assertions in feedback, portfolio and serve tests, not storybook
tests. Page build was `STRUCTURE OK`, 468 page tests passed, and all 13 skill
packages and signatures verified. The full Python suite is therefore **not
green** in this working tree.
