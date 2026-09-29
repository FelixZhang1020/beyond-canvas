# The 3D view check, measured on three saved models

**Why.** A teacher reported that the apple and pear from 全素描样例 opened as a 3D model seen from
behind: the pear stood in front of the apple, where the drawing has the apple in front. The view check
(`studio/view_calibration.py`: Step 3.7 Flash picks one of eight grey renders, then one of nine
nearby, then a second call confirms) had marked that result `matched` at yaw 150.

**The right answer.** Each saved model was rendered at twelve angles 30° apart beside its drawing on
the Spark, and the right angle read by eye. Within 20° counts as right.

| Saved result | Drawing | Right yaw | What the check saved when the model was made |
|---|---|---|---|
| `88185ce2f9fc` | apple in front of a pear | 30 | matched at 150: seen from behind |
| `ec4822822d50` | the same drawing, made earlier | 30 | matched at 165: seen from behind |
| `a5e154024378` | plaster head, three-quarter left | 180 | matched at 30: the back of the head |
| `c6bcbf4265f9` | cube, sphere and cylinder | 180 | gave up (second look said no) |
| `00b5d0d01bd9` | plaster head (later result) | 180 | gave up (second look said no) |

Every result the check passed in the Portfolio faced wrong.

**Run again.** `docs/measured/scripts/view-calibration-trial.py`, on the Spark with the
class's own `vlm.sketch` slot, three models at a time.

| Check | Right | Wrong | Gave up |
|---|---|---|---|
| As it is (first grid from nearly level, 80°), 3 runs each | 4 of 9 | 0 | 5 (3 second-look refusals, 2 failed calls) |
| First grid from 65°, the height a still life is drawn from, 4 runs each | 6 of 12 | 0 | 6 (4 second-look refusals, 2 failed calls) |

The 65° grid is within noise of the original and was **not kept**. What the replies show:

- **A wrong pick is now rare and the second look catches it.** Twice the first two picks were wrong
  (apple at -15, head at 120) and the second look refused both, reading the arrangement correctly.
- **The second look also refuses right picks.** The cube at 180 and at 165 was refused because the
  second look thought the other side of the cube was showing.
- **Calls fail.** 4 of 21 runs ended with a call to StepFun that raised; three ran at once here, one
  at a time in a class.
- When the check gives up the viewer opens at a fixed default (yaw 45), which is wrong for the cube
  and the head.

Why the check saved three wrong views then and none in this run is not known: the prompt has not changed
since (`git log studio/view_calibration.py`); the model may have been served differently.

**What changed.** The teacher has the last word: under a 3D model a button, 按这个角度摆放, saves the
angle she has turned it to (`Portfolio.view`, `PATCH /api/courses/<id>/activities/<id>/view`), and it
opens that way afterwards. The check's own record is kept beside it.

**Teacher corrections, later the same day.** The saved sample course was opened in the actual
Spark browser and its two currently shown GLBs were turned beside the drawing. The UI's existing
`Portfolio.view` path saved fruit result `88185ce2f9fc` from `[150,65]` to `[54,88]` and portrait
result `00b5d0d01bd9` from no angle to `[172,75]`, both with `camera_calibration.status=teacher`.
The fruit was reopened and showed the apple in front of the pear. These are view corrections on
saved results, not new model generation; the generated shapes still differ from the sketches.
