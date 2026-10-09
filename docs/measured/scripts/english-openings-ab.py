"""Writer-only A/B: does a lesson line make a Chinese opening begin in English?

Calls the art-feedback skill's own write_feedback, exactly as a first attempt does, with the
vlm.studio client from a real stepfun class. No judges. Conditions are interleaved within
each repetition so drift over time hits all of them equally. One JSON line per call; a call
that fails five times is printed and left out, and a rerun fills it in.
Written up in docs/measured/english-openings-in-chinese-classes.md.

Usage, from the repository root:
    PYTHONPATH=. .venv/bin/python <this> OUT.jsonl [reps]
ONLY=103,monster limits the drawings, CONDITIONS=blank,subject the lesson lines, CLASS_LANG=en
the class language. VARIANT=chinese_openers or language_last rewrites the prompt in memory the
way each candidate fix did; both only mean anything against the prompts as they were before
the fix landed (check out its parent), since the fixed prompt already names the openers. The
colour drawings live in Image Sample/, which never leaves this machine; running them sends
them to StepFun.
"""
import json
import os
import re
import sys
import time
from pathlib import Path

from studio.classroom import Classroom
from studio.conversation import _load_skill
from studio.deployments import restore_selection
from studio.env import load_dotenv
from studio.errors import ModelError
from studio.portfolio import Portfolio

HERE = Path(__file__).parent
out = Path(sys.argv[1])
reps = int(sys.argv[2]) if len(sys.argv) > 2 else 5
colour = json.loads((HERE / "lesson-lines.json").read_text(encoding="utf-8"))
fixtures = json.loads((HERE / "fixture-lines.json").read_text(encoding="utf-8"))
TECHNIQUE = {"colour": colour["technique"], "sketch": fixtures["technique_sketch"]}

cases = [("colour", n, Path("Image Sample/Color Artwork") / f"Weixin Image_20260903223101_{n}_645.jpg", line)
         for n, line in colour["drawings"]]
cases += [("sketch", key, Path(fixtures["folder"]) / file, line)
          for key, file, line in fixtures["drawings"] if key in ("cat-shaded", "monster", "sphere-study")]
only = [n for n in os.environ.get("ONLY", "").split(",") if n]
cases = [case for case in cases if not only or case[1] in only]

load_dotenv()
feedback = _load_skill("feedback_skill", "skills/art-feedback/scripts/feedback.py")

# A candidate fix is tried by rewriting the prompt in memory, never by editing the skill's files.
VARIANT = os.environ.get("VARIANT", "none")
LANG = os.environ.get("CLASS_LANG", "zh")
SWAP = json.loads((HERE / "english-openings-variants.json").read_text(encoding="utf-8"))
real_build_prompt = feedback.build_prompt


def variant_build_prompt(settings):
    prompt = real_build_prompt(settings)
    if VARIANT in ("language_last", "both"):
        prompt += f"\n\nReply in {settings.language_name} and in nothing else."
    if VARIANT in ("chinese_openers", "both"):
        assert SWAP["openers_from"] in prompt, "the opener instruction moved; the variant would test nothing"
        assert SWAP["openers_to"] not in prompt, "this prompt already names the openers: check out the parent commit"
        prompt = prompt.replace(SWAP["openers_from"], SWAP["openers_to"])
    return prompt


feedback.build_prompt = variant_build_prompt
scratch = out.parent / (out.stem + "-class")
scratch.mkdir(parents=True, exist_ok=True)
room = Classroom(scratch / "ledger.jsonl", profile="stepfun", portfolio=Portfolio(scratch / "portfolio.sqlite3"))
restore_selection(room, scratch / "deployment.json", "stepfun")
sid = room.begin({"language": "zh", "entrance": "colour"})
writer = room._session_runtime(room.sessions[sid]).clients["vlm.studio"]
done = set()
if out.exists():
    for row in out.read_text(encoding="utf-8").splitlines():
        r = json.loads(row)
        if r.get("text"):
            done.add((r["rep"], r["drawing"], r["entrance"], r["condition"]))
try:
    with out.open("a", encoding="utf-8") as sink:
        for rep in range(1, reps + 1):
            for entrance, drawing, image, subject in cases:
                for condition, line in (("blank", ""), ("subject", subject), ("technique", TECHNIQUE[entrance])):
                    if condition not in os.environ.get("CONDITIONS", "blank,subject,technique").split(","):
                        continue
                    if (rep, drawing, entrance, condition) in done:
                        continue
                    settings = feedback.ClassSettings(entrance, LANG, line)
                    text, error = None, ""
                    for wait in (0, 20, 40, 60, 90):  # a rate limit, empty or dropped reply is not a sample
                        time.sleep(wait)
                        try:
                            text = feedback.write_feedback(str(image), settings, writer)
                            break
                        except ModelError as failure:
                            error = str(failure)
                    if not text:
                        print(rep, entrance, drawing, condition, "ERR", error[:80], flush=True)
                        continue
                    row = {"variant": VARIANT, "language": LANG, "rep": rep, "entrance": entrance,
                           "drawing": drawing, "condition": condition, "line": line, "text": text,
                           "english_start": bool(re.match(r"\s*[A-Za-z]", text))}
                    sink.write(json.dumps(row, ensure_ascii=False) + "\n")
                    sink.flush()
                    print(rep, entrance, drawing, condition, "EN" if row["english_start"] else "zh", flush=True)
finally:
    room.end(sid)
print("AB-DONE", flush=True)
