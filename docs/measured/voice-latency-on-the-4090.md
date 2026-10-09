# Where the voice wait actually went

The teacher's page sat on "正在准备声音…" for half a minute and looked
frozen. It was not frozen. Speech worked; almost none of the wait was speech.

Measured from the classroom Mac through `local-first`, against the real page endpoint
`POST /api/courses/{id}/speech`, `tts.studio` → `remotevoice` → VoxCPM2 on the 4090.

## The wait was fixed, not proportional

Two requests of very different length, before any change:

| Text | Time to first audio | Speech produced |
|---|---|---|
| 6 characters | 30.1 s | 1.60 s |
| 57 characters | 33.9 s | 13.44 s |

Nine times the speech cost 3.8 s more. Fitting those two points: **0.07 s per character of
generation on a 29.6 s fixed toll**, paid per sentence whatever its length.

## Where the 29.6 s went

Instrumented inside the worker container, plus wall clock around it:

| Stage | Cost |
|---|---|
| `docker stop beyond-canvas-trellis2` | 10.7 s |
| Container start | 1.0 s |
| Python imports | 1.5 s |
| `VoxCPM.from_pretrained` | 8.2 s |
| `build_prompt_cache` | 6.5 s |
| **Generation** | **1.6 s** |
| Cleanup, restart | ~1 s |

Two of those were avoidable without holding any VRAM.

**The 3D container stop bought nothing.** `beyond-canvas-trellis2` declares no `StopSignal`,
so Docker waits its full 10 s timeout and then kills it. It was stopped to free the card —
but an idle TRELLIS holds *no* CUDA memory: `--query-compute-apps` sums to 0 MiB with it
running, well under the 1536 MiB guard the job checks anyway. Speech now stops it only when
that guard would actually trip; every other kind still stops it unconditionally.

**The prompt cache is the same tensor every time.** `build_prompt_cache` returns
`{'ref_audio_feat': Tensor(33,4,64) float32, 'mode': 'reference'}` — 27–56 KB, and
`torch.save`/`torch.load` round-trip it in 0.0 s. Precomputed per voice by
`build_voice_cache.py`, named by a fingerprint of the reference wav plus the pinned model
revision so a stale cache cannot be read.

The feature comes back **on the CPU** and the model moves it itself. Moving it to CUDA when
loading — the obvious thing, and wrong — fails deep inside `_make_ref_prefix` as a device
mismatch, nowhere near the line responsible. Two fixes were spent on that before comparing a
fresh cache against a loaded one, which showed it in one line.

## Result

| | Time to first audio | Fixed toll |
|---|---|---|
| Before | 30.1 s | 29.6 s |
| Not stopping the 3D container | 19.6 s | 19.1 s |
| Also reusing the prompt cache | **13.0 s** | **12.5 s** |

Same text through the page: "正在准备声音…" at 0.2 s, "正在朗读…" at **13.9 s**, done at 16.7 s.

Audio is unchanged. The same sentence generated before and after is 72,960 samples both
times, with a maximum difference of **5 parts in 32,768** — GPU rounding, not a different voice.

## What is still paid, and what it would cost to remove

`VoxCPM.from_pretrained` at 8.2 s now dominates, and only a resident model removes it.
Measured against that: the weights hold **366 MiB** once loaded and about 1 GB after the
prompt cache — under the 1536 MiB guard — but generation peaks at **6.5 GB**, and PyTorch's
allocator keeps that peak unless `empty_cache` is called. A resident worker therefore has to
release explicitly or it will refuse every image, video and 3D job on the box.

Nothing streams. VoxCPM2 generates progressively and `voice_worker.py` iterates its streaming
generator, but concatenates to one WAV; `remotevoice.py` then buffers that whole WAV before
yielding. Every audio chunk lands within the same millisecond at the end, so the page's own
`voice.preparingProgress` display can never fire.

## Residency, measured and not built

The remaining 8.2 s is `VoxCPM.from_pretrained` on every request, and only a resident
model removes it. Two ways to hold one, both measured on the 4090 in the shipping
container. Neither is shippable as it stands.

**Resident on the card: 5836 MiB, idle.** Not the ~366 MiB an earlier sample suggested —
that reading was another process. After a generation it is 6332 MiB, and
`torch.cuda.empty_cache()` returns almost nothing: 6084 MiB. The guard in
`media_server.py` refuses any job while compute apps hold more than 1536 MiB, so a
resident voice would refuse **every image, video and 3D request** for as long as it was
up. Generation itself is 1.80 s cold and 1.02 s warm, so the prize is real — but not at
that price.

**Resident in host memory, moved across per request: the model does not survive it.**
`.to('cuda')` moves the parameters and nothing else. `tts_model` keeps its own `device`
attribute, still reading `cpu`; setting that by hand gets further and then fails inside
`minicpm4/model.py`, where the KV cache is allocated on the recorded device while the
states arriving are on the card. That is at least three places holding device state, two
of them internal to the vendored library. Making it work means patching VoxCPM internals,
which breaks on their next revision and fails as a wrong-device error far from the cause —
the same shape of bug as the prompt-cache device mistake above, which cost two fixes.

**What is left, in order of honesty:**

- Scope the guard so the voice service is not counted, and accept ~6 GB permanently held
  of the card's 24. Needs the peak of FLUX.2, Wan 2.2 and TRELLIS.2 measured first, since
  the guard exists precisely to stop them colliding. Not attempted.
- Stream what is already generated: worth about 1.5 s of the 13 s, because generation is
  the last 1.6 s. Only pays off once the model is already loaded.
- Leave it. StepFun First is the default and speaks in 3–5 s; this 13 s is Local First
  only, which is the offline and Spark path.

Nothing in this section was built. The probes ran in throwaway containers and changed no
service.
