# BENCHMARK: art-feedback

Profile `stepfun`, language `en`. Written by `step-3.7-flash` via `stepfun`; differs from configured Spark target `step3-vl-10b` (hardware not verified). Graded by `step-3.7-flash` via `stepfun`.

| Slot | Cases | Cases passing all rules | Mean rule pass rate | Cost USD | Mean latency s |
|---|---|---|---|---|---|
| `vlm.studio` | 10 | 80% | 95% | 0.0000 | 15.96 |
| `vlm.studio+no-skill` | 10 | 0% | 61% | 0.0000 | 5.89 |

## Failures by rule

- `vlm.studio`: rule 12: 2, rule 3: 2, rule 9: 1
- `vlm.studio+no-skill`: rule 10: 7, rule 12: 5, rule 2: 10, rule 3: 1, rule 4: 1, rule 6: 1, rule 7: 1, rule 8: 3, rule 9: 10

## Does the skill earn its place?

| Model | With the skill | Bare model | Lift |
|---|---|---|---|
| `vlm.studio` | 95% | 61% | +33% |

**Verdict: PASS** at a 90% mean rule pass rate.

## How to read this

**Mean rule pass rate** averages the rules that actually applied to each case, which for an opening with no transcript is eleven of the fourteen: rules 13 and 14 need the child to have spoken and rule 11 needs a lesson intent. **Cases passing all rules** is the stricter number: one rule failing anywhere fails the case.

Rules 6 and 7 are skipped on the sketch entrance, where correction is expected and proportion is the subject, and rule 12 asks there for a question about the student's own process rather than the world inside the picture.

A rule the judge could not reach is recorded as skipped, not passed. Skipped rules are excluded from the score rather than counted, so an unreachable judge lowers how much was measured instead of inflating the result.

**Refusal cases are scored against the wrong yardstick.** A blank page cannot satisfy rule 3, which wants two visible details, and the right reply to it is a closed request for a photo rather than the open question rule 9 wants. Those failures are correct readings of the rules and wrong about the reply. Read the reply for those cases; see references/rubric.md.

Cases whose drawing is not on disk are skipped and never counted. The not-a-drawing case needs a real photograph, which is not committed.

## Red lines crossed

- `vlm.studio+no-skill`: 4 case(s)

A red line refuses on its own, whatever the average says.
