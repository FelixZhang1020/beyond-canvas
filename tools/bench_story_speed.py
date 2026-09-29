"""One-off, content-free timing of the old and current story-outline retry paths.

Run only on the Spark test copy with the project's test-on-spark.sh command.
The first outline is deliberately stopped after approved scenes so both arms
exercise the same retry boundary. No generated text or image leaves the copy.
"""

from __future__ import annotations

import json
import sys
import tempfile
import time
from dataclasses import replace
from pathlib import Path
from threading import Lock
from types import MethodType

from studio.conversation import creation
from studio.classroom.classroom import Classroom
from studio.classroom.classroom_model import RequestCancelled
from studio.conversation.conversation import Beat
from studio.core.deployments import build_runtime
from studio.providers.base import ChatResult
from studio.providers.frontvoice import FrontFirst, without_front


ROOT = Path(__file__).resolve().parents[1]
IMAGES = (
    ROOT / "skills/art-feedback/evals/files/dog-sun.png",
    ROOT / "skills/art-feedback/evals/files/cat-shaded.png",
)
SCENES = (
    "Two stick figures stand beneath a yellow sun beside a purple four-legged creature. "
    "The creature gently turns toward the figures.",
    "Three green trees stand beside two overlapping brown shapes with pointed ears. "
    "One brown shape gently leans toward the trees.",
)


def _qwen_writes(conversation):
    """Recognize the Qwen-first writer in the historical review-path baseline."""
    return isinstance(getattr(conversation.creator, "inner", conversation.creator), FrontFirst)


class Allowed:
    def chat(self, prompt, images=(), **kwargs):
        return ChatResult('{"verdict":"allow","reason":"drawing","text_found":[]}',
                          0, 0, 0, 0.0, 0.0, "fixture", "fixture")


class Timed:
    def __init__(self, label, inner, calls, fixed_scenes=None):
        self.label, self.inner, self.calls = label, inner, calls
        self.fixed_scenes = fixed_scenes
        self.fixed_outline = None
        self.lock = Lock()

    def chat(self, prompt, images=(), **kwargs):
        started = time.monotonic()
        try:
            result = self.inner.chat(prompt, images, **kwargs)
            if self.fixed_scenes is not None and prompt.startswith("Write a short editable scene"):
                result = replace(result, text=self.fixed_scenes[images[0]])
            elif self.fixed_outline is not None and prompt.startswith("Compose a coherent children's story"):
                result = replace(result, text=self.fixed_outline)
            return result
        finally:
            with self.lock:
                self.calls.append((self.label, round(time.monotonic() - started, 3)))


def old_creation_draft(self, request, session):
    """The HEAD implementation before scene reuse/lookahead; same draft and review clients."""
    scenes, supplied = [], request.options.get("scenes", {})
    for did in request.drawing_ids:
        if request.cancelled.is_set():
            raise RequestCancelled()
        conversation = self._conversation(session, did)
        conversation.observe = self._observer(request)
        text = supplied.get(did) or session.scenes.get(did)
        generated = request.skill == "scene-description" or not text
        if generated:
            def scene():
                return conversation.creation_draft("scene", {
                    "dialogue": session.dialogue.get(did, []),
                    "previous": request.options.get("previous", "") if request.skill == "scene-description" else "",
                }, request.request_id)
            beat = scene()
            if (not beat.ok and beat.reason_code == "draft_review_failed" and request.skill != "scene-description"
                    and _qwen_writes(conversation) and not request.cancelled.is_set()):
                beat = scene()
            text = beat.text
        else:
            beat = conversation.story_page(text, request.request_id)
        if not beat.ok:
            candidate = ({"skill": "scene-description", "text": beat.draft, "drawing_id": did}
                         if beat.draft is not None else None)
            self._stop_draft(request, beat, candidate)
            return
        scenes.append({"drawing_id": did, "text": text, "supplemented": generated})
    if request.skill == "scene-description":
        output = {"text": scenes[0]["text"], "language": session.language}
    else:
        conversation = self._conversation(session, request.drawing_ids[0])

        def story():
            return conversation.creation_draft("story", {"scenes": [
                dict(scene, dialogue=session.dialogue.get(scene["drawing_id"], [])) for scene in scenes
            ], "previous": request.options.get("previous", "")}, request.request_id, request.drawing_ids,
                source_images=[self._conversation(session, did).image for did in request.drawing_ids])
        beat = story()
        if (not beat.ok and beat.reason_code in ("draft_review_failed", "rubric_failed")
                and _qwen_writes(conversation) and not request.cancelled.is_set()):
            with without_front():
                beat = story()
        if not beat.ok:
            candidate = ({"skill": "story-outline", "outline": creation.parse_outline(beat.draft, request.drawing_ids),
                          "scenes": scenes} if beat.draft is not None else None)
            self._stop_draft(request, beat, candidate)
            return
        output = {"outline": creation.parse_outline(beat.text, request.drawing_ids), "scenes": scenes,
                  "language": session.language}
    self._publish(request, "done", {"stage": request.skill, "request_id": request.request_id, "outputs": output})


