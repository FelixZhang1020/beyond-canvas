"""Can a model pick the right skill from the descriptions alone?

The harness diagram's top row assumes it can: the model reads every Skill's
description and chooses. Nothing else in this system tests that directly. The
studio dispatches by explicit Python; the temple's builder is shown the same
kind of index every turn, built from the same descriptions, and chooses from
it, but among fewer skills and inside a long run, where a wrong pick is hard
to see.

The test set already existed and nobody was running it. Every eval case in
every skill names the skill that should handle it, so the cases together are
a dispatch benchmark as they stand. This runner shows a model every name and
description, asks one question, and compares its answer to the case's own
expected_skill. One call per case, no tool runs, no renders.

What it measures is the DESCRIPTIONS, so the instruction around them is kept
deliberately bare: a better prompt here would hide exactly the weakness worth
finding.

Usage: uv run python -m evalkit.dispatch [--profile stepfun] [--slot vlm.studio]
           [--only art-feedback] [--dry-run]
"""
from __future__ import annotations

import argparse
import json
import time
from collections import Counter
from pathlib import Path

from studio.showpiece import catalog

SKILLS = Path("skills")
PROFILE, SLOT = "stepfun", "vlm.studio"   # StepFun First, the one deployment
PAUSE_S = 7.0          # the StepFun key allows ten requests a minute
STOP_AFTER = 3         # errors in a row: a missing key or an empty account fails every case alike
# Step 3.7 Flash bills hidden thinking as completion tokens and reports reasoning_tokens as 0. A
# 1,000-token budget was the documented floor and it still came back empty on the sixth case, so
# these match the temple driver's own numbers: room to think, and a second try with twice as much.
MAX_TOKENS, RETRY_TOKENS = 6000, 12000


def every_skill(root: Path = SKILLS) -> list[str]:
    return sorted(d.name for d in root.iterdir() if (d / "SKILL.md").is_file())


def cases(root: Path = SKILLS, only: str | None = None) -> list[dict]:
    out = []
    for name in every_skill(root):
        if only and name != only:
            continue
        path = root / name / "evals" / "evals.json"
        if not path.is_file():
            continue
        for case in json.loads(path.read_text(encoding="utf-8")):
            out.append({"id": case["id"], "question": case["question"],
                        "expected": case["expected_skill"], "from": name})
    return out


def menu(skills: dict) -> str:
    return "\n\n".join(f"{s.name}: {s.description}" for s in skills.values())


def instruction(skills: dict) -> str:
    return ("You route a request to one skill. These are the skills available, each with the "
            "description its author wrote:\n\n" + menu(skills) +
            "\n\nAnswer with one JSON object and nothing else: {\"skill\": \"<exact name from the list>\"}")


def chosen(text: str) -> str | None:
    """The last JSON object in the answer that names a skill. A thinking model may write braces in
    its prose before the answer, so every opening brace is tried rather than one greedy match."""
    text, decoder, found, start = text or "", json.JSONDecoder(), None, 0
    while (start := text.find("{", start)) != -1:
        try:
            value, start = decoder.raw_decode(text, start)   # past the whole object: nested ones never count
        except json.JSONDecodeError:
            start += 1
            continue
        if isinstance(value, dict) and isinstance(value.get("skill"), str) and value["skill"].strip():
            found = value["skill"].strip()
    return found


def ask(client, system: str, question: str) -> tuple[str | None, int, str]:
    """One question: the pick, the tokens, and what the model said or why it said nothing. A case
    that cannot be answered is recorded as a miss with its reason, never fatal: a run of fifty is
    worth more with one hole in it than not at all."""
    from studio.core.errors import EmptyCompletion, ModelError

    for attempt, budget in enumerate((MAX_TOKENS, RETRY_TOKENS)):
        try:
            reply = client.chat(question, [], system=system, max_tokens=budget)
            return chosen(reply.text), reply.input_tokens + reply.output_tokens, reply.text[-300:]
        except EmptyCompletion:
            if attempt:
                return None, budget, "empty twice"
        except ModelError as error:
            if "429" not in str(error) or attempt:
                return None, 0, f"error: {str(error)[:200]}"
            time.sleep(PAUSE_S * 2)
    return None, 0, "no answer"


def run(client, system: str, todo: list[dict], pause: float = PAUSE_S) -> tuple[list[dict], int]:
    """Every case in turn. One error is one miss; STOP_AFTER in a row stop the run before a report is
    written, so a key that no longer works never writes "0 of 51" over the last good report."""
    rows, spent = [], 0
    for index, case in enumerate(todo, 1):
        picked, tokens, said = ask(client, system, case["question"])
        spent += tokens
        mark = "ok " if picked == case["expected"] else "NO "
        print(f"{mark}{index:2}/{len(todo)} {case['id']:28} wanted {case['expected']:22} chose {picked}")
        rows.append({**case, "picked": picked, "tokens": tokens, "said": said})
        if len(rows) >= STOP_AFTER and all(r["said"].startswith("error:") for r in rows[-STOP_AFTER:]):
            raise SystemExit(f"stopped: {STOP_AFTER} errors in a row, nothing written. Last: {said}")
        if index < len(todo):
            time.sleep(pause)
    return rows, spent


def report(rows: list[dict]) -> str:
    right = sum(1 for r in rows if r["picked"] == r["expected"])
    lines = [f"chose right: {right} of {len(rows)}", ""]
    by_skill = Counter(r["expected"] for r in rows)
    hit = Counter(r["expected"] for r in rows if r["picked"] == r["expected"])
    for name in sorted(by_skill):
        lines.append(f"  {name:24} {hit[name]}/{by_skill[name]}")
    missed = [r for r in rows if r["picked"] != r["expected"]]
    if missed:
        lines += ["", "went elsewhere:"]
        lines += [f"  {r['id']:28} wanted {r['expected']:22} chose {r['picked'] or '(unreadable)'}" for r in missed]
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Does the model pick the right skill from the descriptions?")
    parser.add_argument("--profile", default=PROFILE)
    parser.add_argument("--slot", default=SLOT)
    parser.add_argument("--only", default=None, help="one skill's cases")
    parser.add_argument("--dry-run", action="store_true", help="print what would be asked, call nothing")
    parser.add_argument("--out", type=Path, default=Path(".studio/dispatch-report.json"))
    args = parser.parse_args(argv)

    skills = catalog.load_skills(SKILLS, every_skill())
    todo = cases(only=args.only)
    system = instruction(skills)
    print(f"{len(skills)} skills on the menu, {len(todo)} cases to ask")

    if args.dry_run:
        print("\n--- the instruction the model sees ---\n")
        print(system[:1200] + ("\n... (cut)" if len(system) > 1200 else ""))
        print("\n--- the questions ---")
        for case in todo:
            print(f"  {case['id']:28} -> {case['expected']:22} {case['question'][:70]}")
        return

    from studio.core.env import load_dotenv
    from studio.providers import build_client
    from studio.core.slots import load_profile, resolve

    load_dotenv()
    config = resolve(args.slot, load_profile(args.profile))
    config.options.setdefault("reasoning_effort", "low")
    client = build_client(config)
    print(f"asking {config.model} via {config.provider}\n")

    rows, spent = run(client, system, todo)
    print("\n" + report(rows) + f"\n\ntokens: {spent:,}")
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps({"model": config.model, "provider": config.provider,
                                    "rows": rows, "tokens": spent}, ensure_ascii=False, indent=2),
                        encoding="utf-8")
    print(f"written to {args.out}")


if __name__ == "__main__":
    main()
