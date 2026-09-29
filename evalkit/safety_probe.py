"""Show NVIDIA's safety model the generated test drawings on the Spark and write down what it said.

The question this answers is the one the tests cannot: does Nemotron 3.5 Content Safety, given the
children's-studio policy, let a child's monster in? Each picture is shown with the model's stock
policy and with ours, several times, and every answer goes through studio-safety's own reader and
rule (`skills/studio-safety/scripts/nemotron.py`), so what is measured is what the studio would do.

Runs inside the container on the node, where torch and transformers live; nothing here is imported
by the studio. Only generated fixtures are ever shown to it: the hosted Spark must never see a real
child's drawing. It cannot show that the model catches harmful pictures; no such set is held.

Weights are read whole, never memory-mapped: on the GB10 a memory-mapped load measured about fifty
times slower (the FLUX bring-up).

usage: python evalkit/safety_probe.py MODEL_DIR PICTURE [PICTURE ...] [--runs 3] [--out probe.json] [--policy FILE]
`--policy` tries another wording of our policy, a plain text file, before it replaces the skill's own.
"""
import argparse
import importlib.util
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))


def studio_rule():
    path = ROOT / "skills" / "studio-safety" / "scripts" / "nemotron.py"
    spec = importlib.util.spec_from_file_location("nemotron_script", path)
    module = importlib.util.module_from_spec(spec)
    sys.modules["nemotron_script"] = module
    spec.loader.exec_module(module)
    return module


def reader():
    """The skill's own server script: the one copy of how the model is loaded and asked."""
    path = ROOT / "skills" / "studio-safety" / "scripts" / "nemotron_server.py"
    spec = importlib.util.spec_from_file_location("nemotron_server_script", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def ask(served, model, processor, picture: Path, question: str, policy: str | None) -> tuple[str, float]:
    from PIL import Image

    started = time.monotonic()
    reply = served.ask(model, processor, Image.open(picture), question, policy)
    return reply, round(time.monotonic() - started, 1)


def one_look(rule, reply: str) -> dict:
    try:
        reading = rule.read_answer(reply)
    except Exception as error:      # an unreadable answer is a result worth writing down, not a crash
        return {"read": False, "why": str(error)[:160]}
    ruling = rule.at_the_door(reading)
    return {"read": True, "unsafe": reading.unsafe, "categories": list(reading.categories),
            "comes_in": ruling.proceeds, "answered_warmly": ruling.soften}


def main(argv: list[str]) -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("model_dir", type=Path)
    parser.add_argument("pictures", nargs="+", type=Path)
    parser.add_argument("--runs", type=int, default=3)
    parser.add_argument("--out", type=Path, default=Path("probe.json"))
    parser.add_argument("--policy", type=Path, help="a trial wording, instead of the skill's own policy")
    args = parser.parse_args(argv)
    rule, served = studio_rule(), reader()
    started = time.monotonic()
    model, processor = served.load(args.model_dir)
    rows, loaded = [], round(time.monotonic() - started, 1)
    for picture in args.pictures:
        ours = args.policy.read_text(encoding="utf-8").strip() if args.policy else rule.inference_policy()
        for mode, policy in (("stock", None), ("studio", ours)):
            for run in range(args.runs):
                reply, seconds = ask(served, model, processor, picture, rule.QUESTIONS["door"], policy)
                rows.append({"picture": picture.name, "policy": mode, "run": run + 1, "seconds": seconds,
                             "answer": reply[-300:], **one_look(rule, reply)})
                print("PROBE", picture.name, mode, run + 1, f"{seconds}s", json.dumps(rows[-1]["answer"][-80:]),
                      "comes in" if rows[-1].get("comes_in") else "STOPPED or unread", flush=True)
    args.out.write_text(json.dumps({"model": args.model_dir.name, "load_seconds": loaded, "looks": rows}, indent=1))
    turned_away = [r for r in rows if not r.get("comes_in")]
    print(f"PROBE done: {len(rows)} looks, {len(turned_away)} turned away or unread, loaded in {loaded}s, wrote {args.out}")


if __name__ == "__main__":
    main(sys.argv[1:])
