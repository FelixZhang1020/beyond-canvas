# A refused draft's findings, fed to the attempt that follows it

Live verification of 324e59b against real models. The criteria below were
written before the run.

## What was being checked

The change keeps the findings of the last refused scene description or story outline
and hands them to the next attempt of that kind, so a teacher who presses regenerate
without editing anything gets a draft that corrects the fault rather than rewording it.
Tests prove the findings *reach* the model. Only a live run shows whether the model
acts on them.

## Models

| Slot | Profile | Model | Effort |
|---|---|---|---|
| `vlm.creation` | `stepfun` | `step-3.7-flash` (StepFun) | medium, 12000 max tokens |
| `vlm.director` | `stepfun` | `step-3.7-flash` (StepFun) | high, 16000 max tokens |
| `safety.image` | `stepfun` | as the profile resolves it | — |

`api`, `local-first` and `stepfun` resolve these two slots identically, so the
deployment does not change what is measured here.

## The drawing and why this dialogue

`Image Sample/Color Artwork/Weixin Image_20260903223101_100_645.jpg` — a watercolour
of snow-capped mountains, a dark river, bare trees, and **two** buildings: a wooden
cabin with a porch in front, a smaller red-roofed house behind it.

The child is given the line 「我画了三间房子，河边那间是我家」 — *I drew three houses, the
one by the river is mine*. Three is not what is on the paper. This is the same shape as
the case that prompted the change and it is the conflict the independent reviewer exists
to catch: whichever number the creator uses, it contradicts either the image or the
child. Nothing is fabricated to force this — children misremember their own drawings,
and the reviewer is the thing that is supposed to notice.

**A refusal is the reviewer's call and does not happen every time.** Across the run,
three of five first drafts were refused and two passed. The script asks for fresh first
drafts until one is refused, then presses regenerate on that conversation with nothing
edited — which is row A3 of pull request #4's table, the case the change exists for.

## Results

| # | Criterion | Result |
|---|---|---|
| 1 | The first attempt is refused, and the reviewer returns at least one evidence-and-suggestion pair | **pass** |
| 2 | The findings reach the teacher on the beat (`beat.issues`), not the ledger note | **pass** |
| 3 | Pressing regenerate with **nothing edited** sends those findings to the creator | **pass** |
| 4 | The instruction to act on them is in the creator's prompt | **pass** |
| 5 | The second draft corrects the flagged detail | **pass** |
| 6 | The second draft does not reintroduce the same fault in different words | **pass** |
| 7 | The reviewer's second pass is **not** shown the first pass's findings | **pass** — `source` held only `dialogue` on every pass |
| 8 | Once a draft passes, the findings are dropped — a third attempt carries none | **pass** |
| 9 | The ledger note stays the fixed verdict sentence, with no child's words in it | **pass** |

### The decisive exchange

**First draft, refused.** 「……远处的山脚处有三间小房子，靠近河边的木屋是孩子所说的自己家。」

The reviewer's finding: the child said the riverside house is one *of* the three, and the
draft put all three at the distant mountain foot while treating the riverside cabin as
something else — 「这扭曲了孩子关于三间房子（含河边那间）的原始描述」. Its remedy asked the
draft to distinguish the foreground riverside cabin from the distant ones.

This is a good catch, and it is the reviewer's stated job: distorted child words.

**Second draft, nothing edited by the teacher, findings supplied.**
「……山脚下错落分布着三间房屋，其中靠近河岸的前景木屋就是孩子所说的自己家……」

Three houses at the mountain foot, **of which the foreground cabin near the river bank is
the child's own home**. That is the correction the remedy asked for, made on the first
retry, with no teacher edit. It passed review.

**Third draft.** `carried_findings` was empty and the creator was sent no issues, so the
findings did not survive the pass.

## What the run also found, and what was done

**The reviewer answered in English about a Chinese draft.** On the first run its finding
came back as *"Candidate states '红色屋顶' (red roof) for the cabin on the right side by the
river…"* with the remedy *"The roof color should be corrected to dark brown or black"*.
Since 3f71496 those words go on the screen a teacher is editing on, so a Chinese classroom
would have been shown an English sentence about a Chinese description. The review prompt
never named an output language; the creator's prompt always has.

Fixed in the same pass: `_review_draft` now asks for every evidence and suggestion in the
conversation's language, and the re-run returned Chinese findings throughout — including
the decisive exchange above. A parametrised test covers `zh` and `en` and was seen to fail
without the change.

**A detail supplied only by the child is accepted, and that is correct.** Two drafts said
three houses where the paper shows two, and the reviewer passed both. The creator's prompt
allows any detail "directly visible or supplied in the dialogue", and three houses was
supplied in the dialogue. This is the product preserving the child's account of their own
drawing, not a reviewer miss. Worth knowing before anyone reads it as one.

**One anomaly was the harness, not the product.** An early run reused a ledger file and
its request ids, so the harness resumed an already-completed stage and the creator was
never called on the second attempt. Give each live run its own ledger path and its own
request ids.

## Reproducing

The script is not checked in — it builds the two clients straight from the profile,
records every prompt, seeks a refusal, then presses regenerate twice. The pieces it needs:
`load_profile("stepfun")`, `build_client(resolve("vlm.creation", …))` and the same for
`vlm.director`, a `Conversation` with `language="zh"`, and a wrapper on each client that
keeps the prompt it was handed. Run it under `uv run --env-file .env`, or the StepFun key
is not loaded.

Cost: eleven creator calls and ten reviewer calls across four runs, at `step-3.7-flash`
prices ($0.19 / $1.14 per million).
