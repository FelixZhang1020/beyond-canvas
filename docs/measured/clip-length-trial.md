# How long a clip can be: Wan 2.2 A14B at 3, 5, 7 and 10 seconds on the Spark

One sitting on the node, 1 h 37 min from the first job to the last. Operator: "i want expand to 10s, test different
seconds generation time". The class makes 49 pictures, about 3 s at Wan's 16 a second.

## How it was run

`deploy/spark/clip_length_trial.py`, from its own copy on the node (`~/clip-trial`, never the class's
`~/beyond-canvas`), one after another: the same watercolour (drawing 100 of
`Image Sample/Color Artwork/`, the file ending `_100_645.jpg`, a snowy river valley), the class's own clip instruction
(`VIDEO_PROMPT` in `studio/animation.py`) with "The river flows gently past the snowy banks, and a
little snow drifts down.", seed 42, 15 steps, 480p by area (544 x 720 here). Each went through the clip
service's own job path: the GPU lock, the kept-loaded models stepping aside, the memory floor. Only the
20-minute job deadline was raised, in the trial's process alone. The only code change a class could see
is that the clip worker now accepts a `frames` field; the class never sends one.

## Results

Numbers from `~/clip-trial/out/results.jsonl` and the step line of each `worker-<frames>.log`.

| On screen | Pictures | Drawing steps | Per step | Whole job | Lowest free memory | Clip file |
|---|---|---|---|---|---|---|
| 3.1 s | 49 | 7 min 12 s | 28.8 s | 775 s (12.9 min) * | 36.9 GiB | 200 KB |
| 5.1 s | 81 | 14 min 7 s | 56.5 s | 1,082 s (18.0 min) | 39.3 GiB | 271 KB |
| 7.1 s | 113 | 21 min 28 s | 85.9 s | 1,533 s (25.6 min) | 37.9 GiB | 384 KB |
| 10.1 s | 161 | 36 min 1 s | 144.1 s | 2,431 s (40.5 min) | 38.0 GiB | 683 KB |

\* includes a few minutes queued behind a clip already running when the trial began; 691 s was
measured for the same length earlier.

- **Time grows faster than length.** Going from 49 to 81 pictures (x1.65) doubled the time per step
  (x1.96); 10 s costs 5 times the drawing of 3 s for 3.3 times the length. Loading and writing the file
  add about 4 to 5 minutes whatever the length.
- **Memory does not grow.** Every length kept 37 to 39 GiB free, far above the 24 GiB floor, so 10 s is
  safe on the node.
- **All four finished and kept the painting.** Six pictures spread across each clip show the drawing
  unchanged, nothing entering the frame and no colour drift, 10 s included. The motion itself (how much,
  whether it repeats) has to be watched, not read from still pictures; the clips were given to the
  operator. Wan 2.2 was trained on 81 pictures; 113 and 161 are past that.

## What it means for a class

The class allows a clip 20 minutes (`JOB_DEADLINE_S` in `media_server.py`, and the studio's
`timeout_s: 1200` for `video.animation`), queue included. Only 3 s fits with room; 5 s fits only when
nothing is ahead of it; 7 and 10 s need the deadline raised to about 35 and 55 minutes. While a clip is
made the Spark makes nothing else and the first voice is off, so a 10 s clip holds the chip for 40
minutes of a lesson. One drawing, one seed: a single trial, not a rate.
