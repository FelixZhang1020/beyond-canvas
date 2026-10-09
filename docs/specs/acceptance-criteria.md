# Acceptance criteria

Status: proposed for the operator's confirmation. Companion to
`art-studio-skill-pack-design.md` (what the product is) and
`studio-page-contract.md` (how the page and the harness talk).

## How to read this

Eighty-one criteria. Each is **binary and checkable by someone who was not in
the room**, and says what must be true rather than how to get there. Each names
what checks it;
where nothing checks it yet, it says **not checked**; where the product does
not do it yet, **not met** — and that set, collected
in section M, is the honest list of what is left.

Two phases, because the hardware arrives only partway through. **Phase 0** is this Mac,
local models plus a hosted grader. **Phase 1** is the Spark. A Phase 1 criterion
cannot fail before the hardware arrives; it is written now so it is not invented under time pressure
later.

Numbers marked **(proposed)** are mine, neither measured nor settled. The
operator confirms or replaces them.

---

## A. The hero loop — layer one, both entrances

**A1 — The teacher picks the entrance by hand, every class.** No default, no
memory of the last one, no detection from the image.
*Checked by:* `tests/page/state.test.mjs`, `tests/server/test_serve.py`, and
`--entrance` being required by `skills/art-feedback/scripts/feedback.py`.

**A2 — Four beats, in order: 我看到 → 我好奇 → 你来说 → 我听见了.** The studio
observes, asks, listens, and answers what it heard.
*Checked by:* the beat-scoped rules and `tests/evalkit/test_rubric_loop.py`.

**A3 — On 彩画 nothing is corrected. On 素描, exactly one thing to try.**
*Checked by:* rules 6 and 7, scoped to the colour entrance.

**A4 — The question enters the world (彩画) or the process (素描)**, never the
artifact: never "why did you use blue there".
*Checked by:* rule 12, in its two forms.

**A5 — One drawing produces two to four sentences and exactly one question.**
*Checked by:* rules 9 and 10.

**A6 — The reply uses the child's own words**, not a paraphrase of them.
*Checked by:* rule 13's overlap check.

**A7 — The machine never tells the story for the child.**
*Checked by:* rule 14.

**A8 — When the child says nothing, the studio climbs three rungs and stops.**
It does not keep asking.
*Checked by:* `tests/evalkit/test_rubric_loop.py`, and the rung 2 and rung 3 prompts.

---

## B. The fourteen rules — the grader

**B1 — Every applicable rule passes, for every fixture, on both entrances.**
Seven fixtures times two entrances, all green, before any claim that this layer
works.
*Checked by:* the eval sweep, recorded under `docs/measured/`.

**B2 — Scope is part of the rule.** 6 and 7 are colour-only; 12 has a world form
and a process form; 2, 9 and 12 grade an opening, not a reply.
*Checked by:* `tests/evalkit/test_rubric_entrances.py`.

**B3 — A failure names the sentence that failed it**, so a person can disagree
with the grader.
*Checked by:* the rubric report's shape.

**B4 — A silence is never scored.** An empty completion is retried, then dropped
from the sample; it is not a zero.
*Checked by:* the eval runner's retry-then-drop path.

**B5 — The writer is not its own judge.** `vlm.studio` writes, `vlm.director`
grades, never the same slot.
*Checked by:* the profile files. **No test asserts it — not checked.**

**B6 — Every rule is measured in Chinese before the demo.** The interface, the
prompts and the customer are Chinese; every number so far came from English.
*Checked by:* **nothing. Not met.**

---

## C. Safety

**C1 — Every drawing is screened before any feedback is written**, and the
verdict is remembered for that drawing for the session.
*Checked by:* `tests/classroom/test_classroom.py` and the contract's safety stage.

**C2 — A blank page asks for a photo** rather than inventing a response.
**C3 — A photograph of a real object, or of an adult, is declined warmly.**
**C4 — A violent or unsafe image is blocked, with a reason a teacher can read.**
*Checked by:* `tests/skills/test_safety_refusals.py`, `tests/evalkit/test_red_lines.py`.

**C5 — A name or a school written on the drawing is never echoed downstream.**
*Checked by:* the PII flag path. **Coverage unconfirmed — not checked.**

**C6 — A refused drawing stays refused** for the rest of the session.
*Checked by:* `tests/server/test_serve.py`.

