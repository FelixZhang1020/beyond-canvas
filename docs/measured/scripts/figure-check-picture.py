"""Judge 3D figures with the check's own picture and with the card's picture, several times each.

The check is studio/making/figure.py's look(), with the class's own vlm.figure.look client (Step 3.7 Flash on the
StepFun plan), and the safety screen is the class's own (safety.image with NVIDIA's reader, point "out"). Only the
picture they are shown differs: "flat", the paint shading of figure_render.sheet the class shows them today, or
"card", the same two views and layout drawn by figure_card.picture, lit as the class page's viewer lights the
figure. Nothing the class runs is changed; the swap is made inside this process only.
Written up in docs/measured/figure-check-picture.md.

Usage, on the Spark, from the repository root:
    sh deploy/spark/test-on-spark.sh python docs/measured/scripts/figure-check-picture.py saved [LOOKS]
    sh deploy/spark/test-on-spark.sh python docs/measured/scripts/figure-check-picture.py fresh [LOOKS]
A third number takes only that many figures, to try the script before a full run.
saved: the Portfolio's saved figures, each of which passed the flat check twice when it was made.
fresh: one new figure from each of their paintings, by the class's own vlm.figure writer, kept nowhere.
Every result is printed as one JSON line the moment it is known. The Portfolio is only read; the paintings are
sample drawings and go to StepFun as in a class.
"""
import base64
import io
import json
import random
import sqlite3
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from PIL import Image

from studio.conversation.conversation import _load_skill, _screen_gate
from studio.core.deployments import build_runtime
from studio.core.env import load_dotenv
from studio.core.images import to_data_uri
from studio.making import figure
from studio.making.figure_card import picture
from studio.making.figure_render import sheet as flat_sheet

PORTFOLIO = Path.home() / "beyond-canvas/.studio/portfolio.sqlite3"
SEEN = threading.local()   # which picture this thread's check is shown


def card_sheet(fig):
    """figure_render.sheet's two views in its layout, drawn as the viewer lights the figure."""
    both = Image.new("RGB", (960, 360))
    both.paste(picture(fig, 0, 480, 360), (0, 0))
    both.paste(picture(fig, 35, 480, 360), (480, 0))
    buffer = io.BytesIO()
    both.save(buffer, format="PNG")
    return "data:image/png;base64," + base64.b64encode(buffer.getvalue()).decode()


SHEETS = {"flat": flat_sheet, "card": card_sheet}
figure.sheet = lambda fig: SHEETS[SEEN.picture](fig)   # look() reads this module name when it is called


class Heard:
    """The class's own client, keeping the check's answer so its reasons can be read."""

    def __init__(self, client):
        self.client, self.text = client, ""

    def chat(self, *args, **kwargs):
        reply = self.client.chat(*args, **kwargs)
        self.text = reply.text
        return reply


def look(case, seen, run, looker):
    SEEN.picture, heard, started = seen, Heard(looker), time.time()
    row = {"kind": "look", "case": case["name"], "picture": seen, "run": run}
    try:
        passed, fix = figure.look(case["painting"], case["figure"], heard)
    except Exception as error:   # an outage is recorded, never counted as a verdict
        return {**row, "error": f"{type(error).__name__}: {error}"[:200]}
    return {**row, "passed": passed, "fix": fix, "answer": heard.text.strip()[-500:],
            "seconds": round(time.time() - started, 1)}


def screen(case, seen, safety, screener):
    row = {"kind": "screen", "case": case["name"], "picture": seen}
    try:
        verdict = safety.screen(SHEETS[seen](case["figure"]), screener, second=getattr(screener, "second", None),
                                point="out")
    except Exception as error:
        return {**row, "error": f"{type(error).__name__}: {error}"[:200]}
    # As Conversation.figure gates it: the studio drew this toy, so "block" (not artwork) does not hold it back.
    return {**row, "passes": _screen_gate(verdict)[0] or verdict.verdict == "block", "verdict": verdict.verdict,
            "second_look": getattr(verdict, "second_look", "")}


def saved_cases(db):
    cases = []
    for aid, output, drawings in db.execute("select id, output, drawings from activities "
                                            "where json_extract(output, '$.figure') is not null order by created_at"):
        did = json.loads(drawings)[0]
        cases.append({"name": aid, "drawing": did, "figure": json.loads(output)["figure"]})
    return cases


def painting(db, did):
    return to_data_uri(io.BytesIO(db.execute("select image from artwork where id=?", (did,)).fetchone()[0]))


def write(did, source, writer):
    """One writing, as figure.make's first: the class's prompt and writer, then parse and settle."""
    try:
        reply = writer.chat(figure._prompt("figure.txt"), [source], max_tokens=figure.WRITE_TOKENS,
                            system=figure.WRITE_SYSTEM)
        return {"name": "fresh-" + did, "drawing": did, "figure": figure.settle(figure.parse(reply.text))}
    except Exception as error:
        print(json.dumps({"kind": "write", "drawing": did, "error": f"{type(error).__name__}: {error}"[:200]}),
              flush=True)
        return None


def main():
    mode, looks = sys.argv[1], int(sys.argv[2]) if len(sys.argv) > 2 else 3
    limit = int(sys.argv[3]) if len(sys.argv) > 3 else None
    load_dotenv()
    runtime = build_runtime("stepfun")
    clients = runtime.clients
    looker = clients.get("vlm.figure.look") or clients.get("vlm.figure") or clients["vlm.creation"]
    screener, safety = clients["safety.image"], _load_skill("safety_skill", "skills/studio-safety/scripts/safety.py")
    db = sqlite3.connect(f"file:{PORTFOLIO}?mode=ro", uri=True, check_same_thread=False)
    cases, paintings = saved_cases(db)[:limit], {}
    for case in cases:
        paintings.setdefault(case["drawing"], painting(db, case["drawing"]))
    with ThreadPoolExecutor(max_workers=4) as pool:
        if mode == "fresh":
            writer = clients.get("vlm.figure") or clients["vlm.creation"]
            made = pool.map(lambda did: write(did, paintings[did], writer), sorted(paintings))
            cases = [case for case in made if case]
            for case in cases:
                print(json.dumps({"kind": "figure", "case": case["name"], "figure": case["figure"]}), flush=True)
        for case in cases:
            case["painting"] = paintings[case["drawing"]]
        jobs = [(look, case, seen, run, looker) for case in cases for seen in SHEETS for run in range(looks)]
        jobs += [(screen, case, seen, safety, screener) for case in cases for seen in SHEETS]
        random.Random(7).shuffle(jobs)   # both pictures spread over the whole run, so time of day favours neither
        print(json.dumps({"kind": "start", "mode": mode, "cases": len(cases), "paintings": len(paintings),
                          "jobs": len(jobs)}), flush=True)
        for done in as_completed([pool.submit(job[0], *job[1:]) for job in jobs]):
            print(json.dumps(done.result(), ensure_ascii=False), flush=True)


if __name__ == "__main__":
    main()
