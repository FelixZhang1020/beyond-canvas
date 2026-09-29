"""Open a conversation about one child's drawing, and reply when they answer.

The teacher picks an entrance when the class starts. On the colour entrance the
child tells the story inside their picture and nothing is corrected. On the
sketch entrance a plaster-cast study gets a read of light, proportion and
structure, and a correction arrives as something to try. Age is not a
parameter on either: whether to critique is decided by the kind of work.

Usage:
    uv run python skills/art-feedback/scripts/feedback.py DRAWING --entrance colour --lang zh
    uv run python .../feedback.py DRAWING --entrance sketch
    uv run python .../feedback.py DRAWING --entrance colour --said "they walked a long way"
    uv run python .../feedback.py DRAWING --entrance colour --lesson "warm and cool colours"
    uv run python .../feedback.py DRAWING --entrance colour --opening "..." --rung 2

The prompts live in assets/prompts/, one file per entrance and beat, because
they are content rather than code and the two entrances double them.
"""

from __future__ import annotations

import argparse
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

from studio.conversation.words import answered_turn, asked_in
from studio.core.env import load_dotenv
from studio.core.images import to_data_uri
from studio.providers import build_client
from studio.providers.base import VisionChatClient
from studio.core.slots import load_profile, resolve

LANGUAGE_NAMES = {"en": "English", "zh": "Chinese"}
ENTRANCES = ("sketch", "colour")
RUNGS = (2, 3)
PROMPTS = Path(__file__).parent.parent / "assets" / "prompts"


@dataclass(frozen=True)
class ClassSettings:
    """What the teacher sets once, before class, for every child in it.

    The entrance is chosen by hand. There is no automatic detection, because a
    coloured-pencil study would fool a colour test and the lesson already knows
    which kind of class it is; so there is no default either.
    """

    entrance: str
    language: str
    lesson_intent: str = ""

    def __post_init__(self) -> None:
        if self.entrance not in ENTRANCES:
            raise ValueError(f"entrance must be one of {ENTRANCES}, not {self.entrance!r}")
        if self.language not in LANGUAGE_NAMES:
            raise ValueError(f"language must be one of {tuple(LANGUAGE_NAMES)}, not {self.language!r}")

    @property
    def language_name(self) -> str:
        return LANGUAGE_NAMES[self.language]


def _prompt(name: str) -> str:
    return (PROMPTS / f"{name}.txt").read_text(encoding="utf-8").rstrip("\n")


def build_prompt(settings: ClassSettings) -> str:
    """The rubric restated as instructions, one prompt per entrance.

    Both entrances share the same tail: a blank page or a photograph is refused
    kindly, and a name written on the paper is never read back.
    """
    intent = settings.lesson_intent.strip()
    lesson = "\n\n" + _prompt("lesson-clause").format(intent=intent) if intent else ""
    opening = _prompt(f"{settings.entrance}-opening").format(language=settings.language_name)
    return opening + "\n\n" + _prompt("shared-tail") + lesson


# What to add to a prompt when the grader has already refused one attempt. The
# rules are numbered the same way everywhere, so naming the number is enough.
AGAIN_CLAUSE = """

Your last attempt was refused because it broke {broken}. Write a different
response that does not. Do not apologise and do not mention this instruction."""


def write_feedback(
    image_path: str,
    settings: ClassSettings,
    client: VisionChatClient,
    broken: str = "",
) -> str:
    """Beats one and two: one observation, then one question.

    `broken` is the grader's verdict on a previous attempt. Passing it turns a
    blind retry into a targeted one: the harness has always supported a repair
    step and nothing ever supplied one, so a refused response was rewritten with
    no idea what was wrong with it.
    """
    prompt = build_prompt(settings)
    if broken:
        prompt += AGAIN_CLAUSE.format(broken=broken)
    return client.chat(prompt, [to_data_uri(image_path)]).text


def build_rung_prompt(settings: ClassSettings, rung: int, asked: str,
                      history: Sequence[str] = ()) -> str:
    """Rungs two and three of the escalation when a child says nothing.

    Rung one is the opening question itself, already asked. Never repeat a
    question: make the door smaller instead. On the colour entrance the smaller
    door leads into the picture; on the sketch entrance it leads into the
    process, because a plaster cast has nowhere to be going. A child can fall
    quiet halfway through a story, so the colour rungs are also given the
    conversation so far: a smaller question that forgot the story, or called
    the child's dog a cat again, would tell them nobody had been listening.
    """
    if rung not in RUNGS:
        raise ValueError(f"rung must be 2 or 3, not {rung}; rung 1 is the opening question")
    return _prompt(f"{settings.entrance}-rung-{rung}").format(
        asked=asked, language=settings.language_name, previous_dialogue=recent_dialogue(history)
    )


def climb_a_rung(
    image_path: str,
    settings: ClassSettings,
    asked: str,
    rung: int,
    client: VisionChatClient,
    broken: str = "",
    *,
    history: Sequence[str] = (),
) -> str:
    """Ask again, smaller, when the child said nothing.

    The failure this guards against is silence being read as refusal. In a class
    of twenty some children will not answer an open question, and the answer is a
    smaller door rather than a louder question.
    """
    prompt = build_rung_prompt(settings, rung, asked, history)
    if broken:
        prompt += AGAIN_CLAUSE.format(broken=broken)
    return client.chat(prompt, [to_data_uri(image_path)]).text