**C7 — A refusal is attributed to the safety step**, never shown as a model
outage or a feedback failure.
*Checked by:* the stopped/done event pair.

---

## D. Privacy and the one-off session

**D1 — Nothing about an individual child persists between visits.** No identity,
no history, no growth tracking.
**D2 — Drawings live in memory only**, and are dropped on "End class", on
`DELETE /api/session/{id}`, and when the tab closes.
**D3 — The ledger holds hashes and timings, never a drawing and never a child's
words.**
**D4 — The page sends nothing anywhere except its own origin's routes.**
*Checked by:* `tests/server/test_serve.py`, `tests/conversation/test_session.py`, the page contract.

**D5 — The interface never claims more privacy than the running profile
delivers.** On the local profile the drawing still reaches the hosted grader, for
screening and for rules 3 and 4; only the Spark profile is "nothing leaves the
box". What the page says must match the profile it is running.
*Checked by:* **nothing, and the wording has never been reviewed against this.
Not checked.**

---

## E. The teacher's page

**E1 — The opening asks one question** — which kind of class — and answering it
starts the class.
**E2 — Chinese by default**, one control switches language, the choice is
remembered; the entrance never is.
*Checked by:* `tests/page/state.test.mjs`, `tests/server/test_serve.py`.

**E3 — Every stage transition the harness sends is rendered in the order
received**, so a judge watching the screen sees what the ledger recorded.
**E4 — A run that stops sends its stopped event and then `done`**, so a kind
refusal is never displayed as an outage.
*Checked by:* `tests/server/test_serve.py` and the contract.

**E5 — With no harness the page falls back to its mock and says so on screen.**
**E6 — Only skills the harness can run are offered** — never a button that
answers "that part is not open yet".
*Checked by:* the health route. **The page-side behaviour has no test — not
checked.**

**E7 — It works on the device the class uses.** Tablet portrait (768×1024) and
desktop; child-facing targets at least 76 px, nothing important under 44 px.
*Checked by:* inspection at 768 and desktop. **Never opened on a real
tablet — not checked.**

**E8 — Where the browser forbids the camera, the page says so and offers the
photo library.** A browser allows the camera only on a secure page, so any
address other than this machine's own loses it.
*Checked by:* the `camera.none` path exists. **Never exercised — not checked.**

**E9 — The status board is reachable from inside the studio**, with no second
address to remember.
*Checked by:* `tests/server/test_serve.py`.

**E10 — Nothing is fetched from the network**: no fonts, scripts, images or
voices. One self-contained file.
*Checked by:* the build script's structure check. **The no-network claim itself
has no test — not checked.**

---

## F. The harness and model access

**F1 — A skill names a slot, never a vendor.** `vlm.studio`, `image.edit`; never
an SDK import in a skill.
**F2 — Changing profile changes no skill code.**
*Checked by:* `tests/core/test_slots.py`, `tests/providers/test_llamacpp.py`,
`tests/providers/test_openrouter.py`.

**F3 — Every port sits in 7000–7700 and ends in a zero**, no two slots share
one, and the page never sits on a model's port.
*Checked by:* `tests/server/test_ports.py` and `tests/server/test_document_ports.py`. Temporary
previews follow the same rule. These static
checks do not prove that all existing processes or arbitrary scripts comply. Test-only
OS-assigned ephemeral ports use the explicit zero exception in `studio/server/ports.py`.

**F4 — A busy port is a sentence naming the remedy, not a traceback.**
*Checked by:* `tests/server/test_ports.py`, `tests/ops/test_modelboard.py`.

**F5 — Every failure a teacher can see says what happened and what to do next.**
No stack traces on screen, no apologies, no vagueness.
*Checked by:* the error paths, partially. **No rule enforces it — not checked.**

**F6 — A killed run resumes from the ledger and reproduces the same stage.**
*Checked by:* `tests/core/test_harness.py`.

**F7 — Memory never rises above 90 GB.** Phase 1.
*Checked by:* `studio/ops/dayzero.py`. **Unrunnable until the Spark arrives.**

---

## G. Phase 1 — the Spark, once it arrives

**G1 — The hero loop completes with no hosted call at all.** This is what the
privacy claim rests on; nothing else substitutes for it.
**G2 — Day zero measures what it promises**: first-token and full-reply latency,
throughput, resident memory, and the cost of switching modes.
**G3 — The rotating slot holds one model at a time**, unloading before loading.
**G4 — The container recipe builds and runs on ARM.**
*Checked by:* `studio/ops/dayzero.py` and the Phase 1 build. **None runnable yet.**

