"""The three things the companion says about one drawing: the opening, a reply, a smaller question.

Split out of conversation.py, which had grown past the 500-line limit; the
Conversation mixes this in, as it does the gates that check what these write.

Every beat after the opening reads the conversation so far, as the page's lines "Child: ..."
and "Companion: ...", oldest first, and every beat sends the picture. A colour reply used
to see only its own opening and the child's last sentence: it could not link the child's
words to anything the opening had not named, and a name the child gave two turns earlier
looked, to the judge of invention, like one the studio made up.
"""

from __future__ import annotations

import re
import unicodedata
from typing import Any

from evalkit.rubric.lexicons import OPEN_MARKERS, QUESTION_PARTICLES_ZH, YES_NO_OPENERS_EN
from evalkit.rubric.loop import rule_13_reply_uses_the_childs_words
from evalkit.rubric.structural import rule_9_ends_with_open_question
from evalkit.rubric.text import detect_lang
from studio.conversation.words import (CLOSERS, QUESTION_MARKS, STRAIGHT_QUOTE, answered_turn, asked_in,
                                       bare_question, parts, say)

CHILD = "Child: "
COMPANION = "Companion: "
# How many times a closed question is reworded on its own before the reply goes without it.
REWORDINGS = 2
# The most of the child's words said back in front of a reply that repeated none of them.
HEARD_AT_MOST = 30
# The marks a finished sentence ends in, half and full width: full stop, exclamation, question, and the
# ellipsis and wave dash a line trails off on, which a full stop after them would only double.
ENDS = (".", "!", "?", "~", chr(0x3002), chr(0xFF01), chr(0xFF1F), chr(0x2026), chr(0xFF5E))
# Where a clause ends inside a sentence, in both alphabets: comma, semicolon, colon, the enumeration comma.
CLAUSE_BREAKS = ",;:" + "".join(map(chr, (0xFF0C, 0xFF1B, 0xFF1A, 0x3001)))
# The other way Chinese asks, X-not-X (as in "will it or not"), built from the code point for "not".
EITHER_OR_ZH = re.compile("(.)" + chr(0x4E0D) + "\\1")
# Where Chinese question words say rather than ask, by code point: followed by "all" or "also" they mean any
# ("anyone at all"), after "not" or "without" they soften a statement, and "one" before X-not-X makes the
# set phrase for standing quite still. A sentence-final "ne" asks only with a question word or after "that".
ANY_AFTER, SOFT_BEFORE, ONE, THAT = (chr(0x90FD), chr(0x4E5F)), (chr(0x4E0D), chr(0x6CA1)), chr(0x4E00), chr(0x90A3)
# A sentence this short inside the one before it may be a real echo (a bare "ok."), so it is left.
REPEAT_AT_LEAST = 4
# A statement this much made of an earlier sentence's character pairs (or words) is that sentence again: the
# class page's three wordings of one party shared 68% and 100% with the first.
ECHO_AT_LEAST = 0.6
# The shortest end of a long sentence worth saying back; shorter, and the start of the sentence is said instead.
HEARD_AT_LEAST = HEARD_AT_MOST // 3