def recent_dialogue(history: Sequence[str]) -> str:
    """The last turns of the conversation, oldest first, within a size a prompt can carry."""
    lines = [line[:600] for line in history[-10:] if line.strip()]
    while lines and len("\n".join(lines)) > 2400:
        lines.pop(0)
    return "\n".join(lines) or "(nothing earlier)"


def question_answered(opening: str, history: Sequence[str]) -> str:
    """The question the child's new answer replies to: the companion's last one, or the opening's.

    Named on its own line in the reply prompt: a child answering "why is the soldier blowing his
    trumpet?" with "to buy time" had the answer given to the mouse king or to "you" in four replies of eight on
    the Spark, the question sitting unread among the last ten turns.
    """
    return asked_in(answered_turn(history, opening)) or "(none: they are adding to their story)"


def build_reply_prompt(settings: ClassSettings, opening: str, child_said: str,
                       history: Sequence[str] = ()) -> str:
    """Beat four. The rules it mirrors are 13 and 14.

    On the sketch entrance the reply also carries the technical read, built
    around the part the child said was hard.
    """
    return _prompt(f"{settings.entrance}-reply").format(
        opening=opening, child_said=child_said, language=settings.language_name,
        previous_dialogue=recent_dialogue(history), asked=question_answered(opening, history),
    )


def write_reply(
    image_path: str,
    settings: ClassSettings,
    opening: str,
    child_said: str,
    client: VisionChatClient,
    broken: str = "",
    *,
    history: Sequence[str] = (),
) -> str:
    """Beat four: the reply that uses what the child just said.

    The spec calls this the easiest beat to drop and the one that matters most.
    When it lands, children usually add something they had not said yet, and
    that addition is the evidence it worked.
    """
    prompt = build_reply_prompt(settings, opening, child_said, history)
    if broken:
        prompt += AGAIN_CLAUSE.format(broken=broken)
    # The picture goes with every reply: linking what the child said to something
    # they drew is the move section 5a holds up as the proof this beat worked.
    return client.chat(prompt, [to_data_uri(image_path)]).text


def open_the_question(
    reply: str,
    settings: ClassSettings,
    client: VisionChatClient,
    problem: str,
) -> str:
    """The same reply, ending in an open question this time.

    A reply's question leaves the answer to the child. The writer that answers first on
    the Spark reached for yes-or-no questions however it was told (six first
    attempts in eight), and writing the reply afresh only repeated the habit, so it is
    handed its own reply and the reason, and asked to change the question alone. The
    whole reply comes back, because a Chinese reply often says it and asks it in one
    sentence. Text only: a question is reworded, the picture is not read again.
    """
    prompt = _prompt(f"{settings.entrance}-open-question").format(
        reply=reply, problem=problem, language=settings.language_name
    )
    return client.chat(prompt, []).text


def say_back(
    reply: str,
    child_said: str,
    settings: ClassSettings,
    client: VisionChatClient,
) -> str:
    """The same reply, starting by saying back what the child just said, in their words.

    A reply that repeats none of the child's words is refused (rule 13), and a child who asks
    for help got one every time: the writer answered the question and said none
    of it back. The studio can put their words in front itself, but it reads stiff ("You said:
    ..."), so the writer is asked once to work them in, which a teacher hears as listening.
    Text only: the picture is not read again.
    """
    prompt = _prompt("say-back").format(reply=reply, child_said=child_said, language=settings.language_name)
    return client.chat(prompt, []).text


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Feedback on a child's drawing")
    parser.add_argument("drawing", help="path to a photograph of the drawing")
    parser.add_argument(
        "--entrance",
        required=True,
        choices=list(ENTRANCES),
        help="which kind of class the teacher chose: sketch critiques, colour never does",
    )
    parser.add_argument("--lang", default="en", choices=list(LANGUAGE_NAMES))
    parser.add_argument("--slot", default="vlm.studio")
    parser.add_argument("--profile", default="cloud")
    parser.add_argument(
        "--said",
        default="",
        help="what the child answered, transcribed. Supplying it runs the fourth beat.",
    )
    parser.add_argument(
        "--lesson",
        default="",
        help="what this class was teaching, set once for the whole class",
    )
    parser.add_argument(
        "--rung",
        type=int,
        choices=list(RUNGS),
        help="the child said nothing: 2 offers two choices, 3 lets a character ask",
    )
    parser.add_argument(
        "--opening",
        default="",
        help="the machine's own first line, when replying to --said in a second run",
    )
    return parser


def main() -> None:
    arguments = build_parser().parse_args()
    settings = ClassSettings(arguments.entrance, arguments.lang, arguments.lesson)

    load_dotenv()
    client = build_client(resolve(arguments.slot, load_profile(arguments.profile)))

    opening = arguments.opening or write_feedback(arguments.drawing, settings, client)
    print(opening)
    if arguments.rung:
        print()
        print(climb_a_rung(arguments.drawing, settings, opening, arguments.rung, client))
    elif arguments.said:
        print()
        print(write_reply(arguments.drawing, settings, opening, arguments.said, client))


if __name__ == "__main__":
    main()
