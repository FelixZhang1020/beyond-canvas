"""The hero scenario as one call, for when nobody is waiting in the room.

The page holds a conversation open across beats; a benchmark, a test or a
command line wants the whole of beats one and two in a single call and no state
afterwards. That is all this is: open a conversation, take the opening, and let
it go.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from evalkit.rubric import Entrance
from studio.conversation.conversation import Conversation
from studio.core.harness import StageOutcome
from studio.core.ledger import Ledger
from studio.providers import build_client
from studio.core.slots import load_profile, resolve

# Re-exported because the floor is a property of the hero scenario rather than
# of either file, and callers have always read it from here.
from studio.conversation.conversation import RUBRIC_FLOOR  # noqa: E402,F401  (isort: skip)


@dataclass
class Session:
    """What happened, and what the teacher should show the child."""

    session_id: str
    opening: str = ""
    refused: str = ""
    outcomes: list[StageOutcome] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return bool(self.opening) and not self.refused


def open_a_conversation(
    drawing: str | Path,
    ledger_path: str | Path,
    *,
    entrance: Entrance,
    profile: str = "cloud",
    language: str = "en",
    lesson_intent: str = "",
) -> Session:
    """Screen a drawing, write the opening, and gate it before anyone sees it.

    `entrance` is the teacher's choice for the whole class, sketch or colour.
    It has no default: section 5a says it is picked by hand, and it decides
    both which prompt the skill uses and which rules the gate applies.
    """
    resolved = load_profile(profile)
    conversation = Conversation(
        drawing,
        Ledger(ledger_path),
        entrance=entrance,
        studio=build_client(resolve("vlm.studio", resolved)),
        director=build_client(resolve("vlm.director", resolved)),
        language=language,
        lesson_intent=lesson_intent,
    )
    beat = conversation.open()
    return Session(beat.request_id, beat.text, beat.refused, beat.outcomes)
