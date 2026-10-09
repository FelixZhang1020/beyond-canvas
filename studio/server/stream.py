"""What the page is told while a request runs, and how it is told.

Two jobs, one place, because they are the same subject: the buffer that holds a
request's updates, and the translation from what the harness did into what the
page renders.

The buffer exists because the page opens its stream after the request has been
accepted, which is after the work has started. Anything written straight to the
socket would lose whatever happened in between — usually the safety step, which
is the one a judge most wants to see. So updates are appended to a list and the
stream replays it from the beginning.

The translation exists because the two halves name things differently. The
harness names a stage by its beat, the page names a step by its skill, and the
rubric is a gate in one and a visible step in the other.
"""

from __future__ import annotations

import json
import re
import threading
import time
from datetime import UTC, datetime
from typing import Any, Iterator

from studio.core.harness import Transition
from studio.core.ledger import Entry
from studio.conversation.words import REASON_CODES, split_question

SECOND_LOOK = re.compile(r"second-look:([a-z_]+(?:,[a-z_]+)*)")   # codes only; a note may go on after them

# The skills whose words the page shows while they are written (studio/server/textstream.py).
# Not the safety look, and not the media skills, whose models write numbers and plans.
TEXT_SKILLS = frozenset({"art-feedback", "teacher-review", "scene-description", "story-outline"})
# A story outline is written as JSON; while it arrives the page is shown its passages.
PASSAGE = re.compile(r'"text"\s*:\s*"((?:[^"\\]|\\.)*)')
UNFINISHED_ESCAPE = re.compile(r'\\(u[0-9a-fA-F]{0,3})?$')

# How long a follower waits before checking again whether the request finished.
# Only reached when a request produces nothing for a while; it is not a poll.
TICK_S = 1.0


class Stream:
    """One request's updates, and the condition that wakes whoever is watching."""

    def __init__(self) -> None:
        self.updates: list[tuple[str, dict[str, Any]]] = []
        self.finished = False
        self.cond = threading.Condition()

    def emit(self, name: str, data: dict[str, Any]) -> None:
        with self.cond:
            if self.finished:
                return
            self.updates.append((name, data))
            self.cond.notify_all()

    def finish(self) -> None:
        with self.cond:
            self.finished = True
            self.cond.notify_all()

    def follow(self, quiet_after: float | None = None) -> Iterator[tuple[str, dict[str, Any]] | None]:
        """Yield every update from the first, then stop once the request ends.

        Asked to, with `quiet_after` in seconds, it also yields `None` whenever
        that long has passed with nothing to report, so a route holding a
        socket open can say something on the wire without a second thread. A
        follower that did not ask never sees one, and nobody hears about quiet
        once the request has ended.
        """
        index = 0
        quiet_since = time.monotonic()
        while True:
            with self.cond:
                if len(self.updates) <= index and not self.finished:
                    self.cond.wait(timeout=TICK_S)
                batch = self.updates[index:]
                index = len(self.updates)
                finished = self.finished
            if batch:
                quiet_since = time.monotonic()
                yield from batch
            elif quiet_after is not None and not finished and time.monotonic() - quiet_since >= quiet_after:
                quiet_since = time.monotonic()
                yield None
            if finished:
                return

    # What the page hears -----------------------------------------------------

    def step(self, request_id: str, stage: str, status: str, line: dict | None = None) -> None:
        update = {"stage": stage, "status": status, "request_id": request_id}
        if line is not None:
            update["ledger"] = line
        self.emit("stage", update)

    def stop(self, stage: str, message: str, reason_code: str) -> None:
        """A stopped request, then the terminator the page closes its stream on.

        The page ends a request on `done` and reads a stream that merely closes
        as a model outage, so a kind refusal has to arrive as both.
        """
        data = {"stage": stage, "status": "stopped", "message": message, "reason_code": reason_code}
        self.emit("stage", data)
        self.emit("done", data)

    def observer(self, request_id: str):
        """Turn harness transitions into the page's steps."""
        # Stages whose check has sent a draft back: the words written after that are
        # a rewrite, and the page says so where they stand (operator).
        revised: set[str] = set()

        def observe(transition: Transition) -> None:
            stage = transition.stage.skill
            line = ledger_line(transition.entry, request_id) if transition.entry else None
            status = transition.status
            if status == "running":
                self.step(request_id, stage, "running")
            elif status == "writing" and stage in TEXT_SKILLS:
                # The words so far, straight from the model and not yet checked. Shown
                # where they will stay, replaced if the check sends them back, never
                # spoken: only the `done` result is read aloud (operator).
                shown = _shown(stage, transition.draft)
                if shown["text"].strip() or shown.get("question"):
                    # `name` says which drawing a book's scene is about (scene-description-<drawing>), so the page
                    # can show that picture and which page it is (operator).
                    self.emit("stage", {"stage": stage, "name": transition.stage.name, "status": "running",
                                        "request_id": request_id,
                                        "partial": {**shown, "writing": True, "revised": stage in revised}})
            elif status == "checking" and stage == "art-feedback":
                # The child-facing words, written and not yet passed by the rules.
                # The page shows them marked as under review and never speaks them;
                # only the `done` result is read aloud (operator).
                self.emit("stage", {"stage": stage, "status": "running", "request_id": request_id,
                                    "partial": {**_shown(stage, transition.draft), "checking": True,
                                                "revised": stage in revised}})
            elif status == "pass":
                self.step(request_id, stage, "gate_pass", line)
                if stage == "art-feedback":
                    # The gate that just passed IS the rubric. The page shows it
                    # as its own step because that is how a judge reads it.
                    self.step(request_id, "rubric", "gate_pass")
            elif status == "fail":
                revised.add(stage)
                # A gate said no. For feedback that gate IS the rubric, and the
                # page shows it as its own step because that is how a judge
                # reads it.
                self.step(request_id, "rubric" if stage == "art-feedback" else stage, "gate_fail", line)
            elif status == "error":
                # The model never answered. Drawing this as "checked it against
                # the rules — failed" told a judge the studio had caught a bad
                # response when it had caught nothing; the record on disk said
                # error all along. Found when a model endpoint went down
                # mid-run.
                self.step(request_id, stage, "stopped", line)
            elif status == "repair":
                self.step(request_id, stage, "repair")

        observe.wants_text = lambda stage: stage.skill in TEXT_SKILLS  # type: ignore[attr-defined]
        return observe


