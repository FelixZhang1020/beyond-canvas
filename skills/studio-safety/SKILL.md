---
name: studio-safety
description: Screens an image before a children's art studio acts on it, deciding whether it is a child's drawing, a frightening drawing that should still be answered warmly, something that is not a drawing at all, or a blank page, and reporting any writing found on the page so a name is never read back. Use before any other studio skill sees an image. When the request is to make something out of the image — a solid form, a moving clip, a storybook — and the image is blank, a photograph or not a drawing, it stops here; a request for feedback on that same image goes to art-feedback instead, which declines it warmly.
allowed-tools: studio-safety/nemotron, studio-safety/nemotron_server, studio-safety/safety
license: Apache-2.0
compatibility: Requires a vision-capable model on the vlm.director slot and Python 3.13 with uv. Optional second reader, NVIDIA Nemotron 3.5 Content Safety on the safety.reader slot, needs a GPU with about 11 GB free, PyTorch and Transformers 4.57.
metadata:
  author: beyond-canvas
  version: "0.1"
---

# Studio safety

The first thing that runs, and the only skill that can stop a request. A blocked image
never reaches the harness, so no other skill can receive one.

## Capabilities this skill uses

- Network: the model endpoint named by the `vlm.director` slot in the active profile, and, when
  a second reader is named, the local address of the `safety.reader` slot.
- Files: reads the image passed on the command line. Writes nothing.
- Shell: none beyond running its own script.

## How to run it

```bash
uv run python skills/studio-safety/scripts/safety.py DRAWING
uv run python skills/studio-safety/scripts/safety.py DRAWING --profile spark --second-slot safety.reader
python skills/studio-safety/scripts/nemotron_server.py MODEL_DIR     # where the second reader's weights are
```

## Four verdicts, and why there are four

| Verdict | Meaning | What happens |
|---|---|---|
| `allow` | A child's drawing with something on the page | Proceed |
| `soften` | A child's drawing whose subject is dark or frightening | **Proceed.** The studio describes it warmly and judges it not at all |
| `block` | Not a child's drawing, or genuinely unsafe | Stop |
| `empty` | A blank page | Stop, and ask kindly for the drawing |

`soften` is the one worth arguing about, so here is the argument. A frightening drawing
is not a problem to solve. Children draw monsters, and blocking one tells a child their
subject was unacceptable — the opposite of what this product is for. The spec is explicit:
no "how scary", no asking whether something is wrong, no suggesting they draw something
happier. Any of those and the thing the child was about to say never gets said.

`empty` is separate from `block` for the same reason. Nothing is wrong with the child;
there is simply nothing to talk about yet.

## A second reader: NVIDIA's safety model

Nemotron 3.5 Content Safety (4B, open weights) is trained for nothing but this. When the
profile names it, it looks first, at both points the studio screens, and
`scripts/nemotron.py` holds what it is allowed to decide:

| Point | It flags | What happens |
|---|---|---|
| The door: a child's drawing | Sexual content, twice in a row | Stop. The picture is not sent on to any other model |
| The door | Anything else (violence, a weapon, something sad) | **Proceed** as `soften`, with the category as a code for the teacher |
| The way out: a machine-made picture | Anything | Refuse that picture; it costs one retry |
| Either | It cannot be reached, or its answer cannot be read | It stops nothing. The four verdicts decide, and the record says `second-look:unavailable` |

Only codes are kept (`soften second-look:violence`). The model's own words about a child's
drawing are dropped where its answer is read and go no further. A photograph, a blank page
and a name on the page stay the four verdicts' business.

It runs on NVIDIA's stock rules. A policy of our own was written and measured
(`references/childrens-studio-policy.md`) and is kept as the fallback: on every generated
test drawing the two agree, and the stock rules answer in 0.4 s against about 5.
`scripts/nemotron_server.py` holds the model in memory on the machine with the weights and
answers one picture at a time on 127.0.0.1; it logs nothing about a picture.

## Writing on the page

Any text visible in the image comes back in `text_found`. It never blocks anything.

Two layers keep it out of what the child hears. The feedback prompt forbids repeating a
name, and `redact()` removes the found strings from the text afterwards. The second exists
because a rule the model merely agreed to is not a guarantee. Longer strings are removed
first, so redacting "Sunshine Primary" does not leave "Primary" behind.

## Gotchas

- **The filter fails loudly, never open.** An answer it cannot read raises `ModelRefused`
  rather than becoming an `allow`. A safety filter that degrades to "yes" is worse than
  one that stops.
- A model inventing a fifth verdict is refused for the same reason.
- The four verdicts come from a vision-language model, which has no score to threshold on.
  ShieldGemma 2 was once planned in its place and could never have served: it classifies
  harm and cannot tell a photograph or a blank page from a drawing, nor read writing.
- **The second reader is measured only for not turning a child away.** Seven generated
  drawings, the darkest a sword fight, a hunt and a hurt friend, all came in. Whether it
  catches a truly harmful picture is unmeasured: no such test set is held, or should be.
- **A 4B safety model matches words.** Our first policy listed "gore" and "injury" among
  what is not allowed, and it then flagged the three dark drawings the stock rules passed.
  If the policy is ever edited, keep what children draw out of the not-allowed list; a
  test holds that.
- The second reader is a different protocol from a chat model: build it with
  `build_safety_reader`, never `build_client`.
