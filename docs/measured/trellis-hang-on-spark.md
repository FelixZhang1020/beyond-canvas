# TRELLIS.2 hung on the DGX Spark behind a picture job

The hosted DGX Spark, GB10, one 128 GB memory shared by the
CPU and the chip. Container `beyond-canvas/trellis2:dgx-spark`, the classroom's pinned parameters
(`deploy/gpu-media/extra/trellis_worker.py`), the generated sketch
`skills/art-feedback/evals/files/sphere-study.png`.

## What happened

A TRELLIS.2 job started the instant a FLUX.2 Klein 4B pose preview released the GPU
lock, as the class page queues them. It printed the sparse-structure stage as finished and then did
nothing, chip idle, until the service's 1200 s limit stopped it. Eight later runs that did not follow
a picture job all finished (261.9–278.0 s).

## Reproduced

Scripts under `~/spark-tests/` on the node, log `~/logs/hang-hunt.log`.

| Test | Order | Result |
|---|---|---|
| A | a 3D job stopped 15 s in (the memory floor, faked), then a 3D job at once | finished, 278.0 s — the stop is not the cause |
| B | a picture job (34.4 s), a 3D job queued behind it | **hung** after the sparse-structure stage; stopped at 541 s |
| C | as B, 3D worker with `low_vram` off | finished, 243 s after the lock (271 s with the queue), valid 6.3 MB GLB |

The worker writes every thread's position at 4 and 8 minutes (`faulthandler`). In B both dumps
show the main thread in the same place:

```
torch/nn/modules/module.py, line 1164 in cpu
trellis2/pipelines/trellis2_image_to_3d.py, line 221 in sample_sparse_structure
```

That is `flow_model.cpu()`: `low_vram` mode moving the sparse-structure model back to the CPU's side
after its stage. `docker top` showed the process at 101 % of one core, and `nvidia-smi` showed it
holding 4027 MiB with the chip at 1 %.

## Decision

`low_vram` exists so TRELLIS.2 fits the 4090's own 24 GB. On the Spark both sides are one memory,
so the moves save nothing — the reason `deploy/spark/flux_worker.py` never offloads. The Spark
now runs the worker with `TRELLIS_LOW_VRAM=0` (`deploy/spark/media_spark.py`); the 4090 is
unchanged. Cost: the lowest free memory during the job was 83.8 GiB against 88 GiB with the moves,
about 4 GiB more held while a 3D job runs (the recorder's `~/monitor/samples-*.jsonl`).

Not established: why the move back stalls only after a picture job. The driver is the organisers'
and cannot be changed on the node, so the fix is to not make the move.

## Pixal3D, a few hours later

Pixal3D's runner set `low_vram=True` on the same pipeline code (`deploy/pixal3d/smoke_rgba.py`).
Another window's three Pixal3D jobs in a row stalled the same way — a sampling stage
finished, then one core at ~100 % with the chip at 0 % — and were cancelled at ~900 s by their
client. The runner now reads `PIXAL_LOW_VRAM`, and `media_spark.py` sets it to 0 ("standard mode",
all ~18 GB of models on the chip at once). The next Pixal3D job, through the real service,
finished in 439 s of work (loading ~104 s, sampling ~295 s, export ~40 s) with a valid
6.5 MB GLB; the one successful run before the fix took 516 s.

Since the fix went live: TRELLIS.2 3 of 3 in the order that hung (test C, and two through the real
service behind a picture job), Pixal3D 1 of 1.
