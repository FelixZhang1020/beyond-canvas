# Chat speed: four ways of writing, and a fast front voice on the node

**Operator's question:** every chat line took 20 s to over a minute, and "the interaction should be
about 5 seconds". Why, and which model on the StepFun subscription or on the Spark itself could get
there.

## Why a chat line is slow

Step 3.7 Flash thinks before every answer and cannot be told not to. StepFun's API reference lists
`low` as the lowest `reasoning_effort`; StepFun's staff wrote on Hugging Face that the model "does
not support a nothink mode". Tried on the node, all accepted and all still thinking:
`reasoning_effort` `none` and `minimal`, `thinking: {type: disabled}`, `enable_thinking: false`,
`chat_template_kwargs`, `reasoning: {enabled: false}`, an empty-think prefill, and the Messages API
(`/v1/messages`, the one coding tools use) with thinking disabled.

How long it thinks depends on what it is asked: a one-line prompt answered in 4-7 s (340-680
tokens); the class's rule-heavy opening prompt took 17-22 s (about 2,200 tokens).

On the subscription only `stepaudio-2.5-chat` answers without thinking (0.2-0.5 s), and it cannot see
pictures: it became the `chat.bridge` slot (`studio/bridge.py`). `step-3.5-flash` and
`step-router-v1` refuse images; `step-5-preview` reads them but thinks (5-9 s).

## Four ways of writing the chat lines, Step 3.7 Flash

Nine drawings (six colour, three sketches) with a child's answer each, through the real classroom
code on the node, judged by the class's own rubric. Four arms ran at once, and StepFun's limit of
**8 requests at the same time** answered 429 twice, so every time here is somewhat slower than a
class would see.

| Way | Reply, typical | Reply, worst | Opening, typical |
|---|---|---|---|
| The class's prompts | 42 s | 114 s | 40 s |
| Short prompts (about a fifth of the length) | 27 s | 89 s | 50 s |
| The class's prompts, two drafts raced | 28 s | 50 s | 51 s |
| Short prompts, two drafts raced | 20 s | 37 s | 38 s |

- **Short prompts wrote thinner lines.** The rubric refused them 10 times for sentences too long for a
  child and 3 times for the forbidden word 简单, and sketch replies lost the located technical read
  (the class's prompts: the cast shadow at bottom right is too hard and dark, soften it and keep the reflected
  light; short: general tips about tissue paper).
- **Racing two drafts did not change quality**: both go through the same rubric, the first to pass is
  shown. It roughly doubles the calls on the subscription.
- **What the rubric refuses most with the class's prompts:** rule 14 (the machine adds story the child did
  not tell, "the storm is rotating") and rule 4 (it names a shape the child never named, "a dragon").
- **Openings did not get faster by any of the four ways.**

Scripts: `prompt_trial.py` and `cases.tsv` in the session scratchpad (not committed); the short
prompts were a scratch folder, and the class's prompts were not changed.

## A front voice on the node: NVIDIA Nemotron Nano 12B v2 VL

`nv-community/NVIDIA-Nemotron-Nano-12B-v2-VL-NVFP4-QAD` from ModelScope (10.6 GB listed, 9.9 GB on
disk), served by `nvcr.io/nvidia/vllm:26.08-py3` on 127.0.0.1:7150 with a 0.15 memory share and a
32 GB container cap (`~/nemotron/serve-vl.sh` on the node); ready in about 3.5 minutes, the node at
64 GB free while it was up. Thinking off with the card's system message `/no_think`. The same nine
drawings and answers, the class's own prompts, the class's rubric with Step 3.7 Flash at high effort
as judge.

| | Write time | Passed the rubric first time |
|---|---|---|
| Opening | 2.2-8.1 s (one 13 s; the very first call 22 s, warm-up) | 5 of 9 |
| Reply | 1.0-3.7 s (one 8 s) | 7 of 9 |

About ten times faster than Step 3.7 Flash. Read line by line, its Chinese is weaker:

- **English inside a Chinese reply**, copied from the prompt's own example: a reply ended "You drew
  the road that long because they walked a long way?" The rubric refused that reply, but for rules 10
  and 14; no rule looks for the wrong language in a reply.
- **Repetition**: on the sphere study it wrote the same four sentences twice and stopped mid-word
  (refused, rule 12).
- **The child's words parroted, first person kept**: 「猫的耳朵比例我改了好几次。」 where the prompt asks
  for "your". The rubric passed it.
- **Possibly seeing what is not there**: on one colour drawing it described a unicorn and a birthday
  cake with candles, where Step 3.7 Flash saw fireworks and a pink dragon. Refused, but only for
  sentence length (rule 10); nothing checked what it claimed to see.
- Yes/no questions (「是不是因为……？」) passed in replies, and the forbidden 简单 was refused.

Its model cards disagree on Chinese (the FP8 card lists it, the BF16 card says "English only"); the
lines above are the evidence. Results: `/tmp/bc_vl_trial_nemotron.jsonl` on the node, copied to the
session scratchpad. The server was stopped after the run; the weights stay in
`~/models/nemotron-nano-12b-v2-vl-nvfp4`.

## A front voice on the node: Qwen3.6-35B-A3B, NVIDIA's NVFP4

`nv-community/Qwen3.6-35B-A3B-NVFP4` (22.4 GB on disk) in the same vLLM image on 127.0.0.1:7160
(`~/nemotron/serve-qwen.sh`). A 0.28 share failed to start ("No available memory for the cache blocks");
0.38 of the node (about 46 GB, container capped at 56 GB) started: weights 20.4 GiB, KV cache 2.1 GiB.
Thinking off with `chat_template_kwargs: {enable_thinking: false}`. Same nine drawings, answers, prompts
and judge as Nemotron above.

| | Write time | Passed the rubric first time |
|---|---|---|
| Opening | 0.7-1.3 s | 8 of 9 (one rule 4, a sketch opening that presumed) |
| Reply | 0.4-1.0 s | 9 of 9 |

About thirty times faster than Step 3.7 Flash, and read line by line close to it: grounded in what is on
the page (「我看到画面左上角有一轮黄色的太阳，右边是一只紫色的动物……」 where Step saw the same), the
child's "I" turned into "you" (「你说影子最难画……」), questions about the world inside the picture
(「如果站在这条河边，会听到什么样的声音呢？」). Weaker than Step: some replies end in a yes/no question
(「是想用这种方式吓跑别人吗？」; Step does this too, and no rule checks a reply's question), it called one
pink creature a pony where Step said it looks like a dragon, and sketch advice names less exactly where on
the page. The server was stopped after the run: at about 46 GB it would have to step aside for a Wan clip
the way TRELLIS.2 does. Results: `/tmp/bc_vl_trial_qwen.jsonl` on the node.

## Other NVIDIA candidates, from their own pages

A separate session listed NVIDIA models that could fill a studio job. Checked against the model pages
and ModelScope from the node:

| Model | Job | Finding |
|---|---|---|
| `nvidia/nemotron-3.5-asr-streaming-0.6b` | hearing | Lists Chinese, 2.4 GB on ModelScope, needs transformers ≥ 5.13. Its own card gives Mandarin a character error rate of 19.28. **Measured below: 6 of 93.** |
| `nvidia/magpie_tts_multilingual_357m` | the studio's voice | Lists zh among 12 languages, 22.05 kHz, five speakers named Aria, Jason, Leo, Sofia and John. The ModelScope mirror is an empty shell; the 1.47 GB `.nemo` came from hf-mirror.com. **Measured below.** |
| `nvidia/Cosmos3-Edge` | the clip | 4B, image to video at 480p; NVIDIA's own DGX Spark figures are 166-180 s, against Wan's 691 s. Needs `Cosmos3OmniPipeline`: diffusers 0.40.0 from the Tsinghua mirror has it (built as `beyond-canvas/cosmos3:1` on the node, with transformers 5.17). Takes a structured JSON prompt, not a sentence. **Tested below: fast, and repaints the child's work.** |
| `Qwen3.6-35B-A3B`, NVIDIA's NVFP4 (`nv-community/Qwen3.6-35B-A3B-NVFP4`) | front voice | Reads pictures; thinking off by `chat_template_kwargs: {enable_thinking: false}` (official); 3B active of 35B; 23.5 GB listed, 22.4 GB on disk. **Measured below: the strongest.** |

## The clip: Cosmos3 Edge beside Wan 2.2

The six drawings and requests of [the Wan hands test](clip-hands-and-check.md):
corgi, dog, lions, flamingos, rabbits, giraffe. Step 3.7 Flash filled Cosmos3's JSON prompt for each
from the drawing and the request, with wording B's rules written in (finished painting, only the
painted figures move, still camera, keep the brushstrokes, nothing enters the frame): 19-25 s a
prompt. Cosmos3 Edge then ran at the card's settings, 480p by area, 121 frames at 24 fps (5 s),
20 steps, guidance 6, seed 42, its own negative prompt, under the shared GPU lock with the 24 GiB
floor (`~/spark-tests/run_cosmos.sh`, `cosmos_clips.py`, image `beyond-canvas/cosmos3:1`).

