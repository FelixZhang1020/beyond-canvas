"""Benchmark a classroom skill against the same model working without it.

`evalkit.runner` measures `art-feedback` against the fourteen pedagogy rules, which
only judges writing. `evalkit.showpiece` measures the temple skills by driving an
agent over the carpentry tools. Neither fits the two classroom skills that own a
script and answer in one call: `studio-safety`, which decides whether a drawing may
be seen at all, and `painting-to-animation`, which plans what moves.

Both are measured the same way NVIDIA names for a verified skill: the same model,
the same picture, twice. Once through the skill's real path, and once asked plainly,
with none of the skill's instructions in front of it. A judge model then reads each
answer against the behaviours the eval case already lists, one at a time, and says
whether each holds.

What this does not promise. The judge is a model and can be wrong; its verdicts are
written into the report case by case so a reader can disagree with any of them. The
behaviours come from the eval files and were written before these runs, which is the
only reason the comparison means anything. Three other classroom skills are absent on
purpose: they own no script, the model does not make their mesh or their book, and a
bare-model column for them would be a number with nothing behind it.

Usage: uv run python -m evalkit.classbench --skill studio-safety --profile stepfun --slot vlm.studio
           [--no-write] [--pause 7]
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

ROOT = Path(__file__).resolve().parent.parent
SKILLS = ROOT / "skills"
NO_SKILL_SUFFIX = "+no-skill"
PAUSE_S = 7.0                      # the StepFun key allows ten requests a minute
JUDGE_SYSTEM = "You are a strict examiner. Reply with JSON only. No prose, no code fences."
# Step 3.7 Flash bills hidden reasoning against this. Measured: at 4,000 the judge
# ran out on three cases and all three were in the bare column, because a bare answer is long
# prose where the skill returns compact JSON. A judge that fails more often on one side is a
# thumb on the scale, so the budget is large and the failures are counted in the table.
JUDGE_MAX_TOKENS = 12000
# The bare model is given exactly the budget the skill's own call is given. Measured:
# a first run gave the skill 12,000 tokens and the bare model 1,000, and three
# of its seven bare runs died of a truncated completion rather than of a bad answer. A
# comparison that starves one side measures the harness, and it flattered us.
SAFETY_MAX_TOKENS = 12000       # matches `max_tokens` in skills/studio-safety/scripts/safety.py
ANIMATION_MAX_TOKENS = 8000     # matches CHOREOGRAPHY_MAX_TOKENS in choreograph.py


def load_script(path: Path, name: str):
    """Import a skill script by path, the way the harness runs it. Registered in
    sys.modules first, or a dataclass inside it cannot resolve its own annotations."""
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


@dataclass(frozen=True)
class Answer:
    """What one run produced: the text the judge reads, and whether the skill's own
    gate accepted it. `gate` is None for a skill that has no gate of its own."""
    text: str
    gate: bool | None = None
    note: str = ""


@dataclass(frozen=True)
class Outcome:
    case_id: str
    slot: str
    answer: Answer
    met: tuple[bool, ...]
    behaviours: tuple[str, ...]
    why: tuple[str, ...]
    latency_s: float
    tokens: int

    @property
    def passed_all(self) -> bool:
        return bool(self.met) and all(self.met)

    @property
    def judge_failed(self) -> bool:
        return any(reason.startswith("the judge") for reason in self.why)


# --- the two skills that can be measured this way ---------------------------

def _safety(client) -> tuple[Callable[[Path], Answer], Callable[[Path], Answer]]:
    skill = load_script(SKILLS / "studio-safety/scripts/safety.py", "classbench_safety")
    from studio.core.images import to_data_uri

    def with_skill(image: Path) -> Answer:
        verdict = skill.screen(to_data_uri(str(image)), client)
        return Answer(json.dumps({"verdict": verdict.verdict, "reason": verdict.reason,
                                  "text_found": list(verdict.text_found)}, ensure_ascii=False),
                      gate=verdict.may_proceed)

    def bare(image: Path) -> Answer:
        reply = client.chat("Look at this image. A teacher submitted it to a children's art studio. "
                            "Should the studio accept it? Give your verdict and your reason.",
                            [to_data_uri(str(image))], max_tokens=SAFETY_MAX_TOKENS)
        return Answer(reply.text)

    return with_skill, bare


def _animation(client) -> tuple[Callable[[Path], Answer], Callable[[Path], Answer]]:
    skill = load_script(SKILLS / "painting-to-animation/scripts/choreograph.py", "classbench_choreo")
    from studio.core.images import to_data_uri

    def with_skill(image: Path) -> Answer:
        try:
            plan = skill.choreograph(str(image), "en", client)
        except Exception as problem:                      # a plan the skill cannot even read
            return Answer(f"the skill could not read a plan out of the reply: {problem}", gate=False,
                          note="unreadable")
        broken = skill.problems(plan)
        return Answer(json.dumps(plan.as_dict(), ensure_ascii=False), gate=not broken,
                      note="; ".join(broken))

    def bare(image: Path) -> Answer:
        reply = client.chat("Look at this child's drawing. Plan a short animation of it: "
                            "which parts move, how, and for how long. Answer as JSON.",
                            [to_data_uri(str(image))], max_tokens=ANIMATION_MAX_TOKENS)
        try:
            plan = skill.parse(reply.text)
        except Exception:
            return Answer(reply.text, gate=False, note="unreadable")
        return Answer(json.dumps(plan.as_dict(), ensure_ascii=False), gate=not skill.problems(plan))

    return with_skill, bare


ADAPTERS: dict[str, Any] = {"studio-safety": _safety, "painting-to-animation": _animation}


# --- running and judging ----------------------------------------------------

def cases_for(skill: str) -> list[dict]:
    return json.loads((SKILLS / skill / "evals/evals.json").read_text(encoding="utf-8"))


def image_for(case: dict, skill: str) -> Path | None:
    """The picture a case names, or None when it is not in the repository.

    Two conventions are in use and both are honoured: `art-feedback` writes its paths
    from the skill folder, `studio-safety` writes them from its `evals` folder. One
    case names a photograph of an adult, which is what it exists to have refused; that
    file is deliberately not committed, so the case is reported as not run rather than
    quietly passed or quietly dropped.
    """
    import re

    found = re.search(r"File:\s*(\S+)", case["question"])
    if not found:
        return None
    for root in (SKILLS / skill, SKILLS / skill / "evals"):
        candidate = (root / found.group(1)).resolve()
        if candidate.is_file():
            return candidate
    return None


def judge(client, case: dict, answer: Answer) -> tuple[tuple[bool, ...], tuple[str, ...]]:
    """One call for the whole case: every listed behaviour, each answered yes or no."""
    behaviours = list(case["expected_behavior"])
    numbered = "\n".join(f"{i + 1}. {b}" for i, b in enumerate(behaviours))
    try:
        reply = client.chat(
            f"A skill was asked: {case['question']}\n\n"
            f"What a correct answer looks like: {case['ground_truth']}\n\n"
            f"The answer given:\n{answer.text}\n\n"
            f"For each requirement below, say whether the answer meets it. Judge only what is "
            f"written; do not give credit for what the answer might have meant.\n{numbered}\n\n"
            f'Reply as {{"results": [{{"n": 1, "met": true, "why": "a few words"}}, ...]}}',
            [], system=JUDGE_SYSTEM, max_tokens=JUDGE_MAX_TOKENS)
    except Exception as problem:
        # Never lose a run at its last case. Every case before this one has been paid
        # for, and a judge that could not answer is a fact worth printing, not a crash.
        return tuple(False for _ in behaviours), tuple(f"the judge failed: {problem}"[:120]
                                                       for _ in behaviours)
    text = reply.text.strip().removeprefix("```json").removeprefix("```").removesuffix("```")
    try:
        rows = {int(r["n"]): r for r in json.loads(text)["results"]}
    except Exception:
        return tuple(False for _ in behaviours), tuple("the judge did not answer" for _ in behaviours)
    met = tuple(bool(rows.get(i + 1, {}).get("met")) for i in range(len(behaviours)))
    why = tuple(str(rows.get(i + 1, {}).get("why", ""))[:120] for i in range(len(behaviours)))
    return met, why


def run(skill: str, client, judge_client, slot: str, pause: float,
        skipped: list[str] | None = None) -> list[Outcome]:
    with_skill, bare = ADAPTERS[skill](client)
    outcomes: list[Outcome] = []
    skipped = skipped if skipped is not None else []
    for case in cases_for(skill):
        image = image_for(case, skill)
        if image is None:
            print(f"  {case['id']:<40} not run: its picture is not in the repository")
            skipped.append(case["id"])
            continue
        for name, call in ((slot, with_skill), (slot + NO_SKILL_SUFFIX, bare)):
            started = time.monotonic()
            try:
                answer = call(image)
            except Exception as problem:
                answer = Answer(f"the run failed: {problem}", gate=False,
                                note=f"failed: {problem}"[:140])
            elapsed = time.monotonic() - started
            time.sleep(pause)
            met, why = judge(judge_client, case, answer)
            time.sleep(pause)
            outcomes.append(Outcome(case["id"], name, answer, met, tuple(case["expected_behavior"]),
                                    why, round(elapsed, 1), 0))
            print(f"  {case['id']:<40} {name:<28} {sum(met)}/{len(met)}  {elapsed:.1f}s")
    return outcomes


# --- the report -------------------------------------------------------------

# Written into every report, because a number published without its limits invites a reader
# to believe more than it says. Both lines below were learned the same day the first of these
# reports was produced.
LIMITS = [
    "## What this does not promise",
    "",
    "- **One run, of a model that does not answer the same way twice.** This same code,",
    "  unchanged, scored 86 % and then 100 % on the skill column of two consecutive runs. An",
    "  earlier overnight measurement found the same thing at a larger scale: the measurement",
    "  moves more than most fixes do. A single figure here is worth less than the gap between the",
    "  two rows, which was large and in the same direction both times.",
    "- **The judge is the model that wrote the answers.** It grades its own work in the first row and",
    "  its own unaided work in the second, which is why every verdict is printed above rather than",
    "  summarised. A second model has not been asked.",
    "- **No real child's drawing.** The pictures are the generated test drawings in the repository.",
    "",
]


def render(skill: str, outcomes: list[Outcome], provenance: str,
           skipped: tuple[str, ...] = ()) -> str:
    slots: dict[str, list[Outcome]] = {}
    for outcome in outcomes:
        slots.setdefault(outcome.slot, []).append(outcome)
    lines = [f"# BENCHMARK: {skill}", "", provenance, "",
             "| Slot | Cases | Cases meeting every requirement | Mean requirements met | "
             "Accepted by the skill's own gate | Judge could not answer | Mean latency s |",
             "|---|---|---|---|---|---|---|"]
    for name, rows in slots.items():
        met = sum(sum(r.met) for r in rows)
        total = sum(len(r.met) for r in rows)
        gated = [r for r in rows if r.answer.gate is not None]
        passed = f"{sum(1 for r in gated if r.answer.gate)}/{len(gated)}" if gated else "n/a"
        lines.append(f"| `{name}` | {len(rows)} | {sum(r.passed_all for r in rows) / len(rows):.0%} | "
                     f"{met / total:.0%} | {passed} | {sum(r.judge_failed for r in rows)} | "
                     f"{sum(r.latency_s for r in rows) / len(rows):.1f} |")
    if skipped:
        lines += ["", "## Cases not run", "",
                  "A case whose picture is not in the repository is counted nowhere above.", ""]
        lines += [f"- **{name}** — its picture is not committed" for name in skipped]
    lines += ["", "## Every requirement, case by case", "",
              "The judge is a model. Its verdict on each line is printed so a reader can disagree. "
              "A case where the judge could not answer is counted as met by nothing, so any column "
              "with a number above zero in that last cell is reading low.", ""]
    for name, rows in slots.items():
        lines += [f"### `{name}`", ""]
        for row in rows:
            lines.append(f"- **{row.case_id}** — {sum(row.met)}/{len(row.met)}"
                         + (f" · gate: {'accepted' if row.answer.gate else 'refused'}"
                            if row.answer.gate is not None else "")
                         + (f" · {row.answer.note}" if row.answer.note else ""))
            for behaviour, met, why in zip(row.behaviours, row.met, row.why):
                lines.append(f"  - {'✓' if met else '✗'} {behaviour}" + (f" — {why}" if why else ""))
        lines.append("")
    return "\n".join(lines + LIMITS) + "\n"


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Measure a classroom skill against the bare model.")
    parser.add_argument("--skill", required=True, choices=sorted(ADAPTERS))
    parser.add_argument("--profile", default="stepfun")
    parser.add_argument("--slot", default="vlm.studio")
    parser.add_argument("--pause", type=float, default=PAUSE_S)
    parser.add_argument("--no-write", action="store_true", help="print, do not touch BENCHMARK.md")
    args = parser.parse_args(argv)
    from studio.core.env import load_dotenv
    from studio.providers import build_client
    from studio.core.slots import load_profile, resolve

    load_dotenv()
    config = resolve(args.slot, load_profile(args.profile))
    config.options.setdefault("reasoning_effort", "low")   # its hidden reasoning is billed as output
    print(f"slot {args.slot} in profile {args.profile} is {config.model} via {config.provider}; "
          f"skill {args.skill}; {len(cases_for(args.skill))} cases, each run twice and judged")
    client = build_client(config)
    skipped: list[str] = []
    outcomes = run(args.skill, client, client, args.slot, args.pause, skipped)
    provenance = (f"Provenance: {config.model} via {config.provider}, profile `{args.profile}`, slot "
                  f"`{args.slot}`, judged by the same model, "
                  f"{time.strftime('%Y-%m-%d')}. Produced by `python -m evalkit.classbench "
                  f"--skill {args.skill} --profile {args.profile} --slot {args.slot}`.")
    body = render(args.skill, outcomes, provenance, tuple(skipped))
    print("\n" + body)
    if not args.no_write:
        (SKILLS / args.skill / "BENCHMARK.md").write_text(body, encoding="utf-8")
        print(f"written: skills/{args.skill}/BENCHMARK.md")


if __name__ == "__main__":
    main()
