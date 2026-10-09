# Archived deployments

**API First** (`api.yaml`) and **Local First** (`local-first.yaml`) were archived by
operator decision: **StepFun First is the studio's only deployment.**
These two files are kept for reference only. Nothing loads them — the studio, the
page, the start command and the tests all offer StepFun First alone — and a saved
choice of either one opens as StepFun First.

| Deployment | What it was | Why it mattered |
|---|---|---|
| API First | Bought everything: Step 3.7 Flash per call from the balance, FLUX and Wan on Replicate, TRELLIS.2 and Pixal3D on hosted APIs, StepFun speech and hearing. Needed no hardware of its own. | The fallback for a machine with no GPU box: a fresh clone started on it. StepFun First needs the 4090 or the Spark for pictures and 3D, so a machine with neither now refuses to start rather than falling back. |
| Local First | Bought only the reading (Step 3.7 Flash per call); FLUX, Wan 2.2 5B, TRELLIS.2, Pixal3D, VoxCPM2 speech and Whisper hearing all on the 4090. | **The only deployment that kept a child's recorded voice on hardware the operator owns.** Since the archive every class sends recordings to StepFun for transcription (`stepaudio-2.5-asr`); the operator took this decision with that consequence stated. |

**StepFun First from the Mac + 4090** (`stepfun-mac-4090.yaml`) followed soon after:
the operator moved the whole project to the hosted DGX Spark and kept the Mac for
development. It is StepFun First exactly as it ran from the Mac — pictures and 3D on the 4090
over a tunnel, the Wan 2.2 A14B clip bought from Replicate because the 4090 holds only the 5B.
`../stepfun.yaml` is now the Spark's (the clip made on the Spark itself), `stepfun-spark.yaml`
and the `BEYOND_CANVAS_MACHINE` switch that chose between the two are gone, and the 4090 is
left as it is, unused. To bring it back, restore `stepfun-spark.yaml` and the switch from git
history before this change and put this file's video slot back into `../stepfun.yaml`.

What moved with the archive, so it is not mistaken for a loss:

- StepFun First used to be `extends: api`. The slots it inherited — the six Step 3.7
  Flash reading slots, the StepFun voice and the Replicate Wan clip — were copied into
  `../stepfun.yaml` unchanged; its resolved configuration was compared before and after
  on the Mac and the Spark and is identical.
- The temple showpiece, the photo judge and the teacher-review fallback used API First's
  settings. They now use StepFun First's: the same Step 3.7 Flash, on the subscription
  instead of the balance.
- The code that only these two used is still in the project and unused by any
  deployment: the 4090 voice client (`studio/providers/remotevoice.py`), the Whisper
  client for the 4090, and the hosted mesh routing for Pixal3D.
- The tests that compared three deployments were last present in commit `35b4204`
  (`tests/test_three_deployments.py`); the ones that exercise machinery StepFun First
  still uses moved to `tests/core/test_stepfun_first.py`.

## Bringing one back

Move the file back to `studio/profiles/` (`local-first.yaml` extends `api`, so it needs
`api.yaml` beside it), add it to `DEPLOYMENTS` and remove it from `ARCHIVED` in
`studio/core/deployments.py`, restore the `local-first` branch of `build_runtime` from commit
`35b4204`, and give the page its labels back in `studio/page/src/20a-strings-deployment.js`
and `studio/page/locales/zh.js`. Then re-run the test suite and the page build.
