# BENCHMARK: hall-carpenter

Provenance: step-3.7-flash via stepfun, profile api, slot vlm.studio, temple
output/foguang-east-hall/foguang-east-hall-v25.blend, cap 80, 6 repair laps, 3 refusals.
Command: `uv run python -m evalkit.fromzero --profile api --slot vlm.studio`. One case
(`carpenter-rebuild-the-hall`), three runs, the harness and the skill changed between them; the
changes and what each run got wrong are in `docs/measured/from-nothing-rebuild.md`.

| run | adopted | hanging | fell / shifted | shadows front / side / above | columns | through the roof | actions | repair laps | tokens | seconds |
|---|---|---|---|---|---|---|---|---|---|---|
| 1 | no | 6 | 26 / 0 | not reached | 36 of 36 | not checked | 35 | 2 | 510,181 | 785 |
| 2 | yes, wrongly | 0 | 0 / 0 | 0.953 / 0.913 / 0.958 | 36 of 36 | 2 (check added after) | 27 | 0 | 224,466 | 364 |
| 3 | yes | 0 | 0 / 0 | 0.944 / 0.908 / 0.986 | 36 of 36 | 0 | 45 | 5 | 466,467 | 680 |
| by hand, no model | — | 0 | 0 / 0 | 0.957 / 0.934 / 0.991 | 36 of 36 | 0 | — | — | 0 | 120 |

No bare-model row: without the skill there is no tool that places timber, so there is nothing to compare.
