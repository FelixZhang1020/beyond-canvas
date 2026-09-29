"""An append-only record of everything the studio did.

Section 6 wants one line per decision, and section 10 wants a crashed run to
resume from it. Both fall out of the same property: the ledger is the only
durable state, and it is never rewritten. A line is a fact that happened.

Resume works by reading back what already has a gate-pass recorded. A stage
with no pass record is the first one to run again, which means a crash between
doing the work and recording it costs one repeat rather than a wrong answer.

What a line must never contain: a child's drawing, a child's words, or anything
written on a page. The ledger is a record of the work, not of the child, so it keeps a
hash of the input and the path to an output, never the content. A judge reading
this file learns what the machine did and nothing about who it was done for.
"""

from __future__ import annotations

import hashlib
import json
import threading
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Iterator

SCHEMA = 1


@dataclass(frozen=True)
class Entry:
    """One decision. Everything a judge needs and nothing about the child."""

    session: str
    stage: str
    skill: str
    gate: str
    inputs_hash: str
    outputs_path: str = ""
    tokens: int = 0
    cost_usd: float = 0.0
    wall_time_s: float = 0.0
    memory_before_gb: float = 0.0
    memory_after_gb: float = 0.0
    note: str = ""
    at: float = field(default_factory=time.time)
    schema: int = SCHEMA

    @property
    def passed(self) -> bool:
        return self.gate == "pass"


def hash_inputs(*parts: Any) -> str:
    """A stable fingerprint of a stage's inputs, so a repeat is recognisable.

    Hashing rather than storing is what lets the ledger prove which drawing a
    stage ran on without keeping the drawing.
    """
    digest = hashlib.sha256()
    for part in parts:
        digest.update(repr(part).encode("utf-8"))
    return digest.hexdigest()[:16]


class Ledger:
    """Append-only JSON lines. Opened for append, never for write."""

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()

    def append(self, entry: Entry) -> Entry:
        # A note can carry an unpaired surrogate: json.loads accepts one from a
        # model and a UTF-8 file refuses it. A replacement mark keeps the
        # decision on record rather than losing it to the write.
        text = json.dumps(asdict(entry), ensure_ascii=False).encode("utf-8", "replace").decode("utf-8")
        with self._lock, self.path.open("a", encoding="utf-8") as handle:
            handle.write(text + "\n")
        return entry

    def entries(self, session: str | None = None) -> Iterator[Entry]:
        with self._lock:
            if not self.path.is_file():
                return
            lines = self.path.read_text(encoding="utf-8").split("\n")
        # One JSON object per "\n". str.splitlines() would also cut on the
        # Unicode line and paragraph separators, which JSON leaves raw inside a
        # string and a model can emit; one such note split the file and every
        # later read of it failed.
        for line in lines:
            if not line.strip():
                continue
            record = json.loads(line)
            if session is None or record.get("session") == session:
                yield Entry(**record)

    def forget(self, session: str) -> int:
        """Remove one class's lines, and say how many went.

        Append-only is a property of the file WHILE a class is running: nothing
        is ever rewritten under a judge who is reading it. It is not a promise
        that outlives the class. Section 1a's promise does: nothing about a child
        is kept, and a line saying what the studio decided about their drawing is
        about them. Ending the class removes them.
        """
        with self._lock:
            if not self.path.is_file():
                return 0
            kept, dropped = [], 0
            # One JSON object per "\n". str.splitlines() would also cut on the
            # Unicode line and paragraph separators, which JSON leaves raw inside a
            # string and a model can emit; one such note split the file and every
            # later read of it failed.
            for line in self.path.read_text(encoding="utf-8").split("\n"):
                if not line.strip():
                    continue
                if json.loads(line).get("session") == session:
                    dropped += 1
                else:
                    kept.append(line)
            self.path.write_text("\n".join(kept) + ("\n" if kept else ""), encoding="utf-8")
            return dropped

    def completed_stages(self, session: str) -> set[str]:
        """Stages with a recorded pass. Everything else is still to do."""
        return {entry.stage for entry in self.entries(session) if entry.passed}

    def spent(self, session: str) -> tuple[int, float]:
        """Tokens and dollars for one session, for the benchmark and the bill."""
        rows = list(self.entries(session))
        return sum(row.tokens for row in rows), round(sum(row.cost_usd for row in rows), 6)
