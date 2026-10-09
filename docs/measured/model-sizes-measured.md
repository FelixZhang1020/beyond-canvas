# Every model, weighed

Until now every size in this project came from the earlier research
pass, which read model cards and vendor pages. These numbers come
from the files themselves.

**Method.** Each repository's file listing was read through
`huggingface.co/api/models/{repo}/tree/main?recursive=true` and the weight files
summed. Reproduce with:

```bash
curl -s "https://huggingface.co/api/models/unsloth/Step-3.7-Flash-GGUF/tree/main?recursive=true" \
  | python3 -c "import json,sys;print(sum(f['size'] for f in json.load(sys.stdin) if f['path'].endswith('.gguf'))/2**30)"
```

**What this does not measure.** A download is not a running process: a loaded
model also needs context and working memory, which is what the 90 GB watchdog
ceiling under the Spark's 128 GB is for. FP8 figures are the standard halving of
BF16, estimated rather than weighed. Nothing here has run on a Spark.

## The roster

Sizes are at the precision section 3 of the design record intends, not the
smallest available.

| Slot | Model | Where | Measured GB | §3 budget |
|---|---|---|---|---|
| vlm.studio | Step3-VL-10B | `seanbailey518/Step3-VL-10B-GGUF` | 15.26 BF16 + 3.69 projector = **19.0** | 24 ✓ |
| vlm.director | Step 3.7 Flash | `unsloth/Step-3.7-Flash-GGUF` | see ladder below | 109 / IQ4_XS ✗ |
| safety.image | ShieldGemma 2 4B | `google/shieldgemma-2-4b-it` | **8.0** | 8 ✓ |
| speech.in | Whisper small q5_1 | `ggerganov/whisper.cpp` | **0.18** | — |
| image.edit | Qwen-Image-Edit | `Qwen/Qwen-Image-Edit` | 53.7 BF16, **≈27 FP8** | 28 ✓ |
| video.scene | Wan 2.2 TI2V-5B | `Wan-AI/Wan2.2-TI2V-5B` | 31.8 BF16, **≈16 FP8** | 15 ✓ |
| mesh.fast | InstantMesh | `TencentARC/InstantMesh` | **6.8** | 6 ✓ |
| mesh.premium | Step1X-3D | `stepfun-ai/Step1X-3D` | **18.3** | 29 — over-budgeted |
| depth | Depth Anything V2-Small | `depth-anything/Depth-Anything-V2-Small` | **0.1** | under 4 ✓ |
| tts.studio | Kokoro-82M | `hexgrad/Kokoro-82M` | **0.3** | under 4 ✓ |
| tts.export | CosyVoice 2 | `FunAudioLLM/CosyVoice2-0.5B` | **4.5** | — see below |
| rig.figure | Animated Drawings | `github.com/facebookresearch/AnimatedDrawings` | ≈1 | superseded |

**Section 3's budgets are sound.** The earlier research read them correctly and
this pass confirms them. Two are generously over-budgeted — `mesh.premium` by
11 GB, `depth` and `tts.studio` between them by about 3 GB — which is the safe
direction and leaves the resident set roughly 6 GB lighter than planned.

## Step 3.7 Flash, the only model whose size is a decision

Every quantisation of the director, measured. The Spark has 128 GB shared with
the operating system; section 7 sets the watchdog ceiling at 90 GB.

| Build | Weights | + projector | Verdict |
|---|---:|---:|---|
| UD-IQ2_XXS | 57.5 | 61.2 | Fits with room; 2-bit quality cost is real |
| UD-Q3_K_M | 83.1 | **86.8** | **Largest that clears 90 GB** |
| UD-IQ4_XS | 88.8 | 92.5 | What §3 names — over the ceiling once vision is counted |
| UD-Q4_K_S | 106.3 | 110.0 | Closest to §7's "109 GB" |
| UD-Q4_K_M | 113.7 | 117.4 | Leaves 10 GB for OS and context |
| UD-Q5_K_M | 136.4 | 140.1 | Does not fit |
| BF16 | 371.1 | 374.8 | Three Sparks |

## Three contradictions this turned up

**1. The design record disagrees with itself about the director.** Section 3 says
`IQ4_XS`; section 7 says `109 GB` and so does `studio/profiles/spark.yaml`. Those
are different models: IQ4_XS is 88.8 GB and 109 GB is roughly Q4_K_S. One of the
two has to go. On the measured numbers **neither fits**: IQ4_XS clears 90 GB only
if the vision projector is left out, and it cannot be, because a director that
cannot see a drawing cannot judge rules 3 and 4.

**2. Nothing anywhere counts the vision projector.** It is 3.7 GB for the
director and 3.69 GB for the studio model, and it is not optional. This is the
same component that was the whole difficulty of getting Step3-VL-10B running on
the Mac, recorded in `local-studio-model.md`.

**3. CosyVoice 3 is not available.** Section 3 names "CosyVoice 3 or
Step-Audio-TTS-3B"; `FunAudioLLM/CosyVoice3-0.5B` returns HTTP 401, so it is
gated or does not exist under that name. `spark.yaml` already says CosyVoice 2,
which is the right call and measures 4.5 GB. `stepfun-ai/Step-Audio-TTS-3B` does
exist, at 8.54 GB, and is the StepFun-native alternative.

## The two configurations, against measured numbers

The earlier research posed these and chose B. Both are re-tested here, because
the numbers that decided it have changed.

**Configuration A — Step only.** One model, Step 3.7 Flash, resident and doing
everything it can do.

| At | Director | Plus the small models it can afford | Total |
|---|---:|---:|---:|
| UD-Q3_K_M | 86.8 | safety 8.0 + depth 0.1 + Kokoro 0.3 | **95.2** |
| UD-IQ4_XS | 92.5 | same | 100.9 |

A fits, and fits better than the earlier research concluded — that pass
assumed 4-bit at 105 GB and never considered Q3, which is 22 GB smaller. But
what A cannot do is unchanged and decisive: **Step 3.7 Flash generates no images,
no video, no 3D and no speech.** There is no room left for a model that does —
the largest gap A leaves is about 13 GB, and `image.edit` needs 27.

So A delivers the feedback loop and, because `painting-to-animation` needs no
generative model at all, the animation scenario too. It cannot deliver
sketch-to-3d, painting-to-scene or the storybook.

**Configuration B — small models accumulation.** The chosen one, and what
`spark.yaml` implements.

| Phase | Measured | §7 budget |
|---|---:|---:|
| Resident: studio 19.0, safety 8.0, mesh.fast 6.8, video 16, depth 0.1, tts 0.3, rig 1 | **51.2** | 57 |
| Big slot, largest occupant: `image.edit` FP8 | **27** | 30 |
| Studio peak | **78.2** | 87 |
| Director alone at UD-Q3_K_M, studio unloaded | **86.8** | 109 |

**B holds, with about 9 GB more headroom than section 7 claims.** Every stage
clears the 90 GB ceiling, and it is the only configuration that can deliver all
five skills.

## What this changes

Nothing about the direction: B was the right choice and remains it. Two numbers
in the record need correcting — the director's quantisation, and the projector
that no budget counts. The rest of section 7's arithmetic survived contact with
the actual files, which is a better result than this pass expected.