| | Cosmos3 Edge | Wan 2.2 A14B, wording B |
|---|---|---|
| Time per clip, model loaded | 98-103 s for 5 s of video | 454-472 s for 3 s of video |
| Peak memory | 12.3 GiB | about 85 GiB for a class clip |

Side by side (Wan left), start, middle and end frames:

- **Corgi**: the flat painted corgi becomes a realistic furred, shaded dog with a glossy tongue.
- **Dog**: repainted as a realistic spaniel; a pink blob where the raised paw should be.
- **Lions**: the lion becomes realistic, bright orange mane, roaring.
- **Flamingos**: a new realistic bird with dark spread wings is painted over the flamingo.
- **Rabbits**: the child's line-drawn rabbits are replaced by two 3D doll figures, a girl in a pink
  dress and an orange fox. New figures the child never drew.
- **Giraffe**: closest to faithful; the giraffe lowers its head, the zebra's head changes.

Wan kept the painting style in all six. The written instruction to keep the brushstrokes did not
hold Cosmos3 to the drawing: at these settings it does what the project rejected Qwen-Image-Edit for,
and replaces the child's work. Not usable as it stands.

**Round 2, the same afternoon:** guidance 3.5 (Wan's) instead of 6, and a negative-prompt subject naming
round 1's failure (photorealistic animals with realistic fur, glossy 3D figures, plush dolls or toys, new
characters, CGI replacing the brushstrokes). 99-107 s a clip. Wan | round 1 | round 2 side by side: the
same failures in every clip. The rabbits still became two dolls, the corgi, dog and lion stayed realistic,
the realistic bird still spread over the flamingo. A firm no for the clip at these settings. Clips and
side-by-sides: `~/spark-tests/cosmos-compare/` on the node (`three-<n>.mp4`, `sheet3-<n>.jpg`).

## Hearing and voice, NVIDIA's candidates

**Getting them onto the node.** ModelScope's copy of the ASR model holds only the `.nemo` file, not the
transformers files the card's code loads; those, and Magpie's `.nemo`, came from **hf-mirror.com, which the
node reaches** (huggingface.co it does not), rate-capped like `fetch_weights.py`. The ASR ran in
`beyond-canvas/cosmos3:1` (transformers 5.17, plus librosa, which its feature extractor needs); Magpie in
`beyond-canvas/magpie:1` (NVIDIA PyTorch 26.08 + `nemo_toolkit[tts]==3.0.0` from the Tsinghua mirror).
NeMo's audio codec loads a speaker encoder from a huggingface.co address written into its code
(`nemo/collections/tts/models/audio_codec.py`); the image rewrites that one address to hf-mirror.com.
Neither image reads audio by file name without ffmpeg, so the scripts read WAV with scipy.

