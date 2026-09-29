"""Put real closing questions through rule 12 twice: markers alone, then markers plus judge.

Builds its corpus from the run files an earlier sweep wrote (lesson-line-check.py),
so every question is one a real model wrote in a real class. The judge client is the one a
class uses. Written up in docs/measured/rule-12-questions.md.

Usage, from the repository root:
    PYTHONPATH=. .venv/bin/python <this> OUT.json RUN_DIR [RUN_DIR ...]
A question that no marker recognises costs one judge call; the rest cost nothing.
"""
import glob
import json
import sys
from collections import Counter
from pathlib import Path

from evalkit.rubric.loop import _questions, rule_12_question_enters_the_process
from evalkit.rubric.loop import rule_12_question_enters_the_world
from studio.classroom import Classroom
from studio.deployments import restore_selection
from studio.env import load_dotenv
from studio.errors import ModelError
from studio.portfolio import Portfolio

out = Path(sys.argv[1])
seen, questions = set(), []
for folder in sys.argv[2:]:
    for path in sorted(glob.glob(str(Path(folder) / "*.json"))):
        if path.endswith("deployment.json"):
            continue
        record = json.loads(Path(path).read_text(encoding="utf-8"))
        entrance = record.get("entrance") or ("sketch" if "sketch" in path else "colour")
        for attempt in record["attempts"]:
            graded = next((r for r in attempt["results"] if r["rule"] == 12), None)
            if not graded or graded["status"] == "skip":
                continue
            asked = _questions(attempt["text"])
            question = asked[-1].strip() if asked else ""
            if question and (entrance, question) not in seen:
                seen.add((entrance, question))
                questions.append({"entrance": entrance, "question": question,
                                  "drawing": record["drawing"], "shipped": graded["status"]})

load_dotenv()
room = Classroom(out.parent / "rule12-ledger.jsonl", profile="stepfun",
                 portfolio=Portfolio(out.parent / "rule12-portfolio.sqlite3"))
restore_selection(room, out.parent / "rule12-deployment.json", "stepfun")
session = room.begin({"language": "zh", "entrance": "colour"})
judge = room._session_runtime(room.sessions[session]).clients["vlm.director"]
rules = {"colour": rule_12_question_enters_the_world, "sketch": rule_12_question_enters_the_process}
results, tally = [], Counter()
try:
    for row in questions:
        rule = rules[row["entrance"]]
        markers = rule(row["question"]).status
        judged = markers
        if markers == "fail":
            for _ in range(3):  # a dropped connection is not a verdict
                try:
                    judged = rule(row["question"], client=judge).status
                    break
                except ModelError as error:
                    print("retrying after", error, flush=True)
        results.append({**row, "markers": markers, "with_judge": judged})
        tally[(row["entrance"], markers, judged)] += 1
        if markers != judged:
            print(row["entrance"], markers, "->", judged, row["question"], flush=True)
finally:
    room.end(session)
out.write_text(json.dumps(results, ensure_ascii=False, indent=1), encoding="utf-8")
print("\nquestions", len(results))
for key, count in sorted(tally.items()):
    print(" ", key[0], "markers", key[1], "with judge", key[2], ":", count)
