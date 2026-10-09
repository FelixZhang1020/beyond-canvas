"""Can rule 12 still refuse, with the judge in place? Three live runs per question.

Two of the four cases are refused by the marker list before the judge is consulted, so the
summary counts the judge's own record separately: only a verdict whose evidence says "judged"
was the judge's. Written up in docs/measured/rule-12-questions.md.

Usage, from the repository root: PYTHONPATH=. .venv/bin/python <this> OUT.json
"""
import json
import sys
from pathlib import Path

from evalkit.rubric.loop import rule_12_question_enters_the_process, rule_12_question_enters_the_world
from studio.classroom import Classroom
from studio.deployments import restore_selection
from studio.env import load_dotenv
from studio.portfolio import Portfolio

HERE = Path(__file__).parent
out = Path(sys.argv[1])
cases = json.loads((HERE / "rule-12-negatives.json").read_text(encoding="utf-8"))
load_dotenv()
room = Classroom(out.parent / "r12n-ledger.jsonl", profile="stepfun",
                 portfolio=Portfolio(out.parent / "r12n-portfolio.sqlite3"))
restore_selection(room, out.parent / "r12n-deployment.json", "stepfun")
sid = room.begin({"language": "zh", "entrance": "colour"})
judge = room._session_runtime(room.sessions[sid]).clients["vlm.director"]
rules = {"colour": rule_12_question_enters_the_world, "sketch": rule_12_question_enters_the_process}
results = []
try:
    for case in cases:
        for attempt in range(3):
            # rule_12_* swallows a model error and lets the markers decide, so a verdict here is
            # never an outage — but it may be the markers' rather than the judge's, and only a
            # judged verdict carries ", judged:" in its evidence.
            result = rules[case["entrance"]](case["question"], client=judge)
            judged = ", judged:" in result.evidence
            results.append({**case, "attempt": attempt + 1, "status": result.status,
                            "judged": judged, "evidence": result.evidence})
            print(case["entrance"], attempt + 1, result.status,
                  "(judge)" if judged else "(markers alone)", case["question"], flush=True)
finally:
    room.end(sid)
out.write_text(json.dumps(results, ensure_ascii=False, indent=1), encoding="utf-8")
reached = [r for r in results if r["judged"]]
print("refused", sum(r["status"] == "fail" for r in results), "of", len(results),
      "| of the ones the judge saw:", sum(r["status"] == "fail" for r in reached), "of", len(reached),
      flush=True)