---

## H. Layers two and three — conditional

Each applies only when its key or model is present. Absent, H5 governs.

**H1 — painting-to-animation:** the subject is preserved, no new text appears,
length and resolution are as asked; a figure takes the rig path, otherwise the
video path.
**H2 — sketch-to-3d:** the GLB opens in trimesh and the silhouette matches the
sketch **(proposed: IoU ≥ 0.75)**.
**H3 — painting-to-scene:** the depth map is valid and the main subject has no
hole.
**H4 — drawings-to-storybook:** every drawing is used exactly once, not one word
of the child's language is substituted, and the audio matches the text.
**H5 — A layer with no key is hidden, not offered and broken.**
*Checked by:* H5 by the health route. **H1–H4 not checked: no keys, no runs.**

---

## I. Packaging and submission

**I1 — Every SKILL.md stays under 500 lines**, with detail in `references/`.
**I2 — Frontmatter uses only the closed set** (`name`, `description`, `license`,
`compatibility`, `metadata`, `allowed-tools`), and `name` matches its directory.
*Checked by:* `tests/skills/test_skill_docs.py`.

**I3 — `skills-ref validate` passes on every shipped skill.**
*Checked by:* **manual, last run unrecorded — not checked.**

**I4 — The pack triggers the right skill on a plain request**, loading only
descriptions until then.
*Checked by:* **nothing — not checked.**

**I5 — Signing (`skill.oms.sig`) is a governance decision**, currently absent and
reported by the validator. Not a defect until the operator decides it is one.

---

## J. What counts as evidence

**J1 — No number appears in prose without the command that produced it.**
**J2 — One sweep is not a measurement.** Any change to a prompt, a rule or a
lexicon re-runs every fixture on both entrances, and the replies are read, not
only the pass rate.
**J3 — Generated fixtures test the plumbing; only real drawings test the
product.** No claim about how well this works may rest on the seven fixtures
alone.
**J4 — A silence is dropped, never scored.**
**J5 — The demo path has been run end to end, in the page, against the models
that will be on stage, on the day.**
*Checked by:* J1–J4 by convention and review. **J5 has never been done — not
checked.**

---

## K. The demonstration — 20 of 100 points, and no owner

**K1 — The first ten seconds show a real crayon drawing entering the system**,
not output coming out of it: a picture-book generator already placed in an
earlier edition.
**K2 — One drawing completes inside the time a judge will wait — (proposed:
60 s).** Measured on this Mac with the local model: 35 s.
**K3 — There is a fallback if a model is down**: a recorded run or a cached
result, decided in advance rather than improvised.
**K4 — Who presents, for how long, live or recorded** — undecided.
**K5 — If teammates are assigned, the division of labour is written down**, because
collaboration is scored.
*Checked by:* **nothing. K4 and K5 are decisions, not code.**

---

## V. The voice — hearing the child, and speaking back

Added after the operator asked how the voice gets tested and the
answer turned out to be "it mostly doesn't". The child's own words and own voice
are what layer one exists to produce, so these belong beside the rules, not
under them.

**V1 — A Chinese recording comes back in simplified characters.** The failure
this guards is silent: a correct sentence in the wrong script reads correctly to
the teacher, reaches the skill correctly, and makes rule 13 match nothing.
*Checked by:* `tests/live/test_live_voice.py`, with audio made on the spot by
the system voice.

**V2 — The initial prompt is what keeps the script right**, and cannot be
dropped as decoration. Measured on the same audio: 24 of 26 character
pairs survive with it, 14 without.
*Checked by:* `tests/live/test_live_voice.py`.

**V3 — Whisper's own annotations never reach a skill.** A reply built on
"[BLANK_AUDIO]" would answer a child who said nothing.
*Checked by:* `tests/voice/test_transcribe.py`.

**V4 — A silent room is "nothing heard", never "something said".**
*Checked by:* `tests/voice/test_transcribe.py`.

**V5 — Listening is not the slow part.** A child is standing there. Measured:
0.2 s for 7 s of Chinese, 0.6 s for English.
*Checked by:* `tests/live/test_live_voice.py`.

