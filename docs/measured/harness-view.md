# The Harness view

A second page on the showpiece exhibit, `http://127.0.0.1:7090/harness`, for the StepFun camp session
on harness architecture. It stands on its own: one board of the harness's parts, named by the
general terms agent harnesses use; a button for each of the nine skills a user can start;
press one and that skill's request travels the board as an animation, a caption explaining each
stop, a card for any part saying what the part is generally called, what this project has there,
and the gap between the two. The rail is a console of the journey's own log.

**It is a demonstration, not a run.** The page is fed by three checked data files, never by a model.
The footnote on the page says so, and so does this record.

## How it got this shape

The first version, built and reviewed in one sitting, drew this codebase's own names (Watchdog,
Judge, Gate, Ledger, Benchmark, Signer) and played two stories. The operator's three corrections,
each taken while looking at the page:

1. Engineering terms that only exist in English stay English inside Chinese text; then the
   diagram is English in both languages and only the descriptions switch.
2. "They don't seem like a common harness architecture." Chosen from three: redraw it in the
   terms of a widely used agent harness, every part still mapped to what this project has, the
   gap stated on the card.
3. "This harness page has nothing to do with the temple demonstration." One button per skill,
   the story switch and the temple's console gone, a standalone page titled Harness.

Later, for the public release, the names moved once more: each card had carried that one
harness's own term with a link to its documentation, and the footnote listed the pages read. Every
part now carries the plain term the field uses, and nothing on the page links away.

## The parts on the board, and where each is in the code

Every part is a common harness part, named by its general term, and names code in this repository
that plays that role. `tests/page/showpiece-harness.test.mjs` checks that each code path exists,
that every card states a gap, and that neither the board nor its words hold a web address.

| On the board | General term | Here | The gap |
|---|---|---|---|
| Request | user prompt | the studio page's button or a sentence on the exhibit, as an HTTP request | no hook on the prompt |
| Agent loop | agent loop | `driver.py` for the temple, one JSON action a turn; `harness.py` for the studio, fixed stages | in the studio the order is fixed |
| Tools | tools | the tool catalog, the slots, HTTP media workers | not MCP |
| Skills | skills (SKILL.md) | eleven packages in NVIDIA's format under `skills/`, six of them for the temple | studio skills are called by explicit Python |
| Hook: before a tool | pre-tool check | the safety screen, the catalog's argument checks, the watchdog | hard-wired calls |
| Hook: after a tool | post-tool check | the fourteen-rule rubric, the motion gate, the judge's verdict on a result | hard-wired calls |
| Hook: on stop | stop check | pass, retry once, repair, stop; the action cap | a hard-wired rule |
| Subagent | sub-agent | shot-judge, one vision call with its own prompt; the rubric judge on the director slot | separate calls, not agents with tools |
| Permissions | permissions | the catalog, the exhibit's path and origin checks, the deployment's provider choice | no sandbox, no allow or deny rules |
| Memory | project memory | SKILL.md and prompts, the course portfolio, the chosen deployment | nothing the agent writes for itself |
| Transcript | session transcript | the append-only ledger, each run's events file, the driver's prompt rebuilt from events | no compaction |
| Evals | skill evals | evals.json in every skill, the rubric and showpiece runners, BENCHMARK.md | four skills' evals have no runner |

## The nine journeys and where their facts come from

Each journey was written from a fact-gathering pass through the skill's SKILL.md and the code that
runs it, every claim with a file and line; the numbers are the measured ones. `harness-journeys.json`
holds them; the test checks each step stands on a real part, names a real skill and wire, that a
hook fires before the first tool, that every journey reaches the transcript, that the four studio
journeys are screened by studio-safety, and that the five 3D journeys are judged by shot-judge.

