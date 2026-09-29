# Agentic 3D Showpiece Skills — Design

Status: decided with the operator, ready for a plan. Companion
evidence: the Foguang East Hall physics check under `output/foguang-east-hall/physics-check/`
(gitignored, this Mac only) and its published report.

## 1. What the operator asked for, and decided

The hackathon entry gets a new showcase module for **Agentic 3D on the DGX Spark**, aimed
at the three camp sessions: StepFun models driving an agent loop, Agent Skills built for the
Spark, and vision that runs on the box. The operator chose, in this order:

| Decision | Answer |
|---|---|
| Which result | **Both**: the temple as the hard demo, and the studio's child's toy through the same skills |
| What the temple agent does | Four showpieces, "a bit fancy": take the hall apart to show how pieces join (mortise and tenon), a moving-camera tour inside and out, gravity and load-bearing, and construction from empty platform to finished hall |
| What matters more than the videos | **Agent Skill capability**: any agent drives the skills from a plain-words request, the skills are reusable, and a request never seen before must work |
| How many skills | **Several**, not one, each in NVIDIA's format with its own evals |
| What the judges watch | **A live dashboard** of the agent working: its thinking, the skill it is running, the pictures it renders, whether its eyes approve them, the finished shows |
| Order of work | Temple skills, then the dashboard, then the Spark port, then the child's toy, so the demo is safe if the last item slips |
| Stage format | Not fixed. Every run is logged and replayable, so the roadshow can replay a run or start a fresh request live |

Not in scope: fixing the temple's structure live on stage (done already, v25), changing its
architecture, or touching the five existing skills during the window.

## 2. The six skills

All live under `skills/<name>/` in the same shape as the five shipped ones: `SKILL.md`,
`skill-card.md`, `evals/evals.json`, `BENCHMARK.md`, `scripts/`, `references/`,
`skill.oms.sig`. Their scripts run inside headless Blender (`blender -b <model> --python
scripts/<tool>.py -- <args>`), read and write JSON, PNG and MP4 in a run folder, and never
modify the source model: every change is made on a copy or saved as a derived file. The one
exception is `shot-judge`, a plain Python call to the vision slot with no Blender involved.

