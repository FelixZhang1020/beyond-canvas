# A storybook read in the child's own voice

The operator asked for the storybook to be read in the child's voice ("the storybook didn't tell the story
with child's voice", from the class 彩画课堂 · 语音测试). What they settled, in their words and answers:

- The **whole story** in the child's voice, not only the child's recorded answers played back.
- The voice comes from **聊聊你的画** only: the chat's microphone, not a file the teacher adds, not the ending.
- **Typed only** (or no talk about a drawing): the studio's voice reads that page, as before.
- **One or many voices on one drawing: the first** spoken answer sets the voice, so every page has one voice.
- Kept **with the book until deleted**; **no consent tick** (the design record's own rule set aside, with the
  other one: that a copied voice says only the child's words — the pages are the studio's story).
- Copied **on the Spark**, not by a company, after the StepFun findings below.

Code: `studio/child_voice.py`, `studio/providers/remotevoice.py` (`RemoteChildVoice`),
`deploy/spark/voice_book_worker.py`, `voice_client.py`, `media_spark.py --kind voice` on 7280.

## StepFun first, and why not

References were made by StepFun's own class voice (`wenrounvsheng`, `wenrounansheng`), no child's recording.
Scripts in the session's scratch space; each printed status codes and timings only.

| What | Result |
|---|---|
| Upload a reference on the subscription address (`step_plan/v1/files`) | **404**: the subscription has no file upload, as it has no transcription |
| `audio/voices/preview` on `v1`, references of 1.5, 4.6, 7.0, 14.8 and 22.9 s | all accepted, ~3 s for 35 characters |
| The copy follows the reference | 232 Hz in → 229 Hz out; 170 Hz in → 148 Hz out |
| 122 characters in one request | refused (400) |
| **A second, different sentence in the same voice** | **refused (400, `request_params_invalid`)**, on the same upload and on a fresh upload of the same recording: the preview reads **one sentence per voice** |
| StepFun's lasting copy (`audio/voices`) | **¥9.9 per voice**, charged on creation, kept on StepFun's servers; a delete endpoint could not be confirmed from its documentation ([pricing](https://platform.stepfun.com/docs/zh/guides/pricing/details)) |

A book page is three or four sentences, so the preview cannot read a book, and the lasting copy puts a child's
voice on a company's servers at ¥9.9 a drawing. The operator chose the Spark.

## VoxCPM2 on the Spark

`OpenBMB/VoxCPM2` from ModelScope (4.96 GB, Apache 2.0), `voxcpm` 2.0.3 in `beyond-canvas/voice:1`
(`Dockerfile.voice`: NVIDIA's PyTorch 26.08, VoxCPM without its listed dependencies, torchaudio a stand-in).
The timings below copy from the recording alone; the class copies from the recording and its words (below).
Run with the GPU lock held and under `memory_guard --floor 24`, beside the loaded chat voice and safety reader.

| | |
|---|---|
| Load (not compiled) | 6.4–9.5 s |
| Memory while loaded | 8.3–10.3 GiB, 11.9 at most while reading (`PEAK_GIB['VoxCPM2'] = 12`) |
| Lowest memory available during a run | 43.8 GiB (floor 24) |
| First voice copied after a load | 6.4 s; every later one 0.04 s (the worker warms up on load since) |
| A whole 122-character page | 21.6–30.1 s for 25.5–28.2 s of speech |
| **A sentence at a time** (21–34 characters) | **4.3–6.8 s for 5.0–7.7 s of speech** |
| Fewer diffusion steps (6 for 10) | 3.5–6.3 s for 4.5–8.0 s: little gained, kept at 10 |
| Compiled (`optimize=True`) | load 54.4 s, and slower: 6.5–10.1 s a sentence. Not used |
| The copy follows the reference, whole page | 242 Hz in → 233 Hz out; 280 Hz (a 1.5 s "边玩边游") → 231 Hz; 139 Hz → 87 Hz (the pitch tracker may have halved it) |

So a page is sent **a sentence at a time**: the first is heard after about five seconds, and each is made a
little faster than it is heard, so the reading keeps ahead. A new book is read ahead in the background as soon as
it is bound, and every sentence read is kept with the recording, so the next reading plays at once.

## Through the class page

In the operator's Chrome, on the standard studio, in a colour class made for it (孩子声音朗读测试): the corgi
(作品 12) answered out loud through a stand-in microphone (a recording played into the page's own recorder,
upload and transcription), the dog and its HOME (作品 14) answered only in typing, a book of the two originals.

| What | Result |
|---|---|
| First run | every child's-voice page failed: the worker read the sentence and said ok, and the hand-over borrowed from the picture book waited for its `output.json`. Fixed (`flux_client.main(output=...)`) |
| A man's voice (StepFun `wenrounansheng`) as the stand-in, copied from the recording alone | kept 3.5 s at 148 Hz; the page's five sentences came out at 192, 135, 207, 119 and 140 Hz |
| The same kept recording, one sentence, three ways, run on the node | recording alone 121 Hz; recording and its words 157 Hz; both 148 Hz. **Both since** (the words heard in it are kept with it, unless it was cut at ten seconds) |
| Book made after the answer | the corgi page's five sentences read ahead right away, 3.1–8.6 s each; the page read for 28 s and turned by itself; the typed page read in the studio's voice, with no voice job |
| Opening an older book after the voice had left | first word after **20.7 s** ("正在准备声音…" meanwhile); a book read ahead when it is made has no wait |
| 撤回上一轮 on the page | the recording and its five sentences gone from the Portfolio (0 and 0) |
| A child's voice as the stand-in: a girl designed by VoxCPM2 from a description, no real child (seeds gave 234–313 Hz; seed 1 used, 313 Hz, 6.2 s) | heard correctly; kept 6.1 s with its 22 characters; the book's five sentences at **314–358 Hz**, 4.1–11.8 s each to make for 3.7–12.6 s of speech |
| The operator: "it's still read in Man's voice" | the page played its own saved reading of the same page, kept by text and voice name. Fixed: a child's voice is asked for afresh every time, and the studio's speech memory names the recording. After it the page received exactly the child's five saved sentences (29,421 … 101,037 bytes, byte for byte) |

A side effect of measuring, not of the class: the compiled-mode trial above took enough memory that the chat
voice's keeper stepped aside (qwen-front down for 6 min 30 s). Nothing the class does runs compiled.

## Not measured yet

- **A real child's voice.** Every reference here is synthetic (StepFun's class voices, a VoxCPM2-designed girl);
  how well VoxCPM2 copies a five-year-old in a noisy classroom is judged by ear in the first real class.
