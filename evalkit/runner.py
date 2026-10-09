"""Run the eval suite across one or more slots and report the difference.

Two comparisons matter and they answer different questions.

Studio model against director model asks which model to run, and is what the
Spark memory budget forces a decision on.

The skill against the same model with no skill asks whether the skill earns its
place at all. That is the comparison NVIDIA names for a verified skill, beside
trigger accuracy and token efficiency, and it is the one a judge can read
without knowing anything about the codebase. A bare run is recorded under the
same slot name with a "+no-skill" suffix so the two sit side by side.

Everything printed is a number a judge can repeat: pass rate, which rules
failed, what it cost, how long it took.
"""

from __future__ import annotations

import argparse

import json
import re
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from evalkit.rubric import Entrance, run_rubric
from evalkit.rubric.report import RubricReport

FILE_IN_QUESTION = re.compile(r"File:\s*(\S+)")
ENTRANCE_IN_QUESTION = re.compile(r"\b(sketch|colour) entrance\b")
PASS_THRESHOLD = 0.9
NO_SKILL_SUFFIX = "+no-skill"

# What a capable model does when simply asked, with none of the fourteen rules
# in front of it. The point of the pack is the distance between this and the skill.
BARE_PROMPT = "Give feedback on this child's drawing."


@dataclass(frozen=True)
class CaseOutcome:
    case_id: str
    slot: str
    text: str
    report: RubricReport
    latency_s: float
    cost_usd: float
    tokens: int


def drawing_for(question: str, root: Path) -> Path | None:
    paths = FILE_IN_QUESTION.findall(question)
    if not paths:
        return None
    candidate = root / paths[0]
    return candidate if candidate.is_file() else None


def entrance_for(question: str) -> Entrance:
    """Which door the case walks through.

    The teacher picks the entrance by hand, so a case that names none is a
    broken case rather than a colour one: refusing it keeps a sketch study
    from being graded as a painting by accident.
    """
    match = ENTRANCE_IN_QUESTION.search(question)
    if match is None:
        raise ValueError(
            "the case names no entrance; say 'at the sketch entrance' or "
            f"'at the colour entrance': {question[:80]!r}"
        )
    return "sketch" if match.group(1) == "sketch" else "colour"


def summarise(outcomes: list[CaseOutcome]) -> dict[str, Any]:
    summary: dict[str, Any] = {"slots": {}}
    for slot in sorted({outcome.slot for outcome in outcomes}):
        rows = [outcome for outcome in outcomes if outcome.slot == slot]
        failures: Counter[str] = Counter()
        for row in rows:
            failures.update(str(failure.rule) for failure in row.report.failures)
        summary["slots"][slot] = {
            "cases": len(rows),
            "case_pass_rate": sum(row.report.passed for row in rows) / len(rows),
            "mean_rule_pass_rate": sum(row.report.pass_rate for row in rows) / len(rows),
            "failures_by_rule": dict(failures),
            "total_cost_usd": round(sum(row.cost_usd for row in rows), 6),
            "mean_latency_s": round(sum(row.latency_s for row in rows) / len(rows), 2),
            "mean_tokens": round(sum(row.tokens for row in rows) / len(rows)),
        }
    return summary


def _skill_lift(summary: dict[str, Any]) -> list[str]:
    """Pair every slot with its bare twin, where one was run."""
    slots = summary["slots"]
    pairs = [
        (name, name + NO_SKILL_SUFFIX)
        for name in slots
        if not name.endswith(NO_SKILL_SUFFIX) and name + NO_SKILL_SUFFIX in slots
    ]
    if not pairs:
        return ["", "## Does the skill earn its place?", "",
                "Not measured: no bare run in this benchmark."]
    lines = ["", "## Does the skill earn its place?", "",
             "| Model | With the skill | Bare model | Lift |", "|---|---|---|---|"]
    for name, bare in pairs:
        with_skill = slots[name]["mean_rule_pass_rate"]
        without = slots[bare]["mean_rule_pass_rate"]
        lines.append(
            f"| `{name}` | {with_skill:.0%} | {without:.0%} | "
            f"{with_skill - without:+.0%} |"
        )
    return lines