class ChatBeats:
    """The art-feedback beats of a Conversation, which supplies _beat, the gates and the skill."""

    def open(self, request_id: str = "") -> Any:
        """Beats one and two: the observation, then the one open question."""

        def write(inputs: dict[str, Any]) -> str:
            return self.feedback.write_feedback(
                self.drawing, self.settings, self.writer, inputs.get("broken", "")
            )

        beat = self._beat("opening", write, self._opening_gate(), request_id, repair=_tell_it_why)
        _or_the_studios_own(beat, say(self.language, f"opening_fallback_{self.entrance}"))
        if beat.ok:
            self.opening = beat.text
        return beat

    def reply(self, child_said: str, request_id: str = "", *, history: tuple[str, ...] = ()) -> Any:
        """Beat four: answer with the child's own words, never past them."""
        opened = self._need_opening(request_id)
        if opened is not None:
            return opened

        def write(inputs: dict[str, Any]) -> str:
            text = _said_once(_finished(self.feedback.write_reply(
                self.drawing, self.settings, self.opening, child_said, self.writer,
                inputs.get("broken", ""), history=history,
            )))
            text = self._open_the_question(text) if self.entrance == "colour" else text
            if _repeats_too_little(text, child_said):
                # Asked once to work their words in; the studio's own say-back is the fallback.
                text = self.feedback.say_back(text, child_said, self.settings, self.writer).strip() or text
            return _said_once(_finished(_heard(text, child_said, self.language)))

        # The reply needs the repair step more than any other beat: rule 13 is a
        # red line here, so a reply that missed the child's words is refused
        # outright, and a blind second attempt is likely to miss them again.
        # The question's follow-up judge is about a story, so it reads colour conversations only;
        # a question asked word for word before is refused in both, by the studio itself.
        dialogue = self.feedback.recent_dialogue(history) if self.entrance == "colour" else ""
        gate = self._reply_gate(child_said, dialogue, _child_words(history), _asked(history),
                                answering=answered_turn(history, self.opening))
        beat = self._beat("reply", write, gate, request_id, repair=_tell_it_why)
        if beat.reason_code == "rubric_failed" and child_said.strip():
            # Every attempt crossed a line. The child hears their own words back and one open question,
            # which cross none, rather than "something went wrong" in the middle of their story
            # (operator). The ledger keeps every refused attempt; the Portfolio keeps the rules.
            beat.text, beat.refused, beat.reason_code = self._said_back(child_said, _asked(history)), "", ""
        return beat

    def _said_back(self, child_said: str, asked: tuple[str, ...] = ()) -> str:
        """The child's last sentence and one open question, with anything written on the drawing taken out.

        Every model-written line passes the redactor (Conversation._redacting); this one is the studio's
        own, so it is redacted here, or a name the child read off their drawing would be shown and spoken
        back only on the path where every check had already refused (code review). When its
        one question was already asked, the child hears their words alone: the studio never asks the same
        question twice either (code review).
        """
        line = say(self.language, f"said_back_{self.entrance}").format(words=_last_words(child_said))
        if bare_question(asked_in(line)) in {bare_question(question) for question in asked}:
            line = say(self.language, "heard_you").format(words=_last_words(child_said))
        found = self.verdict.text_found if self.verdict is not None else ()
        return self.safety.redact(line, found) if found else line

    def climb(self, rung: int, request_id: str = "", *, history: tuple[str, ...] = ()) -> Any:
        """Beat three: the child said nothing, so make the door smaller."""
        opened = self._need_opening(request_id)
        if opened is not None:
            return opened

        def write(inputs: dict[str, Any]) -> str:
            return self.feedback.climb_a_rung(
                self.drawing, self.settings, self.opening, rung, self.writer,
                inputs.get("broken", ""), history=history,
            )

        earlier = _child_words(history)
        beat = self._beat(
            f"rung-{rung}", write, lambda text: self._rung_gate(text, earlier), request_id,
            repair=_tell_it_why,
        )
        return _or_the_studios_own(beat, say(self.language, f"rung_fallback_{self.entrance}"))

    def _open_the_question(self, text: str) -> str:
        """A colour reply's question must be open; its wording is fixed on its own.

        The gate refuses a yes-or-no question, and until this a refusal cost the whole reply:
        a probe of section 5a's own conversation on the Spark ended two replies in
        eight in the hiccup line because every attempt asked 吗. So the writer is handed its
        reply and asked to change the question alone, a second or so each time, and if it will
        not open the reply goes without it, which section 5a allows once the child has said
        something. A reply whose question cannot be taken off (one sentence that says and asks
        at once) is left for the gate.
        """
        for _ in range(REWORDINGS):
            verdict = _question(text)
            if verdict is None:
                return text
            text = _finished(self.feedback.open_the_question(text, self.settings, self.writer, verdict).strip())
        if _question(text) is None:
            return text
        return _without_closed_questions(text)

    def _need_opening(self, request_id: str) -> Any:
        """A reply or a rung follows something. Write it first if it is missing."""
        if self.opening:
            return None
        opened = self.open(request_id)
        return None if opened.ok else opened


def _question(text: str) -> str | None:
    """Why this reply's question will not do, or None when it will, or when there is none."""
    if text.count("?") + text.count("？") > 1:
        # Probe: a reworded reply kept its yes-or-no question and added an open one after it.
        return "it asks more than one question"
    if not text.rstrip().endswith(("?", "？")):
        return None
    verdict = rule_9_ends_with_open_question(text)
    return None if verdict.status == "pass" else verdict.evidence


