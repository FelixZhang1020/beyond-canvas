# Hearing on the node's own chip, beside StepFun

**Operator's question: could a child's voice stop leaving our hardware?**

Every class sends a child's recording to StepFun for transcription
(`stepaudio-2.5-asr`). The Spark's chip is idle between jobs and Whisper's weights are open, so the
recording could be transcribed on the node instead. This is what that would cost in accuracy.

## What was run

`deploy/spark/hearing_worker.py` in `beyond-canvas/hearing:1` (NVIDIA's PyTorch image, ffmpeg,
transformers), Whisper large-v3-turbo from ModelScope (1.6 GB in `~/models/whisper`), on port 7290,
the port the hearing slot has always named. It answers `/inference` exactly as the whisper.cpp
server did, so `studio/transcribe.py`'s existing client reaches it unchanged.

Six sentences a child might say about a drawing were spoken by the studio's own voice
(`stepaudio-2.5-tts`, the class's voice), then given to both services. Scoring is by characters
that differ, punctuation ignored, because the two punctuate differently and neither is wrong.

## What came out

| | Characters wrong | Median time |
|---|---|---|
| The node's Whisper, on the chip | 2 of 93 (2.2%) | 0.20 s |
| StepFun `stepaudio-2.5-asr` | 0 of 93 (0%) | 0.42 s |

Five of six sentences came back perfect from the node. The errors were homophones inside a correct
sentence shape; a second run with freshly spoken clips made one error of the same kind in a
different sentence. StepFun made none. The node answered in about half the time, because nothing
leaves the machine.

Memory while transcribing: about 2.4 GiB, with the chip at roughly a fifth. A model load takes
about 80 s, once, at start.

## What this does not say

The project keeps no recordings, by design, so there was no real class audio to test with. These
clips are an adult synthetic voice reading clean sentences: they measure the plumbing, the Chinese
wording and the speed, not how either service copes with a five-year-old in a noisy classroom,
which is the case that matters and where both would do worse.

## What it would change if adopted

A child's recorded voice would stop leaving the hardware the operator rents — the promise this
project once made and later reversed. Speech back to the child stays bought either way:
StepAudio's voice has no open weights.

The teacher already sees the transcript and decides whether it is what the child said
(`studio/transcribe.py`), which is the check a homophone error runs into.

Not adopted yet: nothing in the class points at it. `studio/profiles/stepfun.yaml` still resolves
`speech.in` to StepFun, and `deploy/spark/start.sh` does not start the worker.
