# Documentation

Where to read, by what you want to know. The [project README](../README.md) is the overview; start there.
Several documents are in Chinese, the language of the classroom they describe.

| Folder | What is in it |
|---|---|
| [specs/](specs/) | What the studio is meant to do: the design records and the product flows |
| [guides/](guides/) | How to stand it up, run it, sign it and present it |
| [design/](design/) | The interface rules every screen follows, and their visual reference |
| [measured/](measured/) | The evidence, one file per question |
| [screenshots/](screenshots/) | The screens the project README shows, taken from the class running on the DGX Spark |
| [ten-day-talk/](ten-day-talk/) | 十日谈: the ten days of the build, told as a story, day by day |

## specs/ — what the studio is meant to do

| Document | What it settles |
|---|---|
| [art-studio-skill-pack-design.md](specs/art-studio-skill-pack-design.md) | The canonical design record: purpose, the Skills and their contracts, the two entrances, the model slots, and the open items |
| [studio-page-contract.md](specs/studio-page-contract.md) | The routes and events between the teacher's page and the harness |
| [acceptance-criteria.md](specs/acceptance-criteria.md) | What "done" means for each part |
| [agentic-3d-showpiece-design.md](specs/agentic-3d-showpiece-design.md) | The Agentic 3D Skills and the temple showpiece |
| [creation-flow.md](specs/creation-flow.md) | 创作内容确认流程: how the teacher confirms a clip's description and a storybook's plot before anything is made |
| [teacher-review.md](specs/teacher-review.md) | 老师评价: the teacher's own review, and the order of the creative activities |
| [3d-model-selection.md](specs/3d-model-selection.md) | 素描三维方案选择: how the 3D models for the sketch entrance were chosen |

## guides/ — how it runs

| Document | What it covers |
|---|---|
| [deployment-versions.md](guides/deployment-versions.md) | 部署与运行指南: standing the studio up, which keys to open accounts for, and where a child's drawing and voice go |
| [stepfun-plan-models.md](guides/stepfun-plan-models.md) | What the StepFun subscription includes and which calls use it |
| [where-models-sit.html](guides/where-models-sit.html) | Where each model runs under StepFun First, job by job, and what does not fit on the box |
| [trellis2-dgx-spark.md](guides/trellis2-dgx-spark.md) | Reproducing the TRELLIS.2 build on the DGX Spark |
| [skill-signing.md](guides/skill-signing.md) | How every Skill folder is signed and how to check it |
| [showpiece-presenter-script.md](guides/showpiece-presenter-script.md) | A ninety-second script for presenting the temple showpiece |
| [../studio/page/README.md](../studio/page/README.md) | The teacher's page: build, test, run |

## design/ — how every screen looks

| Document | What it is |
|---|---|
| [DESIGN-PRINCIPLES.md](design/DESIGN-PRINCIPLES.md) | The interface rules; canonical, and read before touching any screen |
| [beyond-canvas-lookbook.html](design/beyond-canvas-lookbook.html) | The live visual reference, updated to match the principles |

## measured/ — what was measured

[measured/](measured/) holds the evidence, one file per question: model timings on the DGX Spark,
bake-offs between candidate models, live runs through both entrances, and every change whose effect was
checked. A claim about how a model behaves, without a file here, is a plan and not a result. Each record
names files where they were when it was written; the table below says where they are now.

## ten-day-talk/ — the story

[十日谈-按日期修订稿.md](ten-day-talk/十日谈-按日期修订稿.md) is the build told day by day, for
the hackathon's 十日谈 essay. Its numbers come from the records in measured/.

## Where files moved

Older records name the files where they were before the project was sorted into folders. File names did
not change; only their folders did.

| Was | Now |
|---|---|
| `studio/classroom*.py`, `portfolio.py`, `samples.py` | `studio/classroom/` |
| `studio/conversation.py`, `chat_beats.py`, `bridge.py`, `gates.py`, `words.py`, `strings.json`, `creation.py`, `drafting.py`, `teacher_review.py`, `session.py` | `studio/conversation/` |
| `studio/animation.py`, `book_pictures.py`, `figure.py`, `figure_render.py`, `sketch.py`, `still_life.py`, `mesh.py`, `glb.py`, `view_calibration.py`, `media_services.py` | `studio/making/` |
| `studio/speech.py`, `transcribe.py`, `audio_in.py`, `child_voice.py` | `studio/voice/` |
| `studio/serve_*.py`, `door_page.html`, `door_strings.json`, `page_transfer.py`, `stream.py`, `textstream.py`, `console_panel.py`, `ports.py` | `studio/server/` |
| `studio/harness.py`, `ledger.py`, `slots.py`, `errors.py`, `env.py`, `images.py`, `metering.py`, `watchdog.py`, `deployments.py`, `deployment_checks.py`, `prompt_book.py`, `prompt_book.json` | `studio/core/` |
| `studio/dayzero.py`, `modelboard.py`, `modelusage.py`, `spark_monitor.py`, `voice_lab.py`, `localmodels.sh` | `studio/ops/` (so `python -m studio.dayzero` is now `python -m studio.ops.dayzero`) |
| `tests/test_*.py` | `tests/<area>/`: the same areas as `studio/`, plus `providers/`, `evalkit/`, `skills/`, `deploy/` and `page/` |
| `design/` | `docs/design/` |
| `docs/creation-flow.md`, `docs/teacher-review.md` | `docs/specs/` |
| `docs/deployment-versions.md`, `stepfun-plan-models.md`, `skill-signing.md`, `showpiece-presenter-script.md`, `where-models-sit.html`, `docs/deployment/trellis2-dgx-spark.md` | `docs/guides/` |
| `3d-model-selection.md` | `docs/specs/` (by way of `docs/history/`, which was removed with the build plans, progress pages and design alternatives; git history keeps them) |
| `deploy/pixal3d/`, `deploy/wan22-smoke/`, `deploy/model-sync/` | `deploy/archive/` |

`studio/start.py` and `studio/serve.py` did not move: the studio starts with the same commands as before.