def run_arm(name):
    calls = []
    runtime = build_runtime("stepfun")
    clients = runtime.clients
    creator = clients["vlm.creation"]
    assert isinstance(creator, FrontFirst)
    creator.front = Timed("qwen_write", creator.front, calls, {})
    creator.behind = Timed("step_write", creator.behind, calls)
    clients["vlm.director"] = Timed("step_review", clients["vlm.director"], calls)
    clients["safety.image"] = Allowed()  # isolate draft time; both images are public fixtures
    with tempfile.TemporaryDirectory(prefix="story-speed-") as directory:
        room = Classroom(Path(directory) / "ledger.jsonl", profile="stepfun", clients=clients)
        if name == "before":
            room._creation_draft = MethodType(old_creation_draft, room)
        sid = room.begin({"language": "en", "entrance": "colour"})
        ids = [room.add_drawing(sid, path.read_bytes()) for path in IMAGES]
        for did, scene in zip(ids, SCENES):
            creator.front.fixed_scenes[room._conversation(room.sessions[sid], did).image] = scene
        creator.front.fixed_outline = json.dumps([
            {"drawing_id": ids[0], "text": "Under a yellow sun, two stick figures watch a purple creature turn toward them."},
            {"drawing_id": ids[1], "text": "Nearby, three green trees stand beside two brown pointed shapes; one leans toward the trees."},
        ])
        first_conversation = room._conversation(room.sessions[sid], ids[0])
        real_draft = first_conversation.creation_draft

        def fail_first_outline(kind, content, request_id="", *args, **kwargs):
            if kind == "story":
                return Beat(kind, request_id, refused="benchmark outline outage", reason_code="model_unavailable")
            return real_draft(kind, content, request_id, *args, **kwargs)

        first_conversation.creation_draft = fail_first_outline
        records = []
        try:
            for press in (1, 2):
                if press == 2:
                    first_conversation.creation_draft = real_draft
                offset = len(calls)
                rid = room.request(sid, "story-outline", ids, {})["request_id"]
                started = time.monotonic()
                room.run_request(rid)
                elapsed = time.monotonic() - started
                done = next(data for event, data in room.follow(rid) if event == "done")
                entries = list(room.ledger.entries(rid))
                timed = calls[offset:]
                records.append({
                    "press": press,
                    "elapsed_s": round(elapsed, 2),
                    "status": done.get("status", "done"),
                    "reason_code": done.get("reason_code", ""),
                    "scene_stage_calls": sum(e.stage.startswith("scene-description-") for e in entries),
                    "scene_stage_s": round(sum(e.wall_time_s for e in entries
                                               if e.stage.startswith("scene-description-")), 2),
                    "outline_stage_calls": sum(e.stage.startswith("story-outline-") for e in entries),
                    "model_calls": {label: [seconds for kind, seconds in timed if kind == label]
                                    for label in ("qwen_write", "step_write", "step_review")},
                })
                if press == 1 and (done.get("reason_code") != "model_unavailable"
                                   or len(room.sessions[sid].accepted_scene_drafts) != (2 if name == "after" else 0)):
                    break
        finally:
            room.close()
    return {"variant": name, "records": records}


if __name__ == "__main__":
    if sys.platform != "linux":
        raise SystemExit("Run this benchmark on the Spark test copy, not on the Mac.")
    for variant in ("before", "after"):
        print(json.dumps(run_arm(variant), ensure_ascii=False), flush=True)
