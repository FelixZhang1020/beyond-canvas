"""The showpiece benchmark: every eval request of the six skills, run by one model twice, with
the skills loaded and with only the raw tool list, scored the same way. What NVIDIA names for a
verified skill is the distance between those two rows.
Usage: uv run python -m evalkit.showpiece --profile stepfun --slot vlm.studio --model <path.blend>
           [--only joint-reveal] [--cap 40] [--no-write] [--runs .studio/showpiece/runs]
"""
from __future__ import annotations

import argparse
import json
import re
import time
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from studio.showpiece import catalog
from studio.showpiece.catalog import SIX
from studio.showpiece.driver import PROTOCOL, Driver

PAUSE_S = 7.0   # the StepFun key allows ten requests a minute


@dataclass(frozen=True)
class Case:
    skill: str
    id: str
    question: str
    expected_skill: str
    expected_script: str
    # Pictures the question names, copied into the run folder before the agent starts.
    # Without these a case that names a file is answered "the file is not in the run
    # folder" by both modes, which is how `shot-judge` stayed unmeasured at first.
    seed: tuple[tuple[str, Path], ...] = ()

    @property
    def expected_tools(self):
        stem = Path(self.expected_script).stem
        return [(self.expected_skill, stem)] if (self.expected_skill, stem) in catalog.TOOLS else []


@dataclass(frozen=True)
class Outcome:
    case_id: str
    mode: str
    completed: bool
    actions: int
    judged: int
    passed: int
    tokens: int
    seconds: float
    final: str


def cases(skills_root: Path, model: Path | None, out_dir: Path, only: str | None = None,
          ids: set[str] | None = None) -> list[Case]:
    """Every eval question of the six skills, with the model and run-folder placeholders filled.
    `only` keeps one skill; `ids` keeps named cases (the stack cases, when the hall is absent)."""
    out = []
    for skill in SIX:
        if only and skill != only:
            continue
        for entry in json.loads((skills_root / skill / "evals/evals.json").read_text(encoding="utf-8")):
            if ids and entry["id"] not in ids:
                continue
            question = entry["question"].replace("<model.blend>", str(model) if model else "the model given to every tool")
            question = question.replace("<out_dir>/", "").replace("<out_dir>", ".")
            question, seed = _seeded(question, skills_root / skill)
            out.append(Case(skill, entry["id"], question, entry["expected_skill"],
                            entry["expected_script"], seed))
    return out


def _seeded(question: str, skill_dir: Path) -> tuple[str, tuple[tuple[str, Path], ...]]:
    """Point each named picture at the run folder, and say where to copy it from.

    The driver copies a seed flat, so the question is rewritten to the bare filename.
    A path that names no file on disk is left exactly as it is: the run then fails the
    way it always did, and the report says so, rather than the picture being invented.
    """
    seed = []
    for named in re.findall(r"File:\s*(\S+)", question):
        source = (skill_dir / named).resolve()
        if not source.is_file():
            continue
        seed.append((source.name, source))
        question = question.replace(named, source.name)
    return question, tuple(seed)


class BareDriver(Driver):
    """The same loop with no skill text: the protocol and the tool list, nothing else."""

    def system_prompt(self, run_dir: Path, used=frozenset()) -> str:
        tools = "\n".join(f"- {s.skill}/{s.tool}: positional {list(s.positional)} flags {list(s.flags)} repeat {list(s.repeat)}"
                          for s in catalog.SPECS)
        text = PROTOCOL.read_text(encoding="utf-8").replace("{skills}", "(no skill descriptions; tools only)")
        return text.replace("{run_dir}", str(run_dir)) + "\n\nTools:\n" + tools


def bare_driver(client, model, runs_root, cap: int = 40) -> Driver:
    return BareDriver(client, model, runs_root, cap=cap, agent_name="bare")


def score(case_id: str, mode: str, events: list[dict], expected_tools) -> Outcome:
    acts = [e for e in events if e["kind"] == "act"]
    called = {(e.get("skill"), e.get("tool")) for e in acts}
    completed = bool(events) and events[-1]["kind"] == "final" and all(t in called for t in expected_tools)
    judged = [e for e in acts if e.get("tool") == "judge"]
    passed = sum(1 for e in judged if (e.get("verdict") or {}).get("verdict") == "pass")
    return Outcome(case_id, mode, completed, len(acts), len(judged), passed,
                   sum(e.get("tokens", 0) for e in events), round(sum(e.get("seconds", 0.0) for e in events), 1),
                   events[-1].get("text", "") if events else "")


