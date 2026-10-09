"""Time the four classroom tabs on the isolated Spark test copy.

The only before/after code difference is the pre-optimization creation-draft
method. Public fixture images are used, and the image safety gate is fixed so
that draft, review and media latency can be compared without safety variance.
The animation request explicitly selects online Wan 3.0; Wan 2.2 is never used.
No model text, media, identifiers or credentials are printed or saved.
"""

from __future__ import annotations

import json
import os
import sys
import tempfile
import time
from pathlib import Path
from types import MethodType

from studio.classroom.classroom import Classroom
from studio.core.deployments import build_runtime
from studio.providers.choices import ClipChoices, clip_makers
from studio.providers.frontvoice import FrontFirst, WithFrontVoice
from tools.bench_story_speed import Allowed, IMAGES, SCENES, Timed, old_creation_draft


def measure(room, sid, skill, ids, options, calls):
    offset = len(calls)
    started = time.monotonic()
    rid = room.request(sid, skill, ids, options)["request_id"]
    room.run_request(rid)
    elapsed = time.monotonic() - started
    done = next(data for event, data in room.follow(rid) if event == "done")
    entries = list(room.ledger.entries(rid))
    return {
        "elapsed_s": round(elapsed, 2),
        "status": done.get("status", "done"),
        "reason_code": done.get("reason_code", ""),
        "stages": [{"stage": entry.stage.split("-")[0] if entry.stage.startswith("screen-") else
                    entry.skill, "seconds": round(entry.wall_time_s, 2)} for entry in entries],
        "model_calls": {label: [duration for kind, duration in calls[offset:] if kind == label]
                        for label in ("qwen_chat", "qwen_creation", "qwen_teacher", "step_chat",
                                      "step_write", "step_review", "step_teacher")},
    }, done.get("outputs", {})


def run(module, variant, *, fixed=True):
    calls = []
    runtime = build_runtime("stepfun")
    clients = runtime.clients
    clients["safety.image"] = Allowed()
    studio = clients["vlm.studio"]
    creator = clients["vlm.creation"]
    teacher = clients["vlm.teacher"]
    if not isinstance(studio, WithFrontVoice) or not isinstance(creator, FrontFirst) or not isinstance(teacher, FrontFirst):
        raise RuntimeError("Expected Qwen-first clients for chat and creation")
    studio.front.front = Timed("qwen_chat", studio.front.front, calls)
    studio.front.behind = Timed("step_chat", studio.front.behind, calls)
    creator.front = Timed("qwen_creation", creator.front, calls, {} if fixed else None)
    creator.behind = Timed("step_write", creator.behind, calls)
    teacher.front = Timed("qwen_teacher", teacher.front, calls)
    teacher.behind = Timed("step_teacher", teacher.behind, calls)
    clients["vlm.director"] = Timed("step_review", clients["vlm.director"], calls)
    with tempfile.TemporaryDirectory(prefix="feature-speed-") as directory:
        room = Classroom(Path(directory) / "ledger.jsonl", profile="stepfun", clients=clients,
                         editor=runtime.editor)
        if variant == "before":
            room._creation_draft = MethodType(old_creation_draft, room)
        sid = room.begin({"language": "en", "entrance": "colour"})
        ids = [room.add_drawing(sid, path.read_bytes()) for path in IMAGES[:2 if module == "storybook" else 1]]
        if fixed:
            for did, scene in zip(ids, SCENES):
                creator.front.fixed_scenes[room._conversation(room.sessions[sid], did).image] = scene
            creator.front.fixed_outline = json.dumps([
                {"drawing_id": ids[0], "text": "Under a yellow sun, two stick figures watch a purple creature turn toward them."},
                {"drawing_id": ids[1], "text": "Nearby, three green trees stand beside two brown pointed shapes; one leans toward the trees."},
            ]) if module == "storybook" else None
        records = {}
        try:
            if module == "teacher":
                records["review"], _ = measure(room, sid, "teacher-review", ids, {}, calls)
            elif module == "chat":
                records["opening"], _ = measure(room, sid, "art-feedback", ids, {}, calls)
            elif module == "motion":
                records["scene"], _ = measure(room, sid, "scene-description", ids, {}, calls)
                editor = runtime.editor
                if editor is None or not isinstance(editor.client, ClipChoices):
                    raise RuntimeError("Expected explicit video choices")
                if clip_makers(editor) != ["online"]:
                    raise RuntimeError("Only online Wan 3.0 may be available in this benchmark")
                if os.environ.get("DASHSCOPE_API_KEY"):
                    records["online_wan3_video"], _ = measure(room, sid, "painting-to-animation", ids,
                        {"hint": SCENES[0], "media_kind": "video", "clip_maker": "online"}, calls)
                else:
                    records["online_wan3_video"] = {"status": "skipped_no_key"}
            elif module == "storybook":
                records["outline"], output = measure(room, sid, "story-outline", ids, {}, calls)
                if records["outline"]["status"] == "done" and not records["outline"]["reason_code"]:
                    pages = [{"drawing_id": item["drawing_id"], "text": item["text"]}
                             for item in output.get("outline", [])]
                    if len(pages) == len(ids):
                        records["binding"], _ = measure(room, sid, "drawings-to-storybook", ids,
                                                        {"pages": pages}, calls)
            else:
                raise ValueError(module)
        finally:
            room.close()
    return {"module": module, "variant": variant, "records": records}


if __name__ == "__main__":
    if sys.platform != "linux":
        raise SystemExit("Run only on the isolated Spark test copy")
    if sys.argv[1:] == ["storybook-raw"]:
        print(json.dumps(run("storybook", "after", fixed=False), ensure_ascii=False), flush=True)
        raise SystemExit(0)
    selected = tuple(sys.argv[1:]) or ("teacher", "chat", "motion", "storybook")
    if any(module not in ("teacher", "chat", "motion", "storybook") for module in selected):
        raise SystemExit("Choose teacher, chat, motion or storybook")
    for module in selected:
        for variant in ("before", "after"):
            result = run(module, variant)
            print(json.dumps(result, ensure_ascii=False), flush=True)