**V6 — What Splat says aloud is never a novelty voice, always follows the
studio's language, and never talks over its own previous line.**
*Checked by:* `tests/page/voice.test.mjs`.

**V7 — The cloned narration says only the child's own words, its voice print is
destroyed at the end of class, and it needs its own guardian consent** — a
different question from consenting to a recording.
*Checked by:* **nothing; layer three is not built.** Two of the three are
deterministic the day it exists: word-level containment against the transcript,
and the absence of the voice print after the session ends. The third is a
product gate, not a test.

**The limit of all of the above.** The audio is synthetic: an adult system voice
in a silent room. It proves the pipeline and the script; it does not prove a
five-year-old in a room with twenty other children. Only real recordings prove
that, and there is no consent to hold any.

---

## U. The page against the document

Added by reading every promise the scenario document makes about
what a teacher touches and checking it against the built page. These seven are
**not met**: not "unchecked", but known to be absent or contradicted. They are
the difference between what the document says the studio does and what the
studio does.

**U1 — The finished work can leave the machine.** 会动的画、绘本、视频文件 are
exported and go home with the child; only the raw drawings and recordings are
cleared. The one download that exists so far is the ledger's JSON.
**Not met.**

**U2 — The book is turned by hand, by the child.** 自动播放就变成了一段视频.
The page ships a play button that does exactly that.
**Not met**, and it contradicts the document rather than merely lagging it.

**U3 — The teacher chooses at most eight drawings for the book**, with a story
style and scene presets. The run sends every drawing in the session, with no
selection, no cap and no options.
**Not met.**

**U4 — The last page is blank until the child answers "然后呢？"** — the ending
belongs to the child, not to the machine.
**Not met.**

**U5 — A recording the teacher made earlier can be brought in.** 3.2 names two
routes to the child's voice; the file input accepts `image/*` only, so only the
second exists. Frame extraction at the moment the child says 「这里」 has no
interface at all.
**Not met.**

**U6 — The teacher can stop a run at any moment.** 老师是闸门，随时可以叫停.
`abort` exists in the code and is reachable only by moving to the next child or
ending the class.
**Not met.**

**U7 — Layer two is named the way the document names it.** 抽象挂画 has no
control at all; 形体立起来 is labelled "Make a 3D toy", which is a toy rather
than the teaching aid the document describes, and its 换光、换材质 and
side-by-side comparison have no interface; "Walk into it" is offered on screen
and appears nowhere in the document.
**Not met.**

**One tension rather than a gap.** 4.1 promises the child sees the drawing move
within two seconds; the page's run loop is built around a comment reading "the
model takes a minute or more", with a counting timer so the wait does not look
broken. Both can be true — the choreography is instant, the model that writes it
is not — but the interface does not distinguish them, and two seconds is the
number on the slide.

---

## L. Out of scope — never to be treated as failures

Removed by the one-off session decision: per-child identity, stored history,
growth tracking, and any guardian consent flow for storage.

Removed by the art-centre decision: a consumer mobile app, a parent-facing
account, and printing or fulfilment of keepsakes.

Out of scope regardless: real-time voice conversation, cloud multi-tenant
hosting, formal regulatory sign-off, and a LoRA on Step 3.7 Flash itself.

---

## M. What is not checked yet

The same list, collected, in the order I would take it:

1. **B6 — Chinese is entirely unmeasured** by the fourteen rules, and it is now
   the default language. (Chinese *transcription* is measured — see V1.)
2. **J5 — the loop has never been run in the page against the local models.**
3. **D5 — the privacy wording has never been checked against the running
   profile.**
4. **K4, K5 — the demonstration has no owner and no plan.**
5. **C5 — name and school redaction is unconfirmed.**
6. **E6, E7, E8, E10 — page behaviours with no test**, and no run on a real
   tablet.
7. **B5, F5 — the writer/judge split and the plain-language failure rule rest on
   review alone.**
8. **I3, I4 — packaging validation is manual and unrecorded.**
9. **G1–G4, F7 — everything Spark**, unrunnable until the hardware arrives.
10. **H1–H4 — the media layers**, unrunnable without keys.
11. **V7 — the cloned voice**, unbuilt; two of its three constraints are
    testable the day it exists.
12. **U1–U7 — seven things the page does not do**, or does against what the
    document says. U1 and U2 first: the export is a promise made in writing,
    and the play button contradicts the document's own argument.