# A table of bare numbers is read wrongly by anyone who did not write it. "judged pass/total"
# counts how many of the run's `judge` calls answered `pass` — it is not a score out of ten,
# and on a case built to be refused a zero is the right answer, not a failure.
READING = [
    "",
    "## How to read this",
    "",
    "- **mode** — `skills` is the model with the skill descriptions in front of it; `bare` is the",
    "  same model with the same tools and no skill text. The distance between the two rows is what",
    "  the skill is worth.",
    "- **judged pass/total** — how many of the run's `judge` calls answered `pass`. **A case whose",
    "  name ends in `-fail` is built around a picture that should be refused, so `0/1` there is the",
    "  correct answer and not a failure.**",
    "- **completed** — the run reached a final answer and called every tool the case names.",
    "- **actions** — tool calls the model chose to make. Fewer is not better; it is the price paid.",
]


def render(outcomes: list[Outcome], provenance: str) -> str:
    lines = ["# BENCHMARK: showpiece skills", "", f"Provenance: {provenance}", "",
             "| case | mode | completed | actions | judged pass/total | tokens | tool seconds |",
             "|---|---|---|---|---|---|---|"]
    for o in outcomes:
        lines.append(f"| {o.case_id} | {o.mode} | {'yes' if o.completed else 'no'} | {o.actions} | "
                     f"{o.passed}/{o.judged} | {o.tokens} | {o.seconds} |")
    return "\n".join(lines + READING) + "\n"


def per_skill(outcomes: list[Outcome], found: list[Case], skill: str, provenance: str) -> str:
    ids = {c.id for c in found if c.skill == skill}
    body = render([o for o in outcomes if o.case_id in ids], provenance)
    return body.replace("# BENCHMARK: showpiece skills", f"# BENCHMARK: {skill}", 1)


def run_all(client, args) -> tuple[list[Outcome], list[Case]]:
    ids = set(args.cases.split(",")) if args.cases else None
    found = cases(Path("skills"), args.model, args.runs, args.only, ids)
    outcomes = []
    for case in found:
        for mode, make in (("skills", Driver), ("bare", bare_driver)):
            driver = make(client, args.model, args.runs, cap=args.cap)
            started = time.monotonic()
            run = driver.run_sync(case.question, seed=dict(case.seed))
            outcome = score(case.id, mode, run.events, case.expected_tools)
            print(f"{case.id:32} {mode:6} completed={outcome.completed} actions={outcome.actions} "
                  f"judged={outcome.passed}/{outcome.judged} tokens={outcome.tokens} wall={time.monotonic() - started:.0f}s")
            print("   final:", outcome.final[:300].replace("\n", " "))
            outcomes.append(outcome)
            time.sleep(PAUSE_S)
    return outcomes, found


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Run the six skills' eval requests with and without the skills.")
    parser.add_argument("--profile", default="stepfun")  # api until its archive
    parser.add_argument("--slot", default="vlm.studio")
    parser.add_argument("--model", type=Path, default=None)
    parser.add_argument("--only", default=None, help="one skill's cases")
    parser.add_argument("--cases", default=None, help="comma-separated case ids, e.g. the stack cases")
    parser.add_argument("--cap", type=int, default=40)
    parser.add_argument("--runs", type=Path, default=Path(".studio/showpiece/runs"))
    parser.add_argument("--no-write", action="store_true")
    args = parser.parse_args(argv)
    from studio.core.env import load_dotenv
    from studio.providers import build_client
    from studio.core.slots import load_profile, resolve

    load_dotenv()
    config = resolve(args.slot, load_profile(args.profile))
    config.options.setdefault("reasoning_effort", "low")
    provenance = (f"{config.model} via {config.provider}, profile {args.profile}, slot {args.slot}, "
                  f"model {args.model}, cap {args.cap}, {datetime.now(UTC).date()}")
    outcomes, found = run_all(build_client(config), args)
    table = render(outcomes, provenance)
    print(table)
    if args.no_write:
        return
    for skill in {c.skill for c in found}:
        (Path("skills") / skill / "BENCHMARK.md").write_text(per_skill(outcomes, found, skill, provenance), encoding="utf-8")
    record = Path("docs/measured") / f"{datetime.now(UTC).date()}-showpiece-benchmark.md"
    record.write_text(table, encoding="utf-8")
    print("written", record)


if __name__ == "__main__":
    main()
