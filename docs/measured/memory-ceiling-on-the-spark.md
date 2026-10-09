# The memory ceiling on the Spark

The DGX Spark does not kill one process when memory runs out; it freezes, and nobody on this project can
reboot it. Until this change every class job kept **24 GiB available** (`deploy/spark/memory_guard.py`,
`FLOOR_GIB`), the same floor the builds keep, which on a 121.7 GiB node is a ceiling of about 97.7 GiB in
use: about a fifth of the node sat idle, and the models stepped aside for each other far more often than the
memory required. The operator set three rules in their place, and this file records what they rest on.

## The rules

| Rule | Number | Where it lives |
|---|---|---|
| A class job, or a kept-loaded model's load, may take the node to this much **in use** (total minus available, the figure the node's monitor shows) | **115 GiB** | `memory_guard.CEILING_GIB`; `media_spark.fits`; the three `*-load.sh` ask `memory_guard.py --room` |
| A job or load already running is **stopped** under this much **available** | **6 GiB** | `memory_guard.STOP_GIB`; `media_spark.memory_low`; the Qwen and TRELLIS loaders ask `memory_guard.py --low` |
| A build keeps this much available (a compile has no measured peak) | 24 GiB | `memory_guard.py --floor 24` in every `build-*.sh` |

**NVIDIA's safety reader (Nemotron 3.5 Content Safety, ~11 GiB) is always loaded.** No job asks it to step
aside, so the class's second look can be taken at any moment, a clip's way-out look included; the clip's wait
for a reader that stepped aside (`conversation.READER_BACK_S`) is answered on its first ask.

