# 4090 media bridge

**No class uses the 4090 any more** (operator decision: the whole project runs on the
hosted DGX Spark; the Mac + 4090 profile is in `studio/profiles/archive/stepfun-mac-4090.yaml`).
Keep `extra/` — the Spark's media services run its `media_server.py` and workers
(`deploy/spark/media_spark.py`). The rest describes how the 4090 served classes until then.

The classroom uses five loopback endpoints on the shared RTX 4090 D. The Mac
runs SSH forwarding and HTTP clients; weights and inference stay on the 4090.
`tunnel.sh` forwards all five ports without exposing them to the LAN.

| Port | POST route | Explicit model IDs | Result |
|---|---|---|---|
| 7240 | `/v1/mesh` | `trellis2` | GLB |
| 7250 | `/v1/mesh` | `pixal` | GLB |
| 7260 | `/v1/video` | `wan2.2-ti2v-5b` | MP4 |
| 7270 | `/v1/image` | `flux`, `step1x` | PNG |
| 7280 | `/v1/audio/speech` | `VoxCPM2` | 24 kHz mono PCM16 WAV |

`GET /v1/models` is read-only: each model reports `ready` and a state, with
`last_generation` evidence when recorded. Standby means installed materials,
not quality approval. Missing materials leave the readiness marker absent
and generation returns 503. Checking never loads weights.

Media requests contain `model`, an embedded `image` data URI, and `instruction`
for images/video. Voice uses `input` and one of `gentle-female`, `gentle-male`,
`soft-child`. Only public synthetic reference WAVs are installed. Sources and
revisions are in [model-sources.json](extra/model-sources.json); existing TRELLIS
inputs remain canonical in [versions.env](../trellis2/versions.env).
Step1X's Qwen2.5-VL encoder is its internal dependency, not another classroom
vision service or API provider.

## Scheduling and cancellation

[media_server.py](extra/media_server.py) accepts at most one request per endpoint.
They share the existing deployment `gpu.lock`; queue and execution together
are bounded to 1,200 seconds. Inference runs in a UUID-named disposable
container, whose exit releases the model's VRAM.

Clients supply a unique `job_id` and send `POST /v1/cancel {"job_id":"…"}`
to the same endpoint. Only the matching request is cancelled. Up to 128 early
cancellations are retained for 120 seconds to cover registration races.
Queued and running requests inspect the cancellation event and socket EOF.
Cleanup removes only the task container. Cleanup failure keeps the display
model paused instead of starting overlapping GPU work.

While holding the lock, a job pauses the project's idle
`beyond-canvas-trellis2` display container and restores it afterwards. Its 7040
viewer remains the original service but is temporarily unavailable during a
media job. Its old 7240 publication is removed; the lightweight classroom
endpoint stays up during switching. Unrelated GPU workloads are not stopped;
more than 1.5 GiB of remaining compute usage rejects the job.

Wan remains 33 frames and 10 steps with the `1280*704` size budget, approximately
1.38 seconds at 24 fps. Actual dimensions follow the input aspect ratio; the
square official sample produced 960×928, not a fixed 1280×704 frame.
Both 3D exports use a 100,000-face target and 1024 textures to fit the classroom
8 MiB budget. Export limits do not imply equal geometric fidelity.

## Start and rollback

Install `extra/` as `media-extra/runner` beneath the remote deployment root.
The explicit-port `extra/start-image.sh`, `extra/start-mesh.sh`,
`extra/start-voice.sh`, `extra/start-trellis.sh` and `extra/start-video.sh`
start the lightweight services. Do not restart a busy process. Port hook tests cover
quoted SSH startups and invalid-port controls. Connection details remain only
in the `gpu4090` SSH alias.

The old compose file is backed up remotely as
`trellis2/compose.before-media-extra.yaml`. To roll back while idle, stop only
the recorded new processes, restore that compose file, and use the original
`select-model.sh`/`start-wan.sh` flow. Preserve weights and outputs. The legacy
flow lacks job-ID cancellation and requires manual model switching.

## Verification scope

- FLUX: official sample produced a 366,054-byte PNG in 28.16 s, including cold
  loading and restoring the display container.
- Pixal3D: same sample produced a 4,194,680-byte GLB in 159.13 s. The original
  million-face/4096-texture export exceeded the budget; classroom export passed.
  This verifies format and transport, not visual quality approval.
  Its opaque RGB variant also passed: 4,039,396 bytes in 173.425 s. RGB inputs
  reuse the already pinned TRELLIS RMBG-2.0 weights before the RGBA Pixal runner;
  that preprocessing model is unloaded before Pixal inference.
- TRELLIS: new single-job lifecycle produced a 4,274,036-byte GLB in 158.88 s.
- Wan: new lifecycle produced 33 H.264 frames at 24 fps, 960×928, 1.375 seconds,
  1,557,963 bytes in 245.67 s.
- VoxCPM2: all three public synthetic references matched their original SHA-256
  hashes. Female/male/child samples produced 5.76/4.96/7.36 seconds of valid
  24 kHz mono PCM16 in 32.484/32.996/31.937 seconds respectively. Each request
  cold-loads its model; this WAV endpoint does not preserve the old Mac model's
  streaming first-audio latency. Subjective voice approval remains with the user.
- Named cancellation: a Pixal request queued behind Wan stopped in 0.059 s;
  cancelling a running FLUX request through the Mac tunnel returned in 11.891 s,
  and no task container remained. The 7040 viewer returned HTTP 200 afterwards.
- Step1X: original v1 checkpoint, VAE and five encoder weight files passed
  SHA-256 verification. FP8 plus server CPU offload produced a 407,587-byte PNG
  in 66.568 s at size level 512. One-second polling observed a device memory
  peak of 17,985 MiB; this is sampled device use, not an exact allocator peak.
  The background edit completed but fine details changed visibly, consistent
  with its experimental backup status. This does not replace a classroom
  drawing fidelity evaluation.
- `extra/test_media_server.py` uses a fake worker to verify explicit selection,
  no fallback, invalid input, queue bounds, named/early cancellation and cleanup
  failure handling. These tests are separate from real generation evidence.