def red_line_failures(outcomes: list[CaseOutcome]) -> dict[str, int]:
    """How many cases crossed a red line, which no average can excuse.

    This used to read `outcome.label`, and no such field exists. It
    only runs when a red line is actually crossed, which the six invented
    fixtures never did, so the crash sat behind the one condition that means
    the benchmark has something serious to report — and it would have thrown
    away the whole run, after every case had been paid for, at the last step.
    """
    counts: dict[str, int] = {}
    for outcome in outcomes:
        if outcome.report.crossed:
            counts[outcome.slot] = counts.get(outcome.slot, 0) + 1
    return counts


def render_benchmark(summary: dict[str, Any], provenance: str = "") -> str:
    """The table, and which model produced it.

    A published number that does not name its model is the defect this argument
    already had once: BENCHMARK.md carried figures from `cloud`, where the writer
    is a hosted stand-in, and nothing on the page said the shipping model had
    never been measured. The line below makes that impossible to repeat.
    """
    lines = ["# BENCHMARK: art-feedback", ""]
    if provenance:
        lines += [provenance, ""]
    lines += [
        "| Slot | Cases | Cases passing all rules | Mean rule pass rate | Cost USD | Mean latency s |",
        "|---|---|---|---|---|---|",
    ]
    for slot, row in summary["slots"].items():
        lines.append(
            f"| `{slot}` | {row['cases']} | {row['case_pass_rate']:.0%} | "
            f"{row['mean_rule_pass_rate']:.0%} | {row['total_cost_usd']:.4f} | "
            f"{row['mean_latency_s']} |"
        )
    lines += ["", "## Failures by rule", ""]
    for slot, row in summary["slots"].items():
        broken = row["failures_by_rule"] or {"none": 0}
        detail = ", ".join(f"rule {rule}: {count}" for rule, count in sorted(broken.items()))
        lines.append(f"- `{slot}`: {detail}")
    lines += _skill_lift(summary)
    if summary["slots"]:
        best = max(summary["slots"].values(), key=lambda row: row["mean_rule_pass_rate"])
        verdict = "PASS" if best["mean_rule_pass_rate"] >= PASS_THRESHOLD else "FAIL"
        lines += ["", f"**Verdict: {verdict}** at a {PASS_THRESHOLD:.0%} mean rule pass rate."]
    else:
        # Every case skipped — usually a missing drawing. Crashing here would
        # throw away a run after each remaining case had already been paid for.
        lines += ["", "**No verdict: every case was skipped.** Nothing was measured."]
    lines += _how_to_read()
    return "\n".join(lines) + "\n"


def _how_to_read() -> list[str]:
    """Numbers without their caveats are worse than no numbers."""
    return [
        "",
        "## How to read this",
        "",
        "**Mean rule pass rate** averages the rules that actually applied to each case, which "
        "for an opening with no transcript is eleven of the fourteen: rules 13 and 14 need the "
        "child to have spoken and rule 11 needs a lesson intent. **Cases passing "
        "all rules** is the stricter number: one rule failing anywhere fails the case.",
        "",
        "Rules 6 and 7 are skipped on the sketch entrance, where correction is expected "
        "and proportion is the subject, and rule 12 asks there for a question about the "
        "student's own process rather than the world inside the picture.",
        "",
        "A rule the judge could not reach is recorded as skipped, not passed. Skipped "
        "rules are excluded from the score rather than counted, so an unreachable judge "
        "lowers how much was measured instead of inflating the result.",
        "",
        "**Refusal cases are scored against the wrong yardstick.** A blank page cannot "
        "satisfy rule 3, which wants two visible details, and the right reply to it is a "
        "closed request for a photo rather than the open question rule 9 wants. Those "
        "failures are correct readings of the rules and wrong about the reply. Read the "
        "reply for those cases; see references/rubric.md.",
        "",
        "Cases whose drawing is not on disk are skipped and never counted. The "
        "not-a-drawing case needs a real photograph, which is not committed.",
    ]


WRITER_ATTEMPTS = 2


