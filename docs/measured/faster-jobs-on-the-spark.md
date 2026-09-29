# Faster jobs on the Spark — follow-up plan (Task 7 of the whole-project plan)

**Goal:** a class waits less for each picture, 3D model and clip, without the Spark running out
of memory (it freezes rather than failing when it does).

## Where the time went before the change

Every job starts a fresh container, loads its model, works, and exits so its memory is freed.
Timed by `phase_timeline.py` from each worker's own log, through the real services; memory from
the recorder (`~/monitor`) and `~/logs/ram-measure.log`.

| Model | Starting the program | Loading the model | Doing the work | Total | Peak memory |
|---|---|---|---|---|---|
| FLUX.2 Klein 4B (pose picture) | ~13 s | ~9 s | ~4 s (drawing itself ~1.2 s) | ~27 s | ~22 GiB |
| TRELLIS.2 (3D) | ~100 s together | | ~140 s sampling + ~30 s export | ~243 s | ~35 GiB |
| Pixal3D (3D, second route) | ~104 s together | | ~295 s sampling + ~40 s export | ~439 s | ~50 GiB |
| Wan 2.2 I2V A14B (clip) | see below | | | | ~70 GB loaded |

The queue comes on top: every job shares one lock, so a picture asked for while a 3D job runs
waits for it (69 s and 208 s in the measured runs, behind another window's jobs).

## The clip as it was set does not fit a class

The class clip — 81 frames, 30 steps, guidance 3.5, played at 24 fps (3.4 s) — was run once through
the real service: the model loaded in ~195 s, each step took
~54.6 s, and the service's own 1200 s job cap stopped it after ~18 of 30 steps. Memory stayed at
40 GiB free (~80 GiB in use). A whole clip needs ~31 minutes; the class allows 900 s.

Measured the same night with the model loaded once (`wan_probe.py`, 2 and 4 steps per setting):

| Frames | One step | Fixed (text, decoding) | Load, every clip |
|---|---|---|---|
| 81 | 54.6 s | ~40 s (estimated) | ~190 s |
| 49 | 28.4 s | 26.6 s | ~190 s |
| 33 | 17.7 s | 18.4 s | ~190 s |

What a whole clip would take (load + fixed + steps; queue not included):

| Setting | Clip on screen | Time | Fits 900 s |
|---|---|---|---|
| 81 frames, 30 steps (as set) | 3.4 s at 24 fps | ~31 min | no |
| 81 frames, 15 steps | 3.4 s | ~17.5 min | no |
| 49 frames, 20 steps | 3.1 s at 16 fps (Wan's own rate) | ~13 min | yes, little room |
| **49 frames, 15 steps** | 3.1 s at 16 fps | **~10.7 min** | yes |
| 33 frames, 30 steps | 2.1 s at 16 fps | ~12.3 min | yes |

Fewer steps soften detail; fewer frames shorten the movement. Keeping the video model loaded is
not an option: it holds ~80 GiB. A queued 3D job ahead of a clip (4–7 min) counts against the
class's 900 s, so any choice fits better with the ceiling raised to the service's 1200 s cap.

## The lever

Starting and loading is most of a picture (22 of 27 s) and about 40 % of a TRELLIS.2 job. A model
kept loaded between jobs skips both. Memory is the limit: the Spark has ~119 GiB, the service
floor is 24 GiB free, and the clip alone holds ~70 GB, so not everything can stay loaded.

## Decided

- **The clip:** 49 frames, 15 steps, 16 fps (the sample the operator saw, 691 s); the class waits
  up to the video service's 1200 s. `deploy/spark/wan_i2v_worker.py`, `studio/profiles/stepfun.yaml`.
- **Speed: option A.** FLUX.2 Klein 4B stays loaded (`deploy/spark/flux_resident.py`, kept running
  by `flux-resident.sh`, reached through `flux_client.py`). It loads while holding the jobs' GPU
  lock, and a job that does not fit only because of its ~22 GiB (the clip) pauses it
  (`media_spark.room_for`) and lets it load again afterwards. Without it, pictures fall back to a
  one-off container.
- **Sharing the chip** (operator): class jobs run beside another window's work when their
  measured memory fits (`media_spark.PEAK_GIB`), instead of refusing whenever anything else is on
  the chip.

## Measured after the change

- A class clip through the class address, end to end: safety 13 s, clip 668 s, the studio's
  check and the frames' safety screening after it — done at 711 s, inside the 1200 s wait.
- Pose pictures through the real service with the model kept loaded: 5.6 s (first) and 3.1 s,
  the same bytes as a one-off job made from the same drawing; ~1 GiB extra while drawing.
- FLUX.2 Klein 9B against the 4B on the three test drawings (`flux_compare.py`): 46–63 s a picture
  loaded per job, ~35 GiB; no clear quality gain (both misread which shape was the dog in
  `dog-sun`). The 4B stays the class model.

## Options for the operator (as they were put)

| Option | What stays loaded | Picture | TRELLIS.2 | Memory held between jobs | Cost |
|---|---|---|---|---|---|
| **A. Picture model stays loaded** (recommended) | FLUX | ~27 s → ~4 s | unchanged | ~22 GiB | Half a day. The clip must unload it first (it is reloaded after, ~20 s). |
| B. Picture and TRELLIS.2 stay loaded | FLUX + TRELLIS.2 | ~27 s → ~4 s | ~243 s → ~145 s | ~57 GiB | About a day. Leaves ~60 GiB for everything else; Pixal3D and the clip must unload both first. |
| C. Nothing changes | — | ~27 s | ~243 s | 0 | None. |

Either A or B also needs the one-at-a-time lock to cover a loaded model, so a 3D job never starts
beside a loaded picture model it has not accounted for, and the memory floor to stop the
newcomer, not the resident, when memory runs short.
