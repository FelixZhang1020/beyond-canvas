"""A judge's objection has to point at words that are really there.

The class's judges are Qwen3.6 on the Spark with its thinking off (operator: no
Step 3.7 Flash in anything a person waits for). It answers a rule check in under two seconds, and on
seven replies whose verdicts were known it refused every good one: it copied the prompt's own example
("calls the purple blob a mushroom") about a reply with no mushroom in it, listed the child's own
words back, and listed questions as invented story, which the invention prompt says a question never
is. Thinking on fixed it at 35 to 200 seconds a reply, which is the delay the switch was made to end.

So a judge names the exact words it objects to, and an objection stands only when those words are in
the line, are not the child's own (or the opening's, or the lesson's), where the rule says a question
is fine are not the question, and survive one narrow second question about those words alone
(`recheck`): "did the child already say this?" is a question a fast model answers well, where "list
everything wrong" is not. It is asked only when there is an objection, so a clean line costs nothing. A judge that answers in descriptions, the older shape that
Step and every test double still use, is taken at its word as before: nothing here can check a
description, and dropping it would pass a line nobody looked at.
"""

from __future__ import annotations

import re
from collections.abc import Callable
from typing import Any

from evalkit.rubric.lexicons import QUESTION_MARKS, QUESTION_PARTICLES_ZH

# Whitespace and quotation marks, which a judge copying words drops or adds freely. The curly quotes
# and the CJK corner brackets are built from their code points, so no Chinese sits in code.
_QUOTES = "".join(map(chr, (0x201C, 0x201D, 0x2018, 0x2019, 0x300C, 0x300D, 0x300E, 0x300F)))
_LOOSE = re.compile("[\\s\"'`" + _QUOTES + "]+")
# Where a clause ends: a sentence's end, or a comma, colon or semicolon inside one, in both alphabets
# (the full-width full stop, exclamation, question mark, comma, enumeration comma, semicolon, colon).
_BREAKS = frozenset(".!?,;:\n" + "".join(map(chr, (0x3002, 0xFF01, 0xFF1F, 0xFF0C, 0x3001, 0xFF1B, 0xFF1A))))


def _squash(text: str) -> str:
    return _LOOSE.sub("", text)


def found(words: str, text: str) -> bool:
    squashed = _squash(words)
    return bool(squashed) and squashed in _squash(text)


def ends_in_the_question(words: str, line: str) -> bool:
    """Do these words end inside the clause that carries a question mark?

    "Where will the dog take them?" is a question, and so is its tail when a judge quotes only that.
    "He is scared, where will they go?" states a feeling before its comma, and the words "he is
    scared" end in that first clause, so they are still a statement. A Chinese clause that ends in a
    question particle asks whatever follows it.
    """
    squashed, whole = _squash(words), _squash(line)
    start = whole.find(squashed)
    if not squashed or start < 0:
        return False
    end = start + len(squashed)
    if whole[end - 1] in QUESTION_MARKS:
        return True
    for at in range(end, len(whole)):
        if whole[at] in _BREAKS:
            return whole[at] in QUESTION_MARKS or (at > 0 and whole[at - 1] in QUESTION_PARTICLES_ZH)
    return False


def said_outside_the_question(words: str, line: str) -> bool:
    """Does any occurrence of these words end in a clause that states, rather than asks?"""
    squashed, whole = _squash(words), _squash(line)
    start = whole.find(squashed) if squashed else -1
    while start >= 0:
        if not ends_in_the_question(squashed, whole[start:]):
            return True
        start = whole.find(squashed, start + 1)
    return False


def standing(items: Any, line: str, theirs: str, *, questions_are_fine: bool,
             recheck: Callable[[str, str], bool] | None = None) -> list[str]:
    """The objections that survive checking, as evidence a rewrite can act on.

    `theirs` is everything the rule counts as already said: the child's words, and the opening or the
    lesson where the rule reads them. An item that quotes words (a dict with "words") is checked; a
    plain string is a description and passes through unchecked. `recheck(words, why)` says whether an
    objection still stands once asked about on its own; it is the rule's to write, and to fail closed.
    """
    if isinstance(items, (str, dict)):
        items = [items]
    if not isinstance(items, list):
        return []
    kept: list[str] = []
    for item in items:
        if not isinstance(item, dict):
            if str(item).strip():
                kept.append(str(item))
            continue
        words, why = str(item.get("words") or ""), str(item.get("why") or "")
        source = str(item.get("source") or "")
        if not found(words, line) or (theirs and found(words, theirs)):
            continue
        if source and theirs and found(source, theirs):
            continue
        # Every place the words appear, not the first: "will it fly? It flies to the moon." states it
        # after asking it (code review).
        if questions_are_fine and not said_outside_the_question(words, line):
            continue
        if recheck is not None and not recheck(words, why):
            continue
        kept.append(f"{why} ({words})" if why else words)
    return kept