def _without_closed_questions(text: str) -> str:
    """The reply with every question taken out but a last one that is open.

    What is left must still say something: a reply that is only questions is returned whole,
    for the gate to refuse and the harness to write again.
    """
    pieces = parts(text)
    kept = [part for part in pieces[:-1] if not part.endswith(QUESTION_MARKS)]
    if pieces and (not pieces[-1].endswith(QUESTION_MARKS)
                   or rule_9_ends_with_open_question(pieces[-1]).status == "pass"):
        kept.append(pieces[-1])
    said = [part for part in kept if not part.endswith(QUESTION_MARKS)]
    return ("" if detect_lang(text) == "zh" else " ").join(kept) if said else text


def _repeats_too_little(text: str, child_said: str) -> bool:
    """Rule 13's shortfall alone: too few of the child's words, not their sentence handed back."""
    verdict = rule_13_reply_uses_the_childs_words(text, child_said)
    return verdict.status == "fail" and "handed back" not in verdict.evidence and bool(text.strip())


def _heard(text: str, child_said: str, language: str) -> str:
    """The reply, with the child's own words said back in front when it repeated too few of them.

    Rule 13 refuses a reply that could have been written before the child spoke, and a child who asks
    for help gets one that answers without repeating them. On the class page, "I don't
    understand, so how exactly do I draw it" was sent three times and all nine attempts were refused,
    each told why: Qwen answered the question every time and repeated none of it. Saying their words back is section 5a's own fourth
    beat, so the studio does it itself rather than ask again. Only their last sentence, and not past
    HEARD_AT_MOST characters, so a long answer is not read back whole. The writer is asked first
    to work the words in itself (feedback.say_back); this is what is left when it does not.
    """
    if not _repeats_too_little(text, child_said):
        return text
    heard = say(language, "heard_you").format(words=_last_words(child_said))
    return f"{heard}{'' if detect_lang(text) == 'zh' else ' '}{text}"


def _or_the_studios_own(beat: Any, line: str) -> Any:
    """A beat every attempt of which a check refused, given the studio's own plain line instead.

    The reply got this first (the child's words said back); the first comment and the smaller
    question did not, and a teacher then got "something went wrong" for a first comment.
    Every chat beat now delivers something unless the drawing itself was refused or no model answered:
    a look-and-ask for the first comment, one open question for the smaller one. Neither names anything
    in the drawing, so neither can presume, correct or invent (studio/conversation/strings.json).
    """
    if beat.reason_code == "rubric_failed":
        beat.text, beat.refused, beat.reason_code = line, "", ""
    return beat


def _last_words(child_said: str) -> str:
    """The child's last sentence, without its closing mark and never longer than HEARD_AT_MOST.

    A sentence too long is shortened between its clauses, keeping its end, which is what "and then
    what happened?" follows: cut at the character, it read the child's words back broken off one word
    before the end of their sentence (the class page). Only a single clause longer than the
    limit is still cut inside itself.
    """
    last = (parts(child_said) or [child_said.strip()])[-1].strip()
    while last and (last[-1].isspace() or unicodedata.category(last[-1]).startswith("P")):
        last = last[:-1]
    if len(last) <= HEARD_AT_MOST:
        return last
    for at, mark in enumerate(last):
        if mark in CLAUSE_BREAKS and len(last) - at - 1 <= HEARD_AT_MOST:
            if len(last) - at - 1 >= HEARD_AT_LEAST:
                return last[at + 1:].strip()
            break   # the end that fits is a scrap ("..., ok"): say the start instead
    if detect_lang(last) != "zh" and " " in last[:HEARD_AT_MOST + 1]:
        return last[:HEARD_AT_MOST + 1].rsplit(" ", 1)[0].rstrip()   # English breaks between words
    return last[:HEARD_AT_MOST]


