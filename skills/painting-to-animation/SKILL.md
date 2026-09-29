---
name: painting-to-animation
description: Creates a short Wan video preview from a child's drawing. The classroom preserves the original, screens the generated clip, holds back a clip with a person's hands or art tools painted in, and can reuse it in storybook pages.
allowed-tools: painting-to-animation/choreograph, painting-to-animation/clip_check
license: Apache-2.0
compatibility: Python 3.13, Pillow, ffmpeg, httpx and the configured video.animation service. StepFun First runs Wan 2.2 I2V A14B on the DGX Spark itself.
metadata:
  author: beyond-canvas
  version: "0.6"
---

# Painting to animation

## Current classroom path

The classroom creates one short video preview through `video.animation` when
the teacher chooses **Generate short video preview**. `Conversation.animate`
calls [studio/making/animation.py](../../studio/making/animation.py) directly; it does not use
a chat model to plan or generate the clip. The original drawing is always the
input, so repeated edits do not accumulate visual drift.

The child's words are bounded to 600 Unicode characters and quoted inside an
instruction that says the painting is finished and nobody is painting it, asks
for a fixed camera and movement of the painted figures only, forbids hands,
brushes and people entering the frame, and keeps the original marks, colours,
characters and composition. That wording replaced a shorter one,
after that one put two hands holding brushes into a clip.

## Output and privacy

The response is `{video_url, language}` and contains an embedded H.264 MP4. The
original drawing remains unchanged. The configured safety model screens the
input and five decoded frames before publication. Then
[scripts/clip_check.py](scripts/clip_check.py) shows the same model one sheet
with the original beside the five frames and asks whether a person's hands or
arms, a person, or an art tool was painted in
([its instruction](assets/prompts/clip-check.txt)). Such a clip is held back with
the code `clip_held_back`, and the teacher is told they can press again; the new
try asks the video service for a different start, since the same start would
paint the same clip. It does not look for other additions, such as a paw that
grows fingers or an extra figure: asking about those held back good clips in
testing ([measured](../../docs/measured/clip-hands-and-check.md)). A check that
gives no usable answer does not hold back a clip that passed screening: the
ledger records `clip check unavailable`. Credentials and vendor URLs are not
returned to the page or written to the ledger. A successful result is cached for
the drawing; a failed media request is never automatically retried.

## Bounds

- One active Wan generation across tablets; an occupied slot returns busy.
- Downloads restricted to HTTPS Replicate delivery hosts, no redirects, maximum 12 MiB.
- Decode five frames for screening; each frame is bounded to 4.5 million pixels.
- Unchanged words reuse a successful, screened result without another model call.
- Configured Replicate polling timeout 300 seconds. This is a client wait limit,
  not proof that an accepted cloud job is canceled if the connection is lost.
- Wan clips are H.264, at most 10 seconds and screened at five decoded frames.

## Verification and legacy workflow

`tests/making/test_video_animation.py` covers validation, screening, caching and
storybook reuse. The still pose picture teachers could choose instead, made by
FLUX.2 Klein through `image.edit`, was retired: Wan makes the real
animation. Still pictures made before that remain in the Portfolio. Current model
choices and wait limits are defined in [deployment versions](../../docs/guides/deployment-versions.md).

The standalone `scripts/choreograph.py`, its `evals/evals.json` and the old
browser mesh player remain available for historical local-deformation experiments
and saved choreography. They are not the current classroom model path.
Their [earlier validation](../../docs/measured/local-animation-repair.md)
does not establish the quality of the Wan preview.