| Skill | What it does | Tools (scripts) | Evidence it keeps |
|---|---|---|---|
| `model-anatomy` | Reads any building model: the pieces, their groups by role (platform, columns, walls, brackets, beams and purlins, rafters, covering), what rests on what, named places a camera can look at | `inventory`, `bearing` (from the physics check's `supports.py` and `statics.py` order) | `anatomy.json`: pieces, roles, bearing order, landmarks |
| `joint-reveal` | Takes a chosen bracket set or joint apart, piece by piece, and shows how the parts fit. Three true mortise-and-tenon joints are modelled for the close-ups (the source model has none, by its own notes): column top into the big block, the crossing bracket arms, a beam end into a column | `joints` (adds the three joints to a derived model), `explode` (animated pull-apart of a named assembly), `closeup` | the derived model, an explode video, key shots |
| `structure-tour` | A camera tour inside and out along named landmarks: an outside orbit, in through the central door, up under the ceiling, and an overhead view with the roof peeled off | `path` (camera through landmarks), `peel` (hide layers), `render` | a tour video, key shots |
| `load-path` | Gravity and load-bearing: weight flowing down in colour from tiles to columns, then the settle test where every piece is let go | `flow` (colour by carried load, revealed top to bottom), `settle` (the Bullet simulation) | a load video, the per-piece numbers |
| `raise-the-hall` | Construction from platform to ridge in the true bearing order: pieces arrive in stages, each stage only after what carries it | `stages` (groups the bearing order into build stages), `raise` (animated arrival), `render` | a construction video, the stage list |
| `shot-judge` | The agent's eyes. Given a rendered shot and what it was meant to show, says whether the subject is visible, centred and readable, and what to change if not. Used by every other skill | `judge` (one vision call with a fixed prompt) | a verdict per shot in the ledger |

Each skill's `SKILL.md` describes when to use it, its tools and their arguments, and what a
good result looks like, in the agentskills.io shape the packaging check enforces. The body
is what an agent loads when the skill triggers; the description is what it sees in the index.

## 3. How an agent drives them

**On the Mac, while building:** the coding agent used for development is the agent. It loads
the six folders from `skills/` the way it loads any skill, and calls the tools through
the shell. This is the development loop and the first proof that the skills compose.

**On the Spark, for the demo:** the Step model is the agent. `studio/showpiece/driver.py`
runs the loop against the `vlm.director` slot (Step 3.7 Flash on llama-server, port 7110):

1. The request in plain words, plus the six skill descriptions, goes to the model.
2. The model answers with one action as JSON: `{"skill": ..., "tool": ..., "args": {...}}`,
   or a final answer. A JSON action works with any chat model, with or without native
   tool calling; native tool calling is not required.
3. The driver runs the tool, returns its JSON result and, for a render, the picture itself,
   so the model looks at what it made.
4. Every step is a ledger line (`studio.core.ledger`, the existing append-only record) with the
   action, the result path, tokens and time. The loop stops at a cap of 40 actions or on
   the final answer.

A replay reads the ledger back and shows the same run on the dashboard without the model.

**The judge is separate from the actor.** `shot-judge` is its own call with its own prompt,
so the check does not share the actor's reasoning. On the Spark it is the same loaded
model with a different prompt; on the Mac it is the studio's `vlm.studio` slot, a Step
model through the API, so the sponsor's model is in the loop on both machines.

## 4. The dashboard

`studio/showpiece/` is a standalone exhibit like `studio/showcase_3d/`: a static page and
a small server in one process, `python -m studio.showpiece --port 7090`, no bundler, no
network dependency. It starts runs, streams their progress and serves their pictures. The
main studio server is not edited (it is over the size limit and split is pending); the
portfolio home links to the exhibit through a new page fragment.

What the page shows, live from the ledger stream:

- the request at the top, and which agent is driving (the development agent or Step 3.7 Flash);
- the loop as a moving timeline of think, act, look, one card per skill call with its
  progress and elapsed time;
- render thumbnails appearing as they are made, each stamped with the judge's verdict;
- a memory and load gauge for the machine (the Spark's unified memory, read from
  `nvidia-smi` and `free`; on the Mac, the process's own numbers);
- the finished videos, playable, and the ledger as a scrolling list;
- a replay control that plays a saved run at its own pace.

Look: dark, animated, Chinese and English switchable, the same tokens as the studio page.

Routes, all under one origin: `GET /` the page; `POST /api/runs` starts a run from a request
text and a model path; `GET /api/runs` lists runs; `GET /api/runs/<id>/events` server-sent
events, one per ledger line, then `done`; `GET /api/runs/<id>/files/<path>` a shot or video.
Runs live in `.studio/showpiece/runs/<id>/` (gitignored, stays on the machine).

## 5. Models and files

- The temple: `foguang-east-hall-v25.blend` (45 MB, 6,264 pieces). It stays under
  `output/` on this Mac and is copied to the hosted Spark only with the operator's
  permission, which was requested. The derived model with the three joints is
  written beside it.
- The child's toy: the sketch entrance's mesh, converted to a one-collection `.blend` by a
  small script, then given the same four shows in short form.
- Pictures: EEVEE at 1280 × 720 for shots the agent looks at, 1920 × 1080 for the final
  videos, assembled with ffmpeg.

## 6. The Spark

- Blender: no official ARM build exists. The community build `CoconutMacaroon/blender-arm64`
  v14 is Blender 5.2.0 for Ubuntu 24.04 aarch64, made for the DGX Spark and other GB10
  machines, with CUDA and OptiX; Vulkan may not work in that build. The Mac runs 5.2.1, so
  the scripts move without change. Headless EEVEE needs an off-screen GPU context; if the
  box refuses one, the fallback is Cycles with OptiX at low samples.
- Memory: the director quantisation is a day-zero measurement (the size ladder is in
  `docs/measured/model-sizes-measured.md`); Blender needs a few GB beside it. The
  demo runs in director mode, with the studio model unloaded, as `spark.yaml` already plans.
- ffmpeg from apt. The dashboard is viewed from a laptop through the SSH port mapping.

## 7. Evals and benchmark

Each skill's `evals.json` holds plain-words requests with the expected skill and tool, a
ground truth in words, and expected behaviours the judge and a person can check. The
temple's four showpieces are the benchmark cases, plus at least one request the skills were
not written for ("show only the roof from below"), because that is the test of a skill
rather than a script.

`BENCHMARK.md` compares two runs of the same requests: the model with the skills loaded,
and the same model given only the raw tool list and no skill text. It reports completion,
number of actions, time, and the judge's pass rate per shot, the way the feedback skill's
benchmark reports its rules. A new runner, `evalkit/showpiece.py`, produces it; the existing
runner is rubric-specific and stays as it is.

## 8. Risks and what is not built

- The judge can approve a wrong shot. Mitigation: a person watches the benchmark run once
  and the dashboard shows every verdict beside its picture, so a bad verdict is visible.
- The Step model may loop on a hard request. Mitigation: the 40-action cap, and the driver
  returns the judge's "what to change" text so each retry has a direction.
- The ARM Blender build may not render headless. Mitigation: the Cycles fallback above, and
  every video can be produced on the Mac and replayed on the Spark while the agent loop
  itself still runs there.
- Not built: a general 3D generator, any change to the temple's architecture, a Chinese
  narration voice (subtitles only in this window), the roadshow slides.

## 9. Verification

- Packaging: `tests/skills/test_skill_packaging.py` extended to the eleven folders; each signed.
- Tools: each script has a test that runs it on a small fixture model (a ten-piece stack
  checked into `skills/model-anatomy/evals/files/`), so the suite needs no temple and no GPU.
- The loop: a driver test with a scripted fake model that answers fixed JSON actions, proving
  the ledger, the cap and the replay without a real model.
- The dashboard: a page test under `tests/page/` for the timeline and the replay, and one
  look through the browser preview of a real run.
- The benchmark: one real run on the Mac with Step through the API, one on the Spark with
  Step 3.7 Flash, both recorded in `docs/measured/` with the command that produced them.

## 10. The demonstration, as the operator directed it

After the skills, the driver and the benchmark were built, the operator directed the dashboard
itself, in this order, each a grilled decision:

- **Smooth first.** "Too lag" meant the page stuttered and jumped; each step is now drawn once
  and the page holds still unless the reader is at the bottom.
- **Like a Manus demonstration.** Words type out, steps pop in, and something moves while the
  agent waits: a two-pane page, conversation left and the agent's screen right, fed by a
  one-second heartbeat from the exhibit while a tool runs (`studio/showpiece/progress.py`), so
  a render paints frame by frame on the screen.
- **The studio's own look**, not the dark stage: tokens copied from the studio page; then "more
  light and motion in the studio look": a glow while a frame is painted, the glass sheen, a burst
  of paint on a pass, the finished picture easing in.
- **A real 3D object.** The building itself on the screen, exported once from the Blender file
  (`glb.py`, light form for the hall), drawn merged by what moves together so eight thousand
  pieces run at sixty frames a second, moved by the agent's own plan files; slowed to a third on
  request, and the auto turn too.
- **Three parts.** One-press buttons that show the temple build, turn and come apart at once;
  prompt chips that replay a recorded temple run as if live (the operator chose "looks live,
  plays a recording" over a live run or quick live actions); and an always-on backend monitor
  with a flow map of the components, machine gauges and counters. Typing a prompt still runs the
  agent for real. The operator's standing direction for this module: backend fidelity does not
  matter, a smooth demonstration does; the "recorded" mark on the screen keeps it honest.

The recordings are produced by the tools themselves (`studio/showpiece/record.py`) so the Spark
can regenerate them on day zero; measurements are in
`docs/measured/demonstration-dashboard.md`.
