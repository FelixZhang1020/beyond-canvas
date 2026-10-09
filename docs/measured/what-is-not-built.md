# What is not built, and what would unblock each piece

Written early, and revised after the studio page, the local models, the audio
path and the animation skill landed. This exists so that "not built"
is a list with reasons rather than a feeling, and so the next person does not
rediscover the same walls.

**Revised again, later the same day.** The keys arrived and every
media slot has now been run on a real drawing, so the wall below moved from
"nobody has a key" to "the model does the wrong thing." The results are in
`media-models-on-real-drawings.md` and `sketch-to-3d.md`.

## No longer blocked on a key — blocked on the output

`STEPFUN_API_KEY` and `REPLICATE_API_KEY` are both set and every slot answers.
What blocks these three skills now is quality, which is a harder wall:

| Skill | Slot, and what it does now | What blocks it |
|---|---|---|
| `sketch-to-3d` | `mesh.fast`, InstantMesh — 16 s, a valid mesh | Reconstructs only forms carrying a tonal shadow; a pencil cube whose faces match the paper is lost. Needs a masking stage in front, not a new model |
| `painting-to-scene` | `depth` — still not wired to anything | Nothing calls the slot. Depth Anything is 0.1 GB and Apple publish a CoreML build, so this is work, not risk |
| `drawings-to-storybook` | `image.edit` Step1X-Edit, `tts.studio` StepAudio 2.5 | The voice works. The picture slot has damaged the child's drawing on every preservation test it has been given |

`painting-to-scene` has a local path that needs no key — Depth Anything runs on
the Mac — so it is partly reachable if the model is downloaded. Neither it nor
`sketch-to-3d` is worth starting before their drop gates, later in the build plan.

The storybook is the exception worth weighing: its narration wants a cloned
voice, but a first version could use the system voice the page already speaks
with, and the keepsake page it would produce is already written
(`skills/art-feedback/scripts/story.py`).

## Blocked on hardware

- **The container recipe.** Phase 1 only.
- **Every Spark number.** Latency, throughput, real memory behaviour, mode
  switching under load. `studio/dayzero.py` asks all of it and already runs; what
  it cannot know is how much of the gap between the 90 GB ceiling and 108 GB
  usable a real load consumes. That is the day-zero measurement that matters
  most.

## Blocked on the thing the machine cannot decide

- **The fine-tune.** Not blocked on the Spark. Blocked on real drawings and on
  ever having measured whether a child says more after the reply. The task itself
  is section 8 of the design record,
  `docs/specs/art-studio-skill-pack-design.md`.
- **Any honest evaluation.** Six generated fixtures test the plumbing. They do
  not tell anyone whether this works on a child's actual drawing, and no number
  in this repository should be read as if they did.

## Deliberately not built

- **`safety.image` as a real classifier.** ShieldGemma 2 has a tunable score;
  the vision model standing in for it does not, so the threshold in the skill
  card cannot actually be tuned. Phase 1 fixes this.
- **`studio-harness` as a skill folder.** The harness exists as `studio/harness.py`
  and is called directly. Wrapping it in a skill package would add another
  permanently-resident description for something no agent needs to trigger.
- **`evalkit/convert.py`.** The plan wants it to translate between "NVIDIA's
  shape" and "the agentskills.io shape". There is one shape. It would convert a
  format to itself.
- **`skill.oms.sig` signing.** The package validator reports its absence on all
  three skills. It is a publishing step and a governance decision, not code.

## Known stale, and cheap to fix

- **`skills/art-feedback/BENCHMARK.md` was measured against a rubric that no
  longer exists.** The 92% against 55% figure predates the sketch and colour
  fork, the rescoping of rules 3 and 4 for replies, and rule 13's second half.
  Its prose also says "the ten rules" when there are fourteen. A published
  number that nobody can reproduce is worse than no number.
- **Every eval case is in English**, in a product whose first language is
  Chinese and whose judges are Chinese. Nothing has ever been graded in Chinese
  end to end.

## Built since this file was first written

The studio page served by its own harness on one port; the four beats of the
hero scenario on screen, including the child speaking and the three rungs; the
studio voice running locally on the Mac; local transcription; the animation
skill and its player; the Spark profile and the day-zero kit.