def _write_or_skip(writer, prompt: str, image: str, case_id: str):
    """Ask the model for one piece of feedback, and survive it not answering.

    Step 3.7 Flash returns empty content now and then whatever the ceiling is:
    a sweep of fourteen drawings hit it twice at 6000 tokens and
    once more at 12000, so headroom makes it rarer without making it go away.

    Unguarded, one of those aborted the whole benchmark and threw away every
    case already paid for. A retry catches most of them, and a case that still
    will not answer is dropped from the run with a line saying so. Dropping is
    the honest option: a model that said nothing has earned neither a pass nor
    a fail, and scoring silence as zero would report an outage as a quality.
    """
    from studio.core.errors import ModelError

    last: Exception | None = None
    for _ in range(WRITER_ATTEMPTS):
        try:
            return writer.chat(prompt, [image])
        except ModelError as error:
            last = error
    print(f"skip {case_id}: the model returned nothing in {WRITER_ATTEMPTS} attempts: {last}")
    return None


def _load_script(root: Path):
    """Import the skill's script by path, the way a harness would run it.

    The module must be registered in `sys.modules` before it executes, or the
    dataclass at the top of `feedback.py` raises at definition time: dataclasses
    resolves annotations through `sys.modules[cls.__module__]`, which is None
    for a module created but never registered.

    That line was missing here, so the benchmark command could not reach the
    first case — which is the real reason the published number went unrefreshed
    while the rubric changed three times underneath it. The tests' own loader in
    `tests/conftest.py` has always had it, and carries the same comment; two
    copies of one loader, and the copy nothing ran is the one that rotted.
    """
    import importlib.util
    import sys

    name = "feedback_script"
    spec = importlib.util.spec_from_file_location(name, root / "scripts" / "feedback.py")
    if spec is None or spec.loader is None:
        raise RuntimeError(f"no feedback script under {root}")
    script = importlib.util.module_from_spec(spec)
    sys.modules[name] = script
    spec.loader.exec_module(script)
    return script


def run_suite(
    suite_path: Path,
    slot: str,
    profile_name: str = "cloud",
    judge_slot: str = "vlm.director",
    use_skill: bool = True,
    language: str = "en",
    lesson_intent: str = "",
    skill_root: Path | None = None,
) -> list[CaseOutcome]:
    """Run every case in a suite through one slot, judged by another.

    With use_skill false the model gets a bare request instead of the skill's
    prompt, which is the control arm of the with-skill comparison.

    `language` used to be hard-coded to English, in a product whose
    first language is Chinese and whose judges are Chinese. Nothing had ever been
    benchmarked in the language it ships in.

    `skill_root` separates two things the suite path used to answer at once:
    where the cases and their drawings live, and where the skill being measured
    lives. They are the same directory for the committed suite and cannot be for
    any other, because real children's drawings are never committed. Without it
    the only measurable drawings are the six invented ones.
    """
    import time

    from studio.core.env import load_dotenv
    from studio.core.images import to_data_uri
    from studio.providers import build_client
    from studio.core.slots import load_profile, resolve

    load_dotenv()
    profile = load_profile(profile_name)
    writer = build_client(resolve(slot, profile))
    judge = build_client(resolve(judge_slot, profile))
    root = suite_path.parent.parent
    script = _load_script(skill_root or root)
    label = slot if use_skill else slot + NO_SKILL_SUFFIX

    outcomes: list[CaseOutcome] = []
    for case in json.loads(suite_path.read_text(encoding="utf-8")):
        drawing = drawing_for(case["question"], root)
        if drawing is None:
            print(f"skip {case['id']}: no drawing on disk")
            continue
        entrance = entrance_for(case["question"])
        image = to_data_uri(drawing)
        settings = script.ClassSettings(entrance, language, lesson_intent)
        prompt = script.build_prompt(settings) if use_skill else BARE_PROMPT
        started = time.monotonic()
        result = _write_or_skip(writer, prompt, image, case["id"])
        if result is None:
            continue
        elapsed = time.monotonic() - started
        report = run_rubric(
            result.text,
            entrance=entrance,
            beat="opening",
            image_data_uri=image,
            client=judge,
            lesson_intent=lesson_intent,
        )
        outcomes.append(
            CaseOutcome(
                case["id"], label, result.text, report, elapsed, result.cost_usd,
                result.input_tokens + result.output_tokens,
            )
        )
    return outcomes


# Criterion B5: the model that writes a critique must not also grade it. These
# two names are the only place that separation is expressed, so they are
# constants rather than string literals typed twice, and a test asserts they
# differ — in the runner AND in every profile that resolves both.
WRITER_SLOT = "vlm.studio"
JUDGE_SLOT = "vlm.director"