**Hearing.** The six sentences of [the hearing test on the node](hearing-on-the-node.md), spoken again by
the class's voice, heard by all three; the clips deleted after (`~/spark-tests/run_asr.sh`).

| | Characters wrong of 93 | Median time |
|---|---|---|
| StepFun `stepaudio-2.5-asr` (the class's) | 0 | 0.44 s |
| Whisper large-v3-turbo on the chip | 0 | 0.17 s |
| NVIDIA Nemotron 3.5 ASR Streaming 0.6B, `language="zh-CN"` | 6 (6.5%) | 0.07 s |

Nemotron's six: 它→他 three times and 棵→颗 (sound-alikes, the same when spoken), a dropped comma's
worth of nothing, and one real error, 很远的地方 → 横院的地方. Better than its card's 19%, worse than
Whisper, which already runs on the node. Adult synthetic voice, clean audio: not a child in a classroom.

**Voice.** Eight lines (the six sentences and two real feedback lines from the front-voice trial) spoken by
StepFun's class voice and by Magpie's two female speakers, Aria and Sofia; Whisper then transcribed every
recording as a check that the words can be recovered (`~/spark-tests/run_voice.sh`).

| | Whisper got wrong, of 188 | Time to make one line |
|---|---|---|
| StepFun `stepaudio-2.5-tts` (the class's) | 1 | about 1.8 s a sentence (measured earlier) |
| Magpie, Aria | 1 | 1.0-1.2 s for 3 s of audio, 3.2-3.3 s for 9.5 s |
| Magpie, Sofia | 0 | 0.9-1.3 s for 3 s of audio, 3.4-3.5 s for 10 s |

Model load 64 s. Magpie's Mandarin is intelligible and fast on the node. Whether it sounds like a warm
teacher is a judgement by ear: the 24 recordings are in `~/spark-tests/voice-test/` on the node.
The operator listened to them and kept StepFun ("StepFun is the better").

## How small Qwen3.6 can run, and the decision

Could Qwen stay loaded while Wan 2.2 makes a clip? Wan takes about 85 GB and the node must keep 24 GB
free, which leaves about 12 GB beside it. Each setup below was started on its own, timed on the same
nine openings and replies (no judge), and stopped (`~/spark-tests/qwen_trim.sh`, results
`/tmp/bc_qwen_trim_*.txt` on the node).

| Setup (share of the node, context, parallel requests) | Result |
|---|---|
| 0.38, 16384, 4 | Started in 232 s. Weights 20.4 GiB, KV cache 3.61 GiB; the node went from 39 to 89 GB used. Opening 1.02 s typical (1.24 s worst), reply 0.59 s (1.19 s) |
| 0.25, 8192, 2 | Did not start |
| 0.20, 8192, 2, no CUDA graphs | Did not start |
| 0.16, 4096, 1, no CUDA graphs | Did not start |
| 0.28, 8192, 2, one image per request, 4096-token batches, no image cache | Did not start: "Available KV cache memory: -7.87 GiB" |

vLLM needs about 42 GB before it has any room for the conversation itself: 20.4 GiB of weights and
about 21 GB of warm-up working space. That leaves 0.38 near the smallest share that works. So Qwen and
a clip cannot share the node (85 + ~50 + 24 floor is about 155 GB of 121). Qwen must step aside for a
clip, as TRELLIS.2 does, with chat falling back to Step 3.7 Flash until it is loaded again (about 4 minutes).

**Decision (operator): Qwen3.6 becomes the first voice.** It writes the opening and the
reply, Step 3.7 Flash still checks each line against the rubric before it counts, and Qwen steps aside
for clips. The comparison the decision was made on is the measurements above.

## What this does not say

Nine drawings and one run per arm: the rates are these lines, not general accuracy. The drawings are
the art centre's generated samples and a few synthetic fixtures; no child spoke. Until the decision
above, nothing here changed what a class uses.
