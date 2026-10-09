"""Run the 3D view check on saved TRELLIS.2 models whose right answer is known, several times each.

The three models are the 全素描样例 course's saved sketch 3D results on the Spark. Their right
angle was found by eye from twelve renders of each beside its drawing (30 degrees apart, at the
drawing's height), and is written below with how far off still counts as right. The check is
the one in studio/view_calibration.py of whichever checkout runs this, with the class's own
vlm.sketch slot, so a change to the check is measured by running this again from its copy.
Written up in docs/measured/view-calibration.md.

Usage, on the Spark, from the repository root:
    sh deploy/spark/test-on-spark.sh python docs/measured/scripts/view-calibration-trial.py [RUNS]
The Portfolio is only read. The drawings are sample drawings, and go to StepFun as in a class.
"""
import base64
import io
import json
import sqlite3
import sys
import tempfile
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from PIL import Image

from studio import view_calibration
from studio.env import load_dotenv
from studio.images import to_data_uri
from studio.providers import build_client
from studio.slots import load_profile

PORTFOLIO = Path.home() / "beyond-canvas/.studio/portfolio.sqlite3"
# activity, drawing, what it shows, right yaw, how far off still reads as the drawing
CASES = [("88185ce2f9fc", "c6388404e1c3", "apple in front of a pear", 30, 20),
         ("c6bcbf4265f9", "df7f65069067", "cube, sphere and cylinder", 180, 20),
         ("00b5d0d01bd9", "72414423232e", "plaster head, three-quarter left", 180, 20)]


def off_by(yaw, right):
    return abs((yaw - right + 180) % 360 - 180)


class Heard:
    """The class's own client, keeping what the check was told so a wrong pick can be read."""

    def __init__(self, client):
        self.client, self.replies = client, []

    def chat(self, *args, **kwargs):
        reply = self.client.chat(*args, **kwargs)
        self.replies.append(reply.text[:800])
        return reply


def one(case, run, client, db):
    client = Heard(client)
    activity, drawing, label, right, slack = case
    scene = json.loads(db.execute("select output from activities where id=?", (activity,)).fetchone()[0])["scene"]
    glb = scene["glb"].split(",", 1)[-1]
    image = db.execute("select image from artwork where id=?", (drawing,)).fetchone()[0]
    with tempfile.NamedTemporaryFile(suffix=".png") as file:
        Image.open(io.BytesIO(image)).convert("RGB").save(file.name)
        source = to_data_uri(file.name, max_edge=1024)
    result = view_calibration.calibrate(base64.b64decode(glb), source, client)
    base = result.get("camera_base")
    status = result["camera_calibration"]["status"]
    verdict = "no view" if base is None else "right" if off_by(base[0], right) <= slack else "WRONG"
    return {"case": label, "run": run, "status": status, "base": base, "right_yaw": right, "verdict": verdict,
            "reason": result["camera_calibration"].get("reason"),
            "selections": result["camera_calibration"].get("selections"), "replies": client.replies}


def main():
    runs = int(sys.argv[1]) if len(sys.argv) > 1 else 3
    load_dotenv()
    client = build_client(load_profile("stepfun")["vlm.sketch"])
    db = sqlite3.connect(f"file:{PORTFOLIO}?mode=ro", uri=True, check_same_thread=False)
    jobs = [(case, run) for case in CASES for run in range(runs)]
    with ThreadPoolExecutor(max_workers=3) as pool:
        results = list(pool.map(lambda job: one(*job, client, db), jobs))
    for row in results:
        print(json.dumps(row, ensure_ascii=False))
    for verdict in ("right", "WRONG", "no view"):
        print(verdict, sum(r["verdict"] == verdict for r in results), "of", len(results))


if __name__ == "__main__":
    main()
