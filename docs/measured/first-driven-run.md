# The first run driven by Step 3.7 Flash

`studio/showpiece/driver.py` with the `api` profile's `vlm.studio` slot (`step-3.7-flash` via
StepFun, reasoning effort low), on the eleven-piece test stack, cap 8 actions. The request:
"What is in this little building, and in what order was it put up?"

```bash
.venv/bin/python - <<'PY'
from pathlib import Path
from studio.env import load_dotenv
from studio.providers import build_client
from studio.slots import load_profile, resolve
from studio.showpiece.driver import Driver
load_dotenv()
config = resolve("vlm.studio", load_profile("api")); config.options.setdefault("reasoning_effort", "low")
run = Driver(build_client(config), Path("skills/model-anatomy/evals/files/stack.blend"), Path(".studio/showpiece/runs"), cap=8).run_sync(
    "What is in this little building, and in what order was it put up?")
PY
```

## Attempt 1: the model drowned in instructions

With all six SKILL.md bodies in the system prompt (about 14,000 characters), the first call
returned nothing after 4,000 completion tokens of hidden thinking. Fix: the system prompt now
carries the protocol and the six one-line descriptions, and the full instructions only of the
skills the run has used (model-anatomy and shot-judge always), the way a skill loads on
trigger; the budget is 6,000 with one retry at 12,000; an empty answer after that stops the
run with a ledger line saying so.

## Attempt 2: a correct answer in 84 seconds, with four stumbles

Run `20260917-050001-ea0fde`, 18 events, 8 actions, wall time 83.7 s, 2,000 to 5,200 tokens a
turn (hidden thinking included).

| Step | Kind | What happened |
|---|---|---|
| 1–2 | think, act | inventory with an argument `model.blend`: refused, "takes no argument" |
| 3–4 | think, act | inventory with `model`: refused again |
| 5–6 | think, act | inventory with `out_dir` only: **ANATOMY 11 pieces** |
| 7–8 | think, act | tool written as `model-anatomy/bearing`: "no such tool", the list of tools returned |
| 9–10 | think, act | bearing: **9 pieces, 0 floating, 5 stages** |
| 11–12 | think, act | stages without its `bearing` argument: "needs 'bearing'" |
| 13–14 | think, act | tool written as `stages.py`: "no such tool" |
| 15–16 | think, act | stages with bearing, anatomy, out_dir: **SCENES 5 from 5 stages** |
| 17–18 | think, final | "11 pieces: 1 ground slab, 7 timber members, 2 rafters, 1 roof covering. The construction order, from the bottom up, is: ground → columns → ..." |

The answer is right. Every stumble was recovered from the tool's own refusal text, which is what
the refusals are for. Three changes followed, so the next run should need fewer turns: the
driver accepts a tool name with its skill prefix; the protocol says the model file is supplied
and that positional arguments are given by name; and a built-in `read` tool lets the model read
a JSON result (a digest for big ones), since at step 17 it wanted to read `scenes.json` and
could not.

The dashboard showed the run live at `http://127.0.0.1:7090/`: the think and act rows with the
tool tails, the token counts per turn, the machine gauge (52 of 69 GB in use with three
renders running), and the runs list.
