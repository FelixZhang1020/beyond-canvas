"""Probe the naming judge (rubric rule 4) directly, three runs per case.

Each case is one sentence of feedback on one drawing, with or without the teacher's
lesson line and what the child said. The judge client is taken from a real stepfun
class, so it is the checker the classroom uses. Written up in
docs/measured/lesson-line-and-naming-check.md.

Usage, from the repository root:
    PYTHONPATH=. .venv/bin/python <this> OUT_DIR
The drawings live in Image Sample/, which never leaves this machine; running this
sends them to StepFun.
"""
import json
import sys
from pathlib import Path

from evalkit.rubric.assisted import rule_4_non_presumptive
from studio.classroom import Classroom
from studio.deployments import restore_selection
from studio.env import load_dotenv
from studio.errors import ModelUnavailable
from studio.images import to_data_uri
from studio.portfolio import Portfolio

out = Path(sys.argv[1])
out.mkdir(parents=True, exist_ok=True)
cases = json.loads((Path(__file__).parent / "naming-probe-cases.json").read_text(encoding="utf-8"))
load_dotenv()
room = Classroom(out / "ledger.jsonl", profile="stepfun", portfolio=Portfolio(out / "portfolio.sqlite3"))
restore_selection(room, out / "deployment.json", "stepfun")
sid = room.begin({"language": "zh", "entrance": "colour"})
judge = room._session_runtime(room.sessions[sid]).clients["vlm.director"]
results = []
try:
    for case in cases:
        image = to_data_uri(Path("Image Sample/Color Artwork") / case["file"])
        for attempt in range(3):
            for _ in range(3):  # a dropped connection is not a verdict
                try:
                    result = rule_4_non_presumptive(case["feedback"], image, judge, lesson_intent=case["lesson"],
                                                    child_said=case.get("child_said", ""))
                    break
                except ModelUnavailable as error:
                    print("retrying after", error, flush=True)
            else:
                continue
            results.append({"case": case["name"], "attempt": attempt + 1, "status": result.status,
                            "evidence": result.evidence})
            print(case["name"], attempt + 1, result.status, result.evidence, flush=True)
finally:
    room.end(sid)
(out / "naming_probe.json").write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
