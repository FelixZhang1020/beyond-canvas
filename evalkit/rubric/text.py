from __future__ import annotations

import re
from typing import Literal

_SENTENCE_BREAK = re.compile(r"(?<=[.!?。！？])\s*")
# The CJK Unified Ideographs block, U+4E00 to U+9FFF, written as escapes. This
# is a range boundary rather than domain data: the code points say what they are,
# and lexicons.py stays the only file carrying actual Chinese.
_CJK = re.compile(r"[\u4e00-\u9fff]")
CJK_THRESHOLD = 4


def detect_lang(text: str) -> Literal["zh", "en"]:
    """Decide which phrase list applies.

    A handful of Chinese characters is decisive: English feedback about a
    Chinese-language drawing will not contain four of them, while any Chinese
    sentence contains many.
    """
    return "zh" if len(_CJK.findall(text)) >= CJK_THRESHOLD else "en"


def sentences(text: str) -> list[str]:
    """Split on the terminators of both alphabets, dropping empties."""
    return [part.strip() for part in _SENTENCE_BREAK.split(text.strip()) if part.strip()]


_PHRASE_CACHE: dict[str, re.Pattern[str]] = {}


def mentions(lowered: str, phrase: str, lang: str, *, whole: bool = False) -> bool:
    """Is this phrase present as a word, rather than buried inside another one?

    English anchors to a word boundary at the front. Without one, a phrase list
    matches fragments: "rough" is inside "through" and "throughout", and a live
    run failed three correct replies on rule 8 for saying "the
    light comes through" and "reads as round throughout". "cute" hides inside
    "acute" the same way, which a sketch critique says often, and "how" inside
    "show" would have let a closed question pass rule 9.

    The front boundary alone, because most of these lists are stems and the
    endings are meant to be caught: "scribble" has to catch "scribbles" and
    "rough" has to catch "roughly".

    `whole` adds the boundary at the back as well, for a list of complete words
    that have no endings worth catching. Rule 9's question words are that list:
    "who" is always "who", and without the back boundary it matches the front of
    "whole", which let "is the whole page finished?" pass as an open question.

    Chinese is not spaced and offers no boundary to anchor to, so there this
    stays a plain substring test, which is what those lists were written for.
    """
    if lang == "zh":
        return phrase in lowered
    key = f"{phrase}\x00{whole}"
    pattern = _PHRASE_CACHE.get(key)
    if pattern is None:
        edge = r"\b" if whole or _ends_in_a_function_word(phrase) else ""
        pattern = _PHRASE_CACHE[key] = re.compile(r"\b" + re.escape(phrase) + edge)
    return pattern.search(lowered) is not None


# A phrase that ends in a short function word needs the back boundary too, and
# the reason is the same one the front boundary exists for. "just a" matched the
# front of "just arriving" and failed a rung — on rule 8, which is a red line, so
# it refused the child outright. An article at the end of a phrase carries no
# ending worth catching; a stem like "rough" or "scribble" does, and keeps the
# open back that lets it catch "roughly" and "scribbles".
_FUNCTION_TAIL = frozenset(
    {"a", "an", "the", "some", "of", "is", "it", "to", "in", "on", "as", "at", "so"}
)


def _ends_in_a_function_word(phrase: str) -> bool:
    return phrase.rsplit(" ", 1)[-1] in _FUNCTION_TAIL
