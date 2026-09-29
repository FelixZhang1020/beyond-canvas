# BENCHMARK: showpiece skills

Provenance: step-3.7-flash via stepfun, profile api, slot vlm.studio, model skills/model-anatomy/evals/files/stack.blend, cap 12

| case | mode | completed | actions | judged pass/total | tokens | tool seconds |
|---|---|---|---|---|---|---|
| anatomy-stack-inventory | skills | yes | 3 | 0/0 | 12897 | 0.5 |
| anatomy-stack-inventory | bare | yes | 3 | 0/0 | 8512 | 1.0 |
| anatomy-stack-bearing | skills | yes | 5 | 0/0 | 16928 | 1.0 |
| anatomy-stack-bearing | bare | no | 9 | 1/1 | 19814 | 88.0 |
| joint-stack-take-apart | skills | no | 12 | 0/3 | 94464 | 68.9 |
| joint-stack-take-apart | bare | yes | 10 | 0/0 | 39369 | 50.6 |
| tour-stack | skills | no | 12 | 0/1 | 60702 | 211.8 |
| tour-stack | bare | no | 12 | 0/2 | 34628 | 384.8 |
| raise-stack | skills | yes | 12 | 1/4 | 47702 | 136.5 |
| raise-stack | bare | no | 12 | 0/3 | 42059 | 345.7 |
| load-stack-stands | skills | yes | 5 | 0/0 | 18003 | 40.9 |
| load-stack-stands | bare | no | 2 | 0/0 | 4294 | 1.0 |

## The first run, before the fixes (38 minutes)

Same six cases, same model, same cap of 12 actions; the log is `.studio/showpiece/runs/stack-benchmark.log`
(this Mac only). It is kept here because it is what found the faults fixed in commit 4a155fd.

| Case | With the skills | Bare |
|---|---|---|
| what is in the model | answered, 3 actions, 13 s | answered, 2 actions, 8 s |
| in what order was it put up | answered, 4 actions, 12 s | cap, 188 s |
| take it apart from the top down | cap, 0/3 judged, 553 s | cap, 0/3, 346 s |
| fly around it | cap, 0/4 judged, 276 s | cap, 0/1, 216 s |
| in what order does it go up | cap, 81 s | answered, 1/1 judged, 271 s |
| does it stand on its own | answered, 0/3 judged, 193 s | the runner crashed |

What the model tripped on, read from the runs: it copied the run folder's own path into
`out_dir`, so every output landed in a second run folder nested inside the first and its plain
reads of `scenes.json` failed; it wrote `--image` for `image`; it passed a JSON list for the tour's
comma-separated `segments`; it judged the closed still of the pull-apart instead of the open one
and aimed the camera straight down; and in the bare run it named a picture that did not exist,
which the driver tried to attach and the whole benchmark died. The stack fixture has no lights,
so every settle and tour still came out black or washed out and failed the judge. All of these
are fixed in the commit above; the numbers at the top are the run after.

## The verification run of the two cases that still hit the cap (15 minutes)

After commit 1123c23 (each act's line names what it wrote, a missing input is refused with the
folder's listing, the two skills name every output file), the two cases were run again with
`--no-write`, so the table at the top is untouched; the log is `.studio/showpiece/runs/stack-benchmark3.log`.

| Case | With the skills | Bare |
|---|---|---|
| take it apart from the top down | answered, 11 actions, 1/3 judged, 315 s | cap, 0/2 judged, 178 s |
| fly around it | answered, 10 actions, 1/4 judged, 279 s | cap, nothing judged, 78 s |

With the skills all six cases now end in an answer; without them two do. The judged counts
are honest about the small model: on the stack fixture the judge fails three of four tour stills
(a bare white box on a slab is hard to call "the front of the hall"), and the model answers
after the one pass, as the protocol allows.
