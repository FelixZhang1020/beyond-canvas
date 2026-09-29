# The media models, on two real drawings

Measured the first time any media model in this product was run on
work a child actually made. The operator supplied both drawings: a savanna
painting in acrylic — cheetah, giraffe, zebra, tree, sun — and a graphite
geometry study of a cube, sphere and cylinder.

Three of the four things tried worked. The one that matters most produced an
answer that looks good and is wrong, which is the reason this file exists.

## 抽象挂画 removed two of the three animals

`image.edit`, `Qwen/Qwen-Image-Edit` on SiliconFlow. 30 seconds, about 3 cents,
prompt asking for an abstract piece keeping the palette and composition.

**What came back was not abstract, and it was not the child's picture.** The
giraffe and the zebra are gone. The cheetah has been repainted in a smooth
commercial style with an adult's anatomy. The brushwork — the thing a parent
would recognise as their own child's hand — is gone.

Section 5b permits exactly one output to make something new: *"it is not 'your
drawing', it is 'a piece grown out of your drawing'."* Deleting two of three
subjects is not growing something out of a drawing. It is replacing it. The same
paragraph rejects video diffusion as "a betrayal at the pixel level"; this is the
same betrayal reached by a different route, and the instruction not to do it was
in the prompt.

**What this does not settle.** One prompt, one model, one drawing. The prompt
asked for a lot at once — abstraction, palette, composition, no faces — and a
weaker instruction with a stronger structural constraint may behave differently.
What it does settle is that **this output cannot be shipped on the strength of
looking good in a thumbnail.** It needs a person to compare it against the
original every time, which is what the rubric does for the writing and what
nothing yet does for the pictures.

## The voice works, and only on one route

`tts.studio`, `FunAudioLLM/CosyVoice2-0.5B` on SiliconFlow. About 3 seconds a
line, eight system voices, audio returned inline as MP3.

Two things had to be discovered against the live API, neither documented:

| | |
|---|---|
| Two clouds, one key | A `cloud.siliconflow.cn` key gets `{"code":30014,"message":"Token is invalid."}` from `api.siliconflow.com`. It reads as a bad key rather than the wrong country |
| The voice needs its model | A bare `anna` is refused as "Invalid voice". It must be `FunAudioLLM/CosyVoice2-0.5B:anna`, and `/v1/audio/voice/list` returns only voices you uploaded, so nothing lists the presets |

**Replicate cannot serve this slot at all.** Its CosyVoice requires
`source_audio` and `source_transcript` on *every* mode including instructed
generation — there is no preset voice. The note in `cloud.yaml` claiming
Replicate keeps the instructed mode available as a fallback was wrong and is
corrected.

That has a consequence beyond convenience. Cloning the child's voice for layer
three needs the child's recording sent to a vendor, and `studio/transcribe.py`
refuses to send a child's recording anywhere for transcription. **In Phase 0
those two positions contradict each other.** On the Spark they do not, because
nothing leaves the box. Until then, layer three's narration should use a preset
voice rather than the child's.

## 3D did not start in half an hour

`mesh.fast`, `tencent/hunyuan3d-2` on Replicate, from the geometry study.
Submitted, accepted, and still in `starting` thirty minutes later with no error
and no metrics. Cancelled rather than left to bill.

This is a cold start on a model nobody has run recently, not a defect, and a
warm one would be far quicker. But it settles the question the profile comment
already suspected: **the hosted 3D route is not a preview of the shipped
feature.** It is a different model from the InstantMesh the box will run, and it
cannot answer fast enough to tell anyone anything about what a child would
experience. 3D belongs on the Spark, once it arrives.

> **Corrected the same day.** Both halves of that paragraph turned out wrong once
> the call was retried warm. Hunyuan3D returned a valid mesh of 20,008 vertices
> in **19 seconds** of compute, and InstantMesh — now the slot's model, so no
> longer a different one — did it in **16**. The thirty minutes was entirely cold
> start. Hosted 3D is a usable preview after all, and the free HuggingFace Spaces
> make it cost nothing. Point 3 below is withdrawn; what replaces it, and the
> reason the reconstruction still loses a low-contrast form, is in
> `sketch-to-3d.md`.

## What the language models did

Unchanged and still passing: both `vlm.studio` and `vlm.director` on OpenRouter,
exercised by `tests/live/test_live_openrouter.py`.

## What to do about it

1. **Do not ship 抽象挂画 without a check.** Either a rubric rule that compares
   the output against the original for missing subjects, or a teacher confirming
   before a parent sees it.
2. **Layer three narrates in a preset voice in Phase 0**, not the child's.
   *Adopted: `tts.export` now serves a preset voice, cloning deferred.*
3. ~~**Stop testing 3D online.** Wait for the box.~~ **Withdrawn the same day** —
   the thirty minutes was a cold start, and warm calls take 16 to 19 seconds. Test
   3D online; the free Spaces cost nothing. See `sketch-to-3d.md`.