| Button | Skill | Numbers used | Source |
|---|---|---|---|
| 聊聊你的画 / Talk about your drawing | art-feedback | 2.0 s mean, USD 0.0013 a case, 97 % against 55 % bare, rule 12 the one that failed | `skills/art-feedback/BENCHMARK.md` |
| 让画动起来 / Make it move | painting-to-animation | pose 43 s on the 4090; clip 288 s local, 631 s on Replicate, ceiling 900 s | `docs/PROJECT-CONTEXT.md`, `studio/profiles/archive/api.yaml` |
| 形体与光影 / Form and light | sketch-to-3d | fruit round trip 92 s; TRELLIS.2 234 s service; replay 0.005 s and 0 tokens | `docs/measured/fruit-image-to-3d.md`, `four-model-scorecard.md` |
| 做本故事书 / Make a storybook | drawings-to-storybook | scene 25 to 44 s and 3.8 to 5.7k tokens; outline 77 s, 13.3k; 5 of 8 drafts passed; a page 0 tokens, 9 of 9 | `skills/drawings-to-storybook/SKILL.md` |
| 认构件 / Know the pieces | model-anatomy | inventory 0.5 s on the stack; hall 10 s for 8,170 pieces, bearing 81 s, 36 stages | `skills/model-anatomy/BENCHMARK.md`, `anatomy-of-the-hall.md` |
| 拆开来 / Take it apart | joint-reveal | 68.9 s on the stack; JOINTS 4 in 3.9 s; four renders 240, 133, 108, 128 s | `skills/joint-reveal/BENCHMARK.md`, `joint-reveal-on-the-hall.md` |
| 转一圈 / Turn it | structure-tour | 211.8 s on the stack; hall 480 frames in 1,353 s; inside re-rendered in 551 s | `skills/structure-tour/BENCHMARK.md`, `tour-raise-and-load-on-the-hall.md` |
| 盖起来 / Build it | raise-the-hall | 136.5 s on the stack; hall 311 frames in 826 s, re-render at 1.45× 799 s | same two files |
| 看载荷 / Show the load | load-path | 40.9 s on the stack; 9.23 MN against 9.83; FLOW 750 s; SETTLE fell 0 shifted 0 in 566 s | `skills/load-path/BENCHMARK.md`, same hall record |

The judge's fail-then-pass in the temple journeys mirrors what the hall records show (a tenon
close-up that took four attempts, a tour segment re-rendered, a raise re-rendered at a wider orbit);
the studio journeys' rule-12 failure and retry mirror the benchmark's one failed rule. Seconds
for the safety verdict and the rubric calls appear nowhere as measured and carry no number.

## How it was verified

- `node --test tests/page/showpiece-harness.test.mjs`: 13 checks, listed above.
- `tests/showpiece/test_showpiece_serve.py`: `/harness` and its seven files are served.
- A headless browser walk at 1600×900 on the exhibit started from the worktree on port 7600: no
  console errors; nine buttons; an idle board until one is pressed; a press starts the journey and
  the number keys start any of the nine; the arrows step; the lit part, tile and wire follow the
  step; the caption and transcript lines follow the language; the console shows a timestamped log
  and a checklist of parts touched; clicking a part pins its card, with the documentation link and
  the gap line, and Escape releases it; the language switch keeps the step and the board's names.
- The console clears when a journey wraps: the play module now returns the lap, and the page
  rebuilds the log from the journey each paint rather than accumulating, which closes the finding
  the first review made.
- The page suite and the Python suite were run whole before landing.
- Seen afterwards on the operator's own screen and reproduced in a browser at 1800×780: on the one-screen
  breakpoint the demo's stylesheet gives the wrapper two rows, header and stage, so this page's button row
  landed in the flexible row and collapsed to nothing on a window under about 820 px tall, the stage drawn
  over the buttons. The page's wrapper now declares its own three rows with the stage the flexible one;
  measured after the fix at 1800×780 the rows are 49, 84 and 594 px, the buttons clear of the stage, no
  page scroll, and the demo page's two rows unchanged. The test file checks the rule is there.

## What stays out, and why

- **No sandbox and no network allowlist on the board.** None exists in the system; the Permissions
  card says so.
- **The link from the temple demo's header** was left out of the first landing because another
  window held uncommitted edits to `studio/showpiece/page/app.js` and `strings.json` at the time.
  It landed the next morning: a ghost button labelled Harness beside the language
  button, its label from the demo's strings file in both languages, checked by the strings test.
- **Nothing live.** The page explains the machinery; a live run belongs to the temple demo.
