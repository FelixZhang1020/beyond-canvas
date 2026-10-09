# Wan 3.0 online: speed and faithfulness beside Wan 2.2 on the Spark

The whole test took ten minutes. Operator: "as you have Dashscope, can you test Wan 3.0 online
version, test the speed?" Same drawing, instruction and action as the Spark's length trial
([clip-length-trial.md](clip-length-trial.md)): the snowy river watercolour,
`VIDEO_PROMPT` from `studio/animation.py` with "The river flows gently past the snowy banks, and a
little snow drifts down.", `prompt_extend` off so the instruction reaches the model as the class wrote it.

Model `wan3.0-video` on `https://dashscope.aliyuncs.com` (the China region; the key answered there), first
frame as a base64 data URI, `ratio: adaptive`, called from the Mac with the key from `.env`, never printed.
Time is from sending the job to the finished file on disk, polling every 10 s, so each figure can be up
to 10 s late. One clip per row, one try each.

| Clip | Wan 3.0 online | File as delivered | Wan 2.2 on the Spark, same length |
|---|---|---|---|
| 5 s, 480P (552 x 740) | **86 s** | 4.4 MB | 1,082 s |
| 10 s, 480P | **107 s** | 9.5 MB | 2,431 s |
| 5 s, 720P | 119 s | 9.0 MB | not made |
| 10 s, 720P (830 x 1110) | 193 s | 17.3 MB | not made |

All at 30 pictures a second (Wan 2.2: 16).

## What it painted

Six pictures spread across each clip, read by eye:

- **Both 720P clips painted in a person paddling a boat down the river**, from about a third of the way
  in, against an instruction that says "absolutely no ... people" and "nothing enters it from outside".
- **Both 480P clips kept the painting** and added no figure, but drew white swoosh lines across the
  water and large falling flakes, marks that are not the painting's own brushwork. They move far more
  than Wan 2.2's clips, which kept the painting and barely moved.

## What the file needs before the studio can take it

`ffprobe` on the 10 s 480P file: an H.264 picture track **and an AAC sound track**, 10.031 s long. The
studio's clip check (`normalize_video`) accepts one picture track of at most 10 s, so the file as
delivered is refused twice over. Re-encoded without sound and cut at 10 s (`libx264 -crf 26 -preset
veryfast`) it was 0.66 MB, from 9.5 MB, in under a second on the Mac.

## Decision

Operator, on seeing these results: keep Wan 2.2 and let the teacher choose each time, shown how long each takes: a
5 s clip on the Spark or a 10 s clip online. Online is made at 480P because of the boat. Both go through
the same safety screen and hands-and-people check. The DashScope key goes to the Spark beside the StepFun
key. The price per second was not on Alibaba's public pages when this was written.