# Development may use a hosted substitute. Compare the resolved writer with
# the Spark plan, without treating either profile name as hardware evidence.
DEFAULT_PROFILE = "local"
SPARK_PROFILE = "spark"


def _provenance(arguments) -> str:
    """One line naming the models a number came from, and the language."""
    from studio.core.slots import load_profile, resolve

    try:
        profile = load_profile(arguments.profile)
        writer = resolve(arguments.slot, profile)
        judge = resolve(arguments.judge, profile)
    except Exception:
        return ""
    try:
        target = resolve(WRITER_SLOT, load_profile(SPARK_PROFILE))
        relation = "matches" if writer.model == target.model else "differs from"
        comparison = f"{relation} configured Spark target `{target.model}`"
    except Exception:
        comparison = "configured Spark target unavailable"
    return (
        f"Profile `{arguments.profile}`, language `{arguments.lang}`. "
        f"Written by `{writer.model}` via `{writer.provider}`; "
        f"{comparison} (hardware not verified). "
        f"Graded by `{judge.model}` via `{judge.provider}`."
    )


def argument_parser():
    """The benchmark's command line, lifted out of main() so it can be tested.

    Both --slot and --judge used to default to vlm.director, so the
    default run had one model writing and grading its own work. Every number in
    BENCHMARK.md came from that arrangement.
    """
    parser = argparse.ArgumentParser(description="Measure a skill with and without itself")
    parser.add_argument("--skill", default="art-feedback")
    parser.add_argument("--slot", default=WRITER_SLOT)
    parser.add_argument("--judge", default=JUDGE_SLOT)
    parser.add_argument("--profile", default=DEFAULT_PROFILE)
    parser.add_argument("--lang", default="en", choices=["en", "zh"])
    parser.add_argument("--lesson", default="", help="a lesson intent, so rule 11 is measured too")
    parser.add_argument("--skill-only", action="store_true", help="skip the bare-model arm")
    parser.add_argument("--no-write", action="store_true", help="print, do not touch BENCHMARK.md")
    parser.add_argument(
        "--suite",
        default=None,
        help="a cases file elsewhere, for drawings that may not be committed",
    )
    return parser


def main(argv: list[str] | None = None) -> None:
    """Re-run the benchmark and write it where the skill keeps it.

    There was no command. The only recorded way to regenerate a published number
    was a snippet typed by hand inside a plan document, which is how the
    published number came to be measured against a rubric that had since changed
    three times.

        uv run --env-file .env python -m evalkit.runner
        uv run --env-file .env python -m evalkit.runner --lang zh --no-write
    """
    parser = argument_parser()
    arguments = parser.parse_args(argv)

    skill_dir = Path("skills") / arguments.skill
    suite = Path(arguments.suite) if arguments.suite else skill_dir / "evals" / "evals.json"
    outcomes = run_suite(
        suite, arguments.slot, arguments.profile, arguments.judge,
        use_skill=True, language=arguments.lang, lesson_intent=arguments.lesson,
        skill_root=skill_dir,
    )
    if not arguments.skill_only:
        outcomes += run_suite(
            suite, arguments.slot, arguments.profile, arguments.judge,
            use_skill=False, language=arguments.lang, lesson_intent=arguments.lesson,
            skill_root=skill_dir,
        )
    summary = summarise(outcomes)
    page = render_benchmark(summary, _provenance(arguments))
    crossed = red_line_failures(outcomes)
    if crossed:
        page += "\n## Red lines crossed\n\n"
        page += "\n".join(f"- `{label}`: {count} case(s)" for label, count in crossed.items())
        page += "\n\nA red line refuses on its own, whatever the average says.\n"
    print(page)
    publishable = arguments.lang == "en" and arguments.suite is None
    if not arguments.no_write and publishable:
        target = skill_dir / "BENCHMARK.md"
        target.write_text(page, encoding="utf-8")
        print(f"\nwritten to {target}")
    elif not arguments.no_write:
        print("\nnot written: BENCHMARK.md holds the English run of the committed suite, "
              "which is the published one")


if __name__ == "__main__":
    main()
