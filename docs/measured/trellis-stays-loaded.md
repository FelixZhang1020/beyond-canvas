# TRELLIS.2 kept loaded on the Spark

**Question.** The sketch entrance is where a child waits with nothing to watch. Loading the model is part of
every 3D job; if it stays loaded between jobs, how much shorter is the wait, what does it cost in memory,
and does the child get the same thing?

**Setup.** The node, through the real 3D service on 7240, with the class's own worker, settings and seed.
One sketch throughout: `Image Sample/B&W Sketch/06-head-excellent.png`. The kept-loaded process is
`deploy/spark/trellis_resident.py`, held up by `trellis-resident.sh` (tmux `trellis-resident`).

## The wait

| | Seconds |
|---|---|
| Its own container each time, as it used to run | 200.4, 205.7 |
| First job after the model loads | 121.2, 124.6, 134.4 |
| Every job after that | 67.0, 67.9, 69.5 |

**A sketch comes back in about a minute instead of three and a half.** The model itself loads in 80 s, and
the first job after a load is slower, so a class that asks for one 3D model and no more saves about a minute
and a half; a class that asks for several saves more than two minutes each.

## The memory

- It holds **~26 GiB** when it loads and **~31 GiB** once it has worked (the difference is what the chip's
  allocator keeps back for the next job).
- A job on top of those weights took **1.6 GiB**, and about 5 GiB the first time after a load. The service
  asks for 8 GiB of room for such a job (`media_spark.TRELLIS_JOB_GIB`) rather than the 38 GiB a job needs
  when nothing is loaded.
- The node keeps 24 GiB free by rule, so with the model loaded, the safety reader up and the studio running,
  about 80 GiB stays free for everything else.

## The clip still gets its memory

A clip needs ~85 GiB. Measured end to end, about 13 minutes: the clip service stopped the loaded 3D model
first and NVIDIA's safety reader a minute later, only when that was not enough, made its clip, and both loaded
again by themselves — the 3D model 13 minutes after it was stopped, the reader a minute after that. **The order is deliberate:** memory
that costs only a reload goes before memory that costs a class its second safety look.

## The same drawing does not give the same file, and never did

Four builds of the one sketch gave four different files: 2,966,632 bytes cold, 3,118,556 / 3,130,724 /
3,158,748 warm, and another cold run different again. Two warm runs disagree as much as warm and cold do,
so this is the model on this chip, not the keeping-loaded. The worker's comment claiming a fixed seed means
the same model has been corrected.

Rendered side by side, the warm model and that other cold one are the same head to the eye: same face, same
proportions, same detail (`~/spark-tests/warm-vs-cold.png` on the node).

## Two defects this measurement found

- **A deploy is not a restart.** After the code was sent, the clip service was still running the version it
  started with, so it did not know how to stand the loaded model aside — and refused a clip (503) while the
  memory was held. Both media services are restarted after a deploy now; the studio alone is not enough.
- **A job the loaded model dropped was lost.** When a pause left behind by a restarted service stopped the
  model under a running job, the job failed outright: a class would have been told there is no 3D this time.
  A job whose loaded model went away is now tried once more in a container of its own
  (`media_spark.once_more_without_the_resident`); a drawing that genuinely fails is not retried, and neither
  is one whose teacher has walked away.

## What is not measured

Whether the saved minute changes anything a teacher notices, and whether holding 31 GiB all day costs
something else on a busy node. Both want a real class day to answer.
