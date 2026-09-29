# Video input to Step 3.7 Flash: measured, and rejected

Measured against `stepfun/step-3.7-flash` through OpenRouter, provider
pinned to StepFun, `reasoning.effort = low`.

## Why this was tested

The design proposed sending the child's whole explanation video to the model, on
the strength of OpenRouter's metadata declaring `input_modalities: [text, image,
video]`. The operator doubted the model could handle video. Nobody had tested it.
NVIDIA's own NIM documentation for this model says text and image, not video, so
the evidence was contradictory before the test.

## Method

Three frames, each a large high-contrast shape on white, one per second: a red
circle, then a blue square, then a green triangle. The same content delivered
three ways, with the same question: list the shapes and colours in order, and say
`ONLY ONE FRAME` if only one frame is visible.

## Result

| Delivery | Prompt tokens | Answer | Correct |
|---|---|---|---|
| Animated GIF as `image_url` | — | `ONLY ONE FRAME.` | reads frame 1 only |
| Real MP4 as `video_url` | 622 | red circle, blue square, **blue square** | 2 of 3 |
| The 3 frames as 3 separate `image_url` parts | 562 | Circle red, square blue, triangle green | **3 of 3** |

A malformed `video_url` returns `video exception: format damaged` from StepFun
rather than an unknown-field error, which is how we know a real video path exists
behind the endpoint.

## Verdict

Video input works but is not accurate enough to use. The model missed one of three
large, unambiguous, one-per-second shapes. It cannot be trusted to track where a
child's finger points across time.

Sending frames as images is more accurate **and** cheaper: 562 tokens against 622.

## What changed because of this

Frames are sampled from the child's video and sent as images. Frame selection is
aligned to the transcript's timestamps, so a frame is taken at the moment the
child says a pointing word such as 这里, 那个 or 这边. That is more precise than
the whole video would have been, because it captures the gesture at the instant
the word is spoken.

Animated GIF is useless for this and must not be used to smuggle motion in.

## Reproducing

Build a three-shape MP4 with `imageio` plus `imageio-ffmpeg`, base64 it into a
`video_url` content part, and compare against the same frames sent as `image_url`
parts. Note that a small `max_tokens` returns empty content on this model; the
video call needed 6000 to answer at all. See
`docs/measured/judge-token-budget.md`.