**Everything else stays loaded together while the total fits.** When a new load would pass the ceiling, the
media service asks, in this order, until the job fits: the storybook's warm FLUX and VoxCPM2 (kept only to
save the next page's load), the kept-loaded TRELLIS.2 (a load it pays back on the next sketch), then Qwen,
the first voice (Step 3.7 Flash stands in for the class's chat, its checks and the screen while it is away,
slower because it thinks before every answer; never for a book's jobs, since the teacher is talking meanwhile).
Failing all three the job is refused. One GPU lock still runs one job at a time:
models load together, jobs take turns.

## What fits, from the code's own numbers

System 6, Nemotron 11, Qwen 50, TRELLIS.2 loaded 31 or a cold 3D job 38, FLUX 22, VoxCPM2 12, Wan 2.2 clip 85
(`media_spark.PEAK_GIB` and the loaders' comments), ceiling 115:

| Job | Loaded beside it | In use | Under the ceiling? | The old floor |
|---|---|---|---|---|
| Wan 2.2 clip | Nemotron | 102 | yes | paused the reader |
| Wan 2.2 clip | Nemotron + Qwen | 152 | no: Qwen steps aside | same |
| Wan 2.2 clip | Nemotron + TRELLIS.2 | 133 | no: TRELLIS.2 steps aside | same |
| Cold 3D job | Nemotron + Qwen | 105 | yes | paused Qwen |
| 3D job on the loaded TRELLIS.2 | Nemotron + Qwen + TRELLIS.2 | 106 | yes | fit |
| Storybook pictures | Nemotron + Qwen | 89 | yes | fit |
| Storybook pictures | + TRELLIS.2 loaded | 120 | no: TRELLIS.2 steps aside | same |
| Child's voice page | Nemotron + Qwen + FLUX warm | 101 | yes | sent FLUX away |
| Qwen loading again | Nemotron + TRELLIS.2 | 100 | yes | needed 76 available |

The counted sizes are peaks, rounded up. Idle, the models hold less: measured by the node's monitor on the
afternoon the ceiling was set, the node took 4.0 GiB with nothing loaded, 20.5 with TRELLIS.2 loaded,
65.6 with Qwen beside it and 77.7 with Nemotron beside both, so Qwen idle is about 45, TRELLIS.2 idle about
16 and Nemotron about 12.

## The evidence for the ceiling and the stop level

The same afternoon, someone stopped `qwen-front` and `nemotron-safety` by hand and ran an SGLang container
(`qwen38`, `lmsysorg/sglang:latest`) for fourteen minutes. The node's monitor (`~/monitor/samples-<day>.jsonl`,
one sample every 10 s) recorded the only measurement anyone has of this node near full:

| Time | In use | Available | In swap | Loaded |
|---|---|---|---|---|
| 16:12 | 65.6 | 56.1 | 1.5 | Nemotron, Qwen (then both stopped by hand) |
| 16:14 | 102.5 | 19.2 | 0.1 | qwen38, TRELLIS.2 loading |
| 16:15 | 109.3 | 12.3 | 5.0 | qwen38, TRELLIS.2 |
| 16:17 | 103.2 | 18.4 | 10.8 | qwen38, TRELLIS.2 |
| 16:23 | 110.2 | 11.5 | 11.5 | qwen38, TRELLIS.2 |
| **16:24** | **114.5** | **7.2** | **11.6** | qwen38, TRELLIS.2 (the peak sampled) |
| 16:24, Qwen's loader | | **6** | | the lowest figure any log holds |
| 16:26 | 20.5 | 101.2 | 8.5 | TRELLIS.2 (qwen38 gone) |
| 16:30 | 77.7 | 44.0 | 8.5 | Nemotron, Qwen, TRELLIS.2 |

The node did not freeze. Three things that episode shows:

- **Past about 19 GiB available the kernel swaps.** The chip's allocations cannot be swapped, so the kernel
  pushed everything else out: 11 GiB within three minutes. Swap (16 GiB) is what carried the node through,
  and it is not counted in "in use"; 8.5 GiB of that episode's pages were still in swap hours later.
- **6 GiB available is the lowest the node has been seen to survive**, with 11.6 GiB in swap. That is the stop
  level. Nothing below it has been measured, and a job allowed to the ceiling lands at 6.7 available, so a
  job planned to land within 0.7 GiB of the ceiling can be stopped by a transient peak. No row in the table
  above lands over 106.
- **The reader's keeper did not fail.** It was stopped by hand at 16:12:15; its loader refused to load at
  14, 9, 18 and 15 GiB available, because it then wanted 11 above the 24 GiB floor while the hand-run
  container held about 100; and once the memory came back at 16:26 the lock was Qwen's for its four-minute
  load. It loaded at 16:30:24, eighteen minutes after it was stopped. Under the ceiling its loader needs
  11 GiB of room, so the same episode would have kept it down for the same fourteen minutes; nothing in the
  keepers can take memory back from a container someone started by hand.

## The real runs under the new rules

From the node's monitor (one sample every 10 s) after the change was sent and the four media services and
the two keepers restarted at 17:01:50 node time; the keepers adopted the models already loaded, so nothing
reloaded and the reader never went down. Four jobs through the standard studio, in two courses made for it:

| Job | Loaded beside it | Peak in use | Available at the peak | Stepped aside | Reader |
|---|---|---|---|---|---|
| Sketch 3D on the loaded TRELLIS.2 (a plaster head) | Qwen, Nemotron, TRELLIS.2 | **84.9** (78.0 idle) | 36.8 | nothing | up |
| Storybook: page 1 in seven styles, then the rest (FLUX) | Qwen, Nemotron, TRELLIS.2, FLUX warm | **103.8** | 17.9 | nothing | up |
| Storybook read in the child's voice (VoxCPM2) | Qwen, Nemotron, TRELLIS.2, VoxCPM2 warm | 97.8 | 23.9 | the warm FLUX: 11.2 GiB of room against its counted 12 | up |
| Sketch 3D with TRELLIS.2 not loaded (pears), its own container | Qwen, Nemotron, VoxCPM2 warm | **106.3** | 15.4 | nothing: Qwen stayed, where the old floor paused it | up |
| Wan 2.2 clip, the Spark's own, 18 minutes (run later that evening, once the clip was open to teachers again) | Nemotron | **92.3** (89 for most of the run) | 29.4 | TRELLIS.2, then Qwen, as the order says; the reader never | up, in every sample |

- **Nemotron was in every sample** from the restart to the end of the runs, and no job wrote a `paused`
  flag: nothing can any more.
- **Swap never grew.** It fell from 8.3 GiB to 5.0 over the hour as pages from the SGLang episode came back.
- **Qwen's log holds no "stopped" line from a job.** It holds one from 17:16:03, between the jobs: the
  container exited by itself with status 0 (Docker's events show no kill or stop and the node's own
  `docker stop` always leaves one), with no pause flag, 84 GiB in use and no media job running. The keeper
  had it answering again at 17:19:54, and one chat reply asked for in that window got no answer and was sent
  again. Its cause is not known; the container's log went with it (`--rm`). Not a memory event: it had
  44 GiB available. Since then its loader runs it without `--rm` and the keeper saves the container's last
  hundred lines and its status to `~/logs/qwen-front-last-exit.log` whenever it stops, so the next such exit
  says why.
- The four models the counted peaks say fit together did, at 103.8: Qwen, Nemotron, TRELLIS.2 and FLUX.
  The child's voice beside them missed by 0.8 GiB of counted peak, so the voice sent the warm FLUX away, as the
  order says. That costs a 22 s reload only when a page is drawn again after its check or a second book
  follows within three minutes.
- Timings: the warm 3D reconstruction passed in 167 s wall time (ledger); the seven styles took about 50 s;
  the cold 3D job ran from 17:32:10 to 17:37:00. The cold job was made by removing the loaded model by hand
  and asking at once: the job's own waiting note (`waiting-<pid>`) kept the keeper from reloading until the
  job ended, and it reloaded afterwards into 41 GiB of room.
- Two things seen on the page that are not the rule's: the head's 3D model passed the studio's check at
  167 s but the page waited 491 s and then said the task failed, which is the door's stalled-download fault
  seen the same afternoon; and at 1440×779 the chat's Send button sits under the console chip, so a click
  on it opens the console (`coveredBy: backstage-console`).

## What is not measured, and the risks that stay

- The stop level is one measurement, taken under swap. A model that grows faster than the stop can act (the
  check runs every 0.25 s; `docker stop` takes a few seconds) could still pass it. A clip loads about 85 GiB
  in about a minute.
- Running jobs at the same time was not tried. The lock stays.
- Swap is not in the rule. A node with swap full and 6 GiB available is not the node that was measured.

## How the figures were gathered

The monitor's timeline: `python3` over `~/monitor/samples-<day>.jsonl` on the node, printing each sample's
`mem_total_gib - mem_avail_gib`, `mem_avail_gib`, `swap_used_gib` and `containers`. The keepers' timings:
`~/logs/safety-reader.log` and `~/logs/qwen-front.log`. The table of fits: `media_spark.PEAK_GIB`,
`TRELLIS_JOB_GIB`, `FLUX_JOB_GIB`, `VOICE_JOB_GIB` and the loaders' comments, added by hand.
