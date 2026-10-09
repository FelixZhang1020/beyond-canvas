# The studio voice, running on this Mac

This is the spike the model access layer plan ends on, and
its verdict decides whether the studio slot is served locally or stays hosted.

**Verdict: it runs, and the studio slot moves local.** Step3-VL-10B at Q4_K_M
serves vision on an M5 Pro at about 52 tokens a second, reads a child's drawing
accurately, and costs nothing. The full hero loop — screen, opening, reply —
passes the rubric with the studio voice local and only the grader hosted.

## What was needed

| Piece | What worked |
|---|---|
| Runtime | llama.cpp **built from master**. The Homebrew bottle, 0.3.0 build 10621, cannot load this model's vision projector. |
| Weights | `seanbailey518/Step3-VL-10B-GGUF`, file `Step3-VL-10B-Q4_K_M.gguf`, about 6 GB. |
| Projector | `JamePeng2023/Step3-VL-10B-GGUF`, file `mmproj-Step3-VL-10b-F16.gguf`, about 4 GB. **Not the projector from the same repository as the weights.** |

```bash
sh studio/localmodels.sh          # start both local models
sh studio/localmodels.sh status   # say what is answering
```

## Where these live, and why it is not where they were built

Added later. The build and the projector were sitting in an editor
session's scratchpad under `/private/tmp`, which macOS clears. Nothing warned
about it, and the failure it would have produced is the expensive kind: the
model stops starting and the error names a missing file rather than saying the
build is gone. Both now live in one place:

| Piece | Path |
|---|---|
| Build (binary and its nine dylibs, 19 MB) | `~/.local/share/beyond-canvas/bin/` |
| Projector (3.7 GB) | `~/.local/share/beyond-canvas/models/mmproj-step3vl.gguf` |
| Weights (4.7 GB) | left in the Hugging Face cache, which is re-downloadable |

**A copy alone would not have worked.** The binary finds its nine libraries
through an `@rpath` that was an absolute path into the scratchpad, so a copied
binary would have kept reading from the directory it was moved out of and broken
on the day that directory was cleared. The rpath is now `@executable_path`, which
resolves beside the binary wherever it sits, and the binary was re-signed
afterwards because editing a Mach-O invalidates its signature. Verified by
running the hero loop through the moved model and reading a drawing correctly.

## The projector is the whole difficulty

Four repositories publish a GGUF projector for this model and they do not agree
on what its tensors are called. llama.cpp master's `step3vl` loader wants
`mm.0`, `mm.1` and `mm.model.fc.weight`. Read over HTTP range requests, without
downloading a byte of weights:

| Repository | Projector tensors | Loads |
|---|---|---|
| `seanbailey518` | `mm.0.weight` only | no — "unable to find tensor mm.1.weight" |
| `kraven1109` | `mm.0`, `mm.1`, `mm.2.weight` | no — the third is misnamed |
| `Vastined` | `mm.0`, `mm.1`, `mm.model.fc.weight` | yes |
| `JamePeng2023` | `mm.0`, `mm.1`, `mm.model.fc.weight` | yes |

All four declare `clip.projector_type = step3vl`, so the metadata is no guide.
The failure is silent in the useful sense: the server refuses to start rather
than serving a model that cannot see, which is the right way round.

## What it does

Asked to name the colours and shapes in the test drawing, with 3000 tokens:

> The drawing contains the colors yellow, purple, black, and white. The shapes
> include a yellow sun-shaped polygon, two stick figures with circular heads,
> and a purple creature made of an oval body, a circular head, and rectangular
> legs.

Correct, and specific enough for the rubric's rule 3. 1409 completion tokens in
28.6 seconds, 51.6 tokens a second, prompt processed at 142 tokens a second.

**It thinks before it writes, and llama-server puts that thinking in its own
field.** At 200 tokens it produced 200 tokens of reasoning and an empty answer,
which is the same failure Step 3.7 Flash shows on OpenRouter for the same
reason. The local client now says so — "spent its whole budget on hidden
reasoning; raise max_tokens" — rather than reporting a blank.

## The hero loop, studio voice local

`studio/profiles/local.yaml`, colour entrance, English:

| Stage | Gate | Seconds |
|---|---|---:|
| screen | pass | 9.1 |
| opening | pass, 100% clean | 115.2 |
| reply | pass, 100% clean | 171.3 |

> I see you made a yellow sun with pointy edges. There are two stick figures
> holding a line between them. The purple shape has an oval body, a round head,
> and four legs. What is the purple creature doing near the stick figures right
> now?

**The remaining latency is the hosted grader, not the local model.** The model
writes its part in about 29 seconds; each beat then waits on two judge calls to
OpenRouter, and those are the same long-tailed calls measured in the first-loop
timings note. Moving the grader local — which the Spark profile does — is what
would make this fast, not a faster studio model.

## One defect this run found

The reply came back *"So the purple creature is looking for your mum because she
got lost"* when the child had said **his** mum. The prompt rule added earlier the
same day told the model to turn the child's first person into second person, and
it over-applied that to a character. Both reply prompts now say it explicitly:
what the child says about themselves changes voice, what they say about someone
in the picture stays exactly as they said it. No rule caught this — rule 13 saw
the echo, rule 14 saw no invention — and a rule for it would be a pronoun
heuristic, which is worse than the prompt being right.

## What this does not settle

The Spark runs different hardware, a different quantisation may fit, and the
director model is not this model. Nothing here predicts a Spark number. What it
does settle is the plan's open question: the studio slot can be served locally,
so Phase 0 does not have to send every child's drawing to a hosted API.
