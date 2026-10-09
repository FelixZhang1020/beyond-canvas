"""The only words the harness itself says to a child, and how they are shaped.

Everything else a child hears comes from a skill. These are the few lines the
machinery has to say when no skill could run: a blank page, something that is
not a drawing, and a model that failed to answer. They live in a JSON file
beside this one because they are content in two languages, not code.
"""

from __future__ import annotations

import json
from pathlib import Path

from evalkit.rubric.text import detect_lang, sentences

# The two question marks, half and full width, by code point rather than glyph
# so this file carries no Chinese.
QUESTION_MARKS = ("?", chr(0xFF1F))
# Marks that close a quotation or a bracket, by code point: the curly double and single quotes, the two
# corner brackets, the full-width and ASCII round brackets, the lenticular bracket. They end the sentence
# they close. The straight double quote opens as well as closes, so it is counted instead (parts).
CLOSERS = "".join(map(chr, (0x201D, 0x2019, 0x300D, 0x300F, 0xFF09, 0x29, 0x3011)))
STRAIGHT_QUOTE = '"'

# What each safety verdict is called in the record and on the ledger view. The
# child never sees these; a teacher and a judge do. `unsafe` exists so that an
# image no child should be shown is not filed under the same code as a
# photograph of a room, which is what section 10 asks the parent view to show.
REASON_CODES = {
    "empty": "blank_page",
    "block": "photo_not_drawing",
    "unsafe": "unsafe_image",
}

STRINGS: dict[str, dict[str, str]] = json.loads(
    Path(__file__).with_name("strings.json").read_text(encoding="utf-8")
)


def say(language: str, key: str) -> str:
    """The harness's own words to a child, in the class language."""
    return STRINGS.get(language, {}).get(key) or STRINGS["en"][key]


def parts(text: str) -> list[str]:
    """The sentences of a text, each keeping the quotation marks and brackets that close it.

    A sentence ends at its full stop, and the mark closing a quotation comes after that stop: the
    split alone gave the child's quoted sentence to the question that followed it, and once
    the page showed questions beginning with a closing quote and a line break. A straight quote opens
    as often as it closes, so it goes back only while one is open.
    """
    pieces, straight = [], 0
    for piece in sentences(text):
        while pieces and piece and (piece[0] in CLOSERS or (piece[0] == STRAIGHT_QUOTE and straight % 2)):
            straight += piece[0] == STRAIGHT_QUOTE
            pieces[-1] += piece[0]
            piece = piece[1:].strip()
        if piece:
            pieces.append(piece)
            straight += piece.count(STRAIGHT_QUOTE)
    return pieces


def asked_in(text: str) -> str:
    """The question a text ends on, or nothing when it ends on something said."""
    pieces = parts(text)
    return pieces[-1] if pieces and pieces[-1].endswith(QUESTION_MARKS) else ""


def answered_turn(history, opening: str = "") -> str:
    """The companion's last turn, when it ended on the question the child is now answering; else nothing.

    One answer for the reply's writer and its who-said-it judge (code review): the judge was
    given the last question asked however long ago, the writer only the last turn's, and a turn that asked
    nothing left them disagreeing about who the child's he or she meant.
    """
    turn = next((line[len("Companion: "):] for line in reversed(history) if line.startswith("Companion: ")), opening)
    return turn if asked_in(turn) else ""


def bare_question(question: str) -> str:
    """A question as two askings of it compare: no spaces, and either width of question mark."""
    return "".join(question.split()).rstrip("".join(QUESTION_MARKS))


def split_question(text: str) -> tuple[str, str]:
    """Separate the closing open question from what comes before it.

    The page shows them apart: the observation in the bubble, the question as
    the line the teacher asks the child. A text that is nothing but a question
    stays whole, because taking it out would leave the bubble empty.
    """
    pieces = parts(text)
    if len(pieces) >= 2 and pieces[-1].endswith(QUESTION_MARKS):
        joiner = "" if detect_lang(text) == "zh" else " "
        return joiner.join(pieces[:-1]), pieces[-1]
    return text, ""