def _finished(text: str) -> str:
    """The reply with a mark at its end: a question's when its last clause asks, a full stop when it says.

    The writer now and then leaves the last mark off, and every check here knows a question by that
    mark. Once "how will the snow drift", unmarked, reached the page inside the bubble with no
    question shown, and a second question after a first went unseen, so the closed one was never taken
    out. Marked, the question meets those checks like any other.
    """
    body = text.rstrip()
    if not body or body.rstrip(CLOSERS + STRAIGHT_QUOTE).endswith(ENDS):
        return text
    body = body.rstrip(CLAUSE_BREAKS + " ")   # a line left on a comma ends there, with one mark
    if not body:
        return text
    last = parts(body)[-1]
    if detect_lang(body) == "zh":
        clause = re.split("[" + re.escape(CLAUSE_BREAKS) + "]", last)[-1]
        return body + (chr(0xFF1F) if _asks_zh(clause) else chr(0x3002))
    first = last.lower()
    asks = first.startswith(YES_NO_OPENERS_EN) or first.split(" ", 1)[0] in OPEN_MARKERS["en"]
    return body + ("?" if asks else ".")


def _asks_zh(clause: str) -> bool:
    """Whether a Chinese clause with no mark asks: a closing "ma", a question word used as one, X-not-X, "that ... ne".

    Code review: a teacher's soft statement shares its words with a question ("it has not grown yet,
    ne", "nothing at all", "standing quite still"), and a statement marked as a question is read out as one.
    """
    particle, soft_particle = QUESTION_PARTICLES_ZH[0], QUESTION_PARTICLES_ZH[1]
    if clause.endswith(particle):
        return True
    for marker in OPEN_MARKERS["zh"]:
        at = clause.find(marker)
        while at >= 0:
            after, before = clause[at + len(marker):at + len(marker) + 1], clause[at - 1:at] if at else ""
            if after not in ANY_AFTER and before not in SOFT_BEFORE:
                return True
            at = clause.find(marker, at + 1)
    either = EITHER_OR_ZH.search(clause)
    if either and clause[either.start() - 1:either.start()] != ONE:
        return True
    return clause.endswith(soft_particle) and clause.startswith(THAT)


def _said_once(text: str) -> str:
    """The reply with no sentence said twice: one already whole inside the sentence before it goes, and so
    does a statement made mostly of an earlier one's words (ECHO_AT_LEAST), the same thing said again.

    Asked to say the child's words back, the writer sometimes said them and then said their last
    sentence again, twice in one conversation. On the class page it once said the child's party and
    penguins three times over in three wordings and asked nothing (operator). A question is never
    taken out. Nothing else is touched, and a reply with nothing said twice comes back exactly as it
    was, line breaks and all.
    """
    pieces, kept = parts(text), []
    for piece in pieces:
        bare = "".join(piece.split())
        if kept and len(bare) >= REPEAT_AT_LEAST and bare in "".join(kept[-1].split()):
            continue
        if kept and not piece.rstrip().endswith(QUESTION_MARKS) and _echoes(piece, kept):
            continue
        kept.append(piece)
    if len(kept) == len(pieces):
        return text
    return ("" if detect_lang(text) == "zh" else " ").join(kept)


def _units(text: str) -> set[str]:
    """What a sentence is made of: pairs of characters in Chinese, which has no spaces, and words otherwise."""
    flat = unicodedata.normalize("NFKC", text).lower()
    if detect_lang(flat) == "zh":
        letters = [ch for ch in flat if ch.isalnum()]
        return {a + b for a, b in zip(letters, letters[1:])}
    return set(re.findall(r"[a-z0-9']+", flat))


def _echoes(piece: str, earlier: list[str]) -> bool:
    """Whether this sentence is mostly one said before it, in other words."""
    mine = _units(piece)
    return len(mine) >= REPEAT_AT_LEAST and any(len(mine & _units(said)) >= ECHO_AT_LEAST * len(mine)
                                                for said in earlier)


def _child_words(history: tuple[str, ...]) -> str:
    """What the child has said so far, one answer a line: theirs to name and to tell."""
    return "\n".join(line[len(CHILD):] for line in history if line.startswith(CHILD))


def _asked(history: tuple[str, ...]) -> tuple[str, ...]:
    """Every question the companion has already asked about this drawing, oldest first."""
    return tuple(question for question in (asked_in(line[len(COMPANION):]) for line in history
                                           if line.startswith(COMPANION)) if question)


def _tell_it_why(inputs: dict[str, Any], reason: str) -> dict[str, Any]:
    """Section 6's third step, supplied at last: retry once, then REPAIR, then stop.

    The harness has always had this hook and no caller ever passed one, so the
    second attempt was written by a model that had not been told what was wrong
    with the first. The gate's own reason names the rules it broke, and that is
    exactly what the writer needs.
    """
    return {**inputs, "broken": reason}
