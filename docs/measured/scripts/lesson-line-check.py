"""Live check: does a lesson line get the opening refused, drawing by drawing?

Runs the real Classroom on the stepfun deployment, one class per drawing and
condition, and records every attempt the opening gate judged. Nothing in the
harness is changed; run_rubric is wrapped only to keep a copy of each report.
Written up in docs/measured/lesson-line-and-naming-check.md.

Usage, from the repository root:
    PYTHONPATH=. .venv/bin/python <this> OUT_DIR [condition ...]
Conditions: blank, subject, technique; a trailing digit repeats one ("subject2").
LESSON_LINES names the input file beside this script (default the six colour
drawings; fixture-lines.json for the eval fixtures), ENTRANCE picks
colour or sketch, and ONLY=120,75 limits the drawings. The six colour drawings
live in Image Sample/, which never leaves this machine; running them sends them
to StepFun.
"""
import json
import os
import sys
import time
from pathlib import Path

import studio.gates as gates
from studio.classroom import Classroom
from studio.deployments import restore_selection
from studio.env import load_dotenv
from studio.portfolio import Portfolio

HERE = Path(__file__).parent
LINES = json.loads((HERE / os.environ.get("LESSON_LINES", "lesson-lines.json")).read_text(encoding="utf-8"))
SAMPLES = Path(LINES.get("folder", "Image Sample/Color Artwork"))
ENTRANCE = os.environ.get("ENTRANCE", "colour")

out = Path(sys.argv[1])
conditions = sys.argv[2:] or ["blank", "subject"]
out.mkdir(parents=True, exist_ok=True)
load_dotenv()

attempts = []
real_run_rubric = gates.run_rubric


def recording_run_rubric(text, **kwargs):
    report = real_run_rubric(text, **kwargs)
    attempts.append({
        "text": text,
        "results": [{"rule": r.rule, "status": r.status, "evidence": r.evidence} for r in report.results],
    })
    return report


gates.run_rubric = recording_run_rubric

room = Classroom(out / "ledger.jsonl", profile="stepfun", portfolio=Portfolio(out / "portfolio.sqlite3"))
restore_selection(room, out / "deployment.json", "stepfun")

only = [n for n in os.environ.get("ONLY", "").split(",") if n]
for entry in LINES["drawings"]:
    number, subject = entry[0], entry[-1]
    if only and number not in only:
        continue
    fixture = len(entry) == 3
    image = SAMPLES / (entry[1] if fixture else f"Weixin Image_20260903223101_{number}_645.jpg")
    for condition in conditions:
        target = out / (f"{number}-{ENTRANCE}-{condition}.json" if fixture else f"{number}-{condition}.json")
        if target.exists():
            continue
        # "subject2" is a repeat of "subject": the judges are models, so one run is one sample.
        line = {"blank": "", "subject": subject, "technique": LINES["technique"]}[condition.rstrip("0123456789")]
        attempts.clear()
        started = time.monotonic()
        sid = room.begin({"language": "zh", "entrance": ENTRANCE, "lesson_intent": line})
        try:
            did = room.add_drawing(sid, image.read_bytes())
            rid = room.request(sid, "art-feedback", [did], {})["request_id"]
            room.run_request(rid)
            stream = list(room.follow(rid))
            ledger = room.ledger_lines(sid)
        finally:
            room.end(sid)
        done = [data for name, data in stream if name == "done"]
        final = done[-1] if done else {}
        record = {
            "drawing": number, "entrance": ENTRANCE, "condition": condition, "lesson_line": line,
            "elapsed_s": round(time.monotonic() - started, 1),
            "final": final, "attempts": list(attempts),
            "ledger": [{key: row.get(key) for key in ("stage", "gate", "note")} for row in ledger],
        }
        target.write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8")
        failed = [[r["rule"] for r in a["results"] if r["status"] == "fail"] for a in attempts]
        print(number, ENTRANCE, condition, final.get("status", "shown"), final.get("reason_code", ""),
              "failed per attempt:", failed, f"{record['elapsed_s']}s", flush=True)
