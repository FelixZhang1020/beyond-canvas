"""The agent's eyes: does this picture show what it was meant to show?

One vision call with a fixed prompt, separate from whatever produced the picture, so the check
does not share the actor's reasoning. The answer is a small JSON verdict; an answer that cannot be
read is a fail that says so, never a silent pass.
Usage: uv run python skills/shot-judge/scripts/judge.py --image shot.png --meant "the corner bracket set"
           [--profile api] [--slot vlm.studio] [--out verdict.json]
"""
from __future__ import annotations

import argparse
import json
import re
from dataclasses import asdict, dataclass
from pathlib import Path

PROMPT = Path(__file__).resolve().parents[1] / "assets/prompts/judge.txt"
SYSTEM = "You judge rendered pictures for an agent. Return only the requested JSON."
# Step 3.7 Flash bills its hidden thinking as completion tokens; under 1000 it returns nothing,
# and on a busy picture it can think past 1500. Low effort and a wide ceiling keep the verdict.
MAX_TOKENS = 4000
REASONING_EFFORT = "low"
JSON_BLOCK = re.compile(r"\{.*\}", re.DOTALL)
FLAGS = ("visible", "centred", "readable")


@dataclass(frozen=True)
class Verdict:
    seen: str
    visible: bool
    centred: bool
    readable: bool
    verdict: str
    change: str
    parsed: bool
    tokens: int = 0
    latency_s: float = 0.0


def parse_verdict(text: str) -> dict:
    """The JSON object inside the model's answer, or {} when there is none."""
    match = JSON_BLOCK.search(text)
    if not match:
        return {}
    try:
        data = json.loads(match.group(0))
    except json.JSONDecodeError:
        return {}
    return data if isinstance(data, dict) else {}


def settle(data: dict) -> dict:
    """A verdict passes only when the three flags are true, whatever the model wrote."""
    flags = {k: bool(data.get(k, False)) for k in FLAGS}
    verdict = "pass" if all(flags.values()) else "fail"
    return {"seen": str(data.get("seen", "")), **flags, "verdict": verdict,
            "change": str(data.get("change", "")) if verdict == "fail" else ""}


def judge(image: Path, meant: str, client) -> Verdict:
    from studio.core.errors import EmptyCompletion
    from studio.core.images import to_data_uri

    prompt = PROMPT.read_text(encoding="utf-8").replace("{meant}", meant)
    shown = [to_data_uri(image, max_edge=1024)]
    try:
        reply = client.chat(prompt, shown, system=SYSTEM, max_tokens=MAX_TOKENS)
    except EmptyCompletion:      # the whole budget went on hidden thinking: once more, with twice the room
        reply = client.chat(prompt, shown, system=SYSTEM, max_tokens=2 * MAX_TOKENS)
    data = parse_verdict(reply.text)
    tokens = reply.input_tokens + reply.output_tokens
    if not data:
        return Verdict(seen=reply.text.strip()[:200], visible=False, centred=False, readable=False,
                       verdict="fail", change="the judge could not read its own answer; try once more",
                       parsed=False, tokens=tokens, latency_s=reply.latency_s)
    return Verdict(**settle(data), parsed=True, tokens=tokens, latency_s=reply.latency_s)


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Judge whether a rendered shot shows what it was meant to.")
    parser.add_argument("--image", required=True, type=Path)
    parser.add_argument("--meant", required=True, help="what the shot was meant to show, in plain words")
    parser.add_argument("--profile", default="stepfun")  # api until its archive
    parser.add_argument("--slot", default="vlm.studio")
    parser.add_argument("--out", type=Path, default=None)
    args = parser.parse_args(argv)
    from studio.core.env import load_dotenv
    from studio.providers import build_client
    from studio.core.slots import load_profile, resolve

    load_dotenv()
    config = resolve(args.slot, load_profile(args.profile))
    config.options.setdefault("reasoning_effort", REASONING_EFFORT)
    client = build_client(config)
    verdict = asdict(judge(args.image, args.meant, client))
    text = json.dumps(verdict, ensure_ascii=False, indent=1)
    if args.out:
        args.out.write_text(text, encoding="utf-8")
    print(text)


if __name__ == "__main__":
    main()