def _shown(skill: str, written: str) -> dict[str, str]:
    """Words being written, in the shape the page shows the finished ones in.

    The observation and the closing question go apart exactly as `done` will send
    them, so each lands in its own place from the first word and does not move when
    the check ends. An outline is JSON until it is parsed; its passages are shown.
    """
    if skill == "art-feedback":
        text, question = split_question(written)
        return {"text": text, "question": question}
    if skill == "story-outline":
        return {"text": "\n\n".join(_passage(raw) for raw in PASSAGE.findall(written))}
    return {"text": written}


def _passage(raw: str) -> str:
    raw = UNFINISHED_ESCAPE.sub("", raw)
    try:
        return json.loads('"' + raw + '"')
    except ValueError:
        return raw


def ledger_line(entry: Entry, request_id: str) -> dict[str, Any]:
    """One ledger entry in the page's field names. Hashes and paths, never content."""
    gate = entry.gate if entry.gate in ("pass", "fail") else None
    return {
        "ts": datetime.fromtimestamp(entry.at, UTC).isoformat(),
        "request_id": request_id,
        "stage": entry.skill,
        "beat": entry.stage,
        "inputs_hash": entry.inputs_hash,
        "outputs_path": entry.outputs_path,
        "gate": "fail" if entry.gate == "error" else gate,
        "tokens": entry.tokens,
        # Named by the contract beside `tokens` and never emitted at first,
        # so the ledger view built for judges could say what a
        # request spent in tokens and nothing about money. The harness has been
        # reading it off the meters into Entry.cost_usd the whole time.
        "cost": entry.cost_usd,
        "wall_s": entry.wall_time_s,
        "mem_before_gb": entry.memory_before_gb,
        "mem_after_gb": entry.memory_after_gb,
        # The contract says the ledger view exists to show this, and it was never
        # filled. A refused screen records its verdict as the note, so the code
        # is a lookup rather than a second source of truth. The verdict is the
        # note's first word: NVIDIA's second look adds its answer after it.
        "reason_code": REASON_CODES.get(entry.note.partition(" ")[0]) if entry.gate != "pass" else None,
        # What the second look said, as the safety skill recorded it: "clear",
        # "unavailable", or the codes of what it flagged. Never its words.
        "second_look": _second_look(entry.note),
        "note": entry.note,
    }


def _second_look(note: str) -> str | None:
    found = SECOND_LOOK.search(note or "")
    return found.group(1) if found else None
