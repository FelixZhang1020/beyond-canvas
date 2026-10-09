"""Decide whether an image may reach the rest of the studio.

This runs before anything else and it is the only skill that can stop a
request. Section 6 puts it first in the data flow for a reason: a blocked image
never reaches the harness, so no other skill can receive one.

Four verdicts, and the difference between the last two matters:

    allow   a child's drawing, proceed
    soften  a drawing whose subject is dark or frightening; proceed, and the
            studio describes it warmly and judges it not at all
    block   not a child's drawing, or unsafe; stop
    empty   a blank page; stop, and ask kindly for the drawing

"soften" exists because a frightening drawing is not a problem to solve. The
spec is explicit: no "how scary", no asking whether something is wrong, no
suggestion to draw something happier. Blocking those would tell a child their
subject was unacceptable, which is the opposite of the product.

Text found on the page is reported separately from the verdict. A name or a
school does not block anything — it is redacted downstream, never read back.

A second reader may look first: NVIDIA's Nemotron 3.5 Content
Safety, a model trained for nothing else. What it may decide is the operator's
rule in nemotron.py beside this file, and it is narrow on purpose. At the door
it stops only sexual content, and only when it says so twice; anything else it
flags comes in as "soften" with codes for the teacher. On the way out any flag
refuses the machine-made picture. When it cannot be reached or read it stops
nothing, the four verdicts decide as they always have, and the record says the
second look was missing. It does not promise to catch a harmful picture: the
generated test drawings can only show that it turns no child away.

Usage:
    uv run python skills/studio-safety/scripts/safety.py DRAWING
    uv run python skills/studio-safety/scripts/safety.py DRAWING --profile spark --second-slot safety.reader
    ... --second-slot safety.reader --second-only --point out     # NVIDIA's model alone, on the way out
"""

from __future__ import annotations

import argparse
import functools
import importlib.util
import json
import sys
import time
from concurrent.futures import ThreadPoolExecutor, TimeoutError as NoAnswerYet
from dataclasses import dataclass, field, replace
from pathlib import Path

from studio.core.env import load_dotenv
from studio.core.errors import ModelError, ModelRefused, ModelUnavailable
from studio.core.images import to_data_uri
from studio.providers import build_client, build_safety_reader
from studio.providers.base import VisionChatClient
from studio.core.slots import load_profile, resolve

VERDICTS = ("allow", "soften", "block", "empty", "unsafe")

JUDGE_SYSTEM = "You are a precise annotator. Reply with JSON only. No prose, no code fences."

# How long one look at the door may take before it counts as no answer. A look takes 3-7 s;
# once one spent all 12,000 tokens thinking and returned nothing, and with the retries a
# drawing could wait about five minutes for a verdict that never came. Past this, the look is a
# model that did not answer, which the harness already asks once more. Only at the door: a finished
# clip's or toy's own pictures are looked at with no such limit, because the made thing is thrown away
# when its look fails and nothing asks again; the clip check's slowest real answer took 83 s.
LOOK_DEADLINE_S = 45.0

SAFETY_PROMPT = """Look at this image. It was submitted by a teacher to a children's art
studio, which expects artwork, including observational pencil studies.

Judge the visible medium and subject, not the creator's age or level of skill.
A carefully shaded graphite still life is artwork too. Pencil hatching, drawn
contours and paper grain are evidence of a drawing even when the solids look
realistic. Do not confuse a pencil study of solid forms with a photograph of
physical objects. Actual scene/person photographs still get "block", blank
pages still get "empty", and genuinely harmful images still get "unsafe".

Answer three things.

1. verdict — exactly one of:
   "allow"  a child's drawing or painting, with something on the page
   "soften" a child's drawing whose subject is dark or frightening: monsters,
            weapons, blood, someone hurt. Still a child's drawing. Still allowed.
   "block"  a photograph of a real scene or person, a screenshot, or a document.
            Not artwork, but nothing wrong with it either
   "unsafe" an image no child should be shown at all. Use this only for genuine
            harm, never for a frightening drawing: a drawn monster is "soften"
   "empty"  a blank or almost blank page with no drawing on it

**When you are not sure, the answer is "allow".** The two mistakes are not equal.
Letting a photograph through wastes a teacher's minute. Refusing a child's drawing
tells that child their work does not count, in front of their class, and the thing
they were about to say never gets said. Only refuse what you are certain about.

HOW the drawing was made is irrelevant. Crayon, paint, pencil, a tablet, or shapes
made on a computer are all a child's drawing. Judge the SUBJECT and whether this is
artwork rather than a photograph.

None of these is a reason to block, ever:
- it looks like a digital graphic, an icon, clip art or a logo
- it is simple, flat, or made of a few plain shapes
- the lines are clean, the colours are solid, or there is no shading
- it is a scribble nobody can identify
- it is faint, small, or drawn in pencil on white paper
- the child's painting is printed on a calendar, a card, a poster or a book page, or
  has printed words or numbers around it: the painting on it is still a child's
A five-year-old's drawing looks exactly like all of these.

A frightening subject is never a reason to block. Monsters, weapons, blood, someone
hurt: these are ordinary things for a child to draw, and they get "soften", which
still proceeds. If you find yourself wanting to block a dark drawing, the answer is
"soften". Blocking one tells a child their subject was unacceptable, and the thing
they were about to tell you never gets said.

Reserve "block" for an image that is genuinely not a child's artwork, and "unsafe"
for one that would harm a child to look at. A teacher sees which of the two you
chose; the child hears the same gentle words either way.

2. reason — one short sentence a teacher would understand. Never describe the
   contents of anything you blocked as unsafe.

3. text_found — every piece of written text visible in the image, as a list of
   strings. Names, school names, dates, titles, anything written. An empty list
   if the page carries no writing. Read it exactly; do not translate or guess.

Reply exactly like:
{"verdict": "allow", "reason": "a crayon drawing of a house and a sun", "text_found": []}"""


@dataclass(frozen=True)
class Verdict:
    """What the filter decided, and what it saw written on the page."""

    verdict: str
    reason: str
    text_found: tuple[str, ...] = field(default_factory=tuple)
    # What the second reader added: "" when none was asked, else clear, flagged or
    # unavailable. The codes are all of its answer that is kept; its words are not.
    second_look: str = ""
    teacher_codes: tuple[str, ...] = field(default_factory=tuple)

    @property
    def may_proceed(self) -> bool:
        return self.verdict in ("allow", "soften")

    @property
    def ledger_note(self) -> str:
        """The decision as a record may keep it: the verdict, and the second look as codes."""
        if not self.second_look:
            return self.verdict
        said = ",".join(self.teacher_codes) if self.second_look == "flagged" else self.second_look
        return f"{self.verdict} second-look:{said}"

    @property
    def carries_personal_text(self) -> bool:
        """Any writing on a child's drawing is treated as personal until proven otherwise."""
        return bool(self.text_found)


def _strip_fences(text: str) -> str:
    stripped = text.strip()
    if not stripped.startswith("```"):
        return stripped
    return stripped.split("\n", 1)[-1].rsplit("```", 1)[0].strip()


POINTS = ("door", "out")


@functools.cache
def second_look_rule():
    """nemotron.py beside this file: how the second reader's answer is read, and what it may decide."""
    name = "studio_safety_second_look_rule"
    spec = importlib.util.spec_from_file_location(name, Path(__file__).with_name("nemotron.py"))
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def _second_look(image_data_uri: str, second, point: str) -> Verdict | None:
    """What the second reader adds, as a verdict of its own; None when there is no second reader.

    A stop at the door is asked twice and stands only if the second look agrees, the same care the
    four verdicts take. On the way out one look is enough: a machine-made picture refused costs a
    retry, and nobody is told their work does not count.
    """
    if second is None:
        return None
    rule = second_look_rule()
    decide = rule.at_the_door if point == "door" else rule.on_the_way_out
    try:
        reading = rule.read_answer(second.look(image_data_uri, rule.QUESTIONS[point]))
        if not decide(reading).proceeds and point == "door":
            again = rule.read_answer(second.look(image_data_uri, rule.QUESTIONS[point]))
            reading = again if decide(again).proceeds else reading
    except ModelError:
        return Verdict("allow", "", second_look="unavailable")
    ruling = decide(reading)
    if not reading.unsafe:
        return Verdict("allow", "", second_look="clear")
    codes = ruling.teacher_codes or reading.categories or ("unspecified",)
    if ruling.proceeds:
        return Verdict("soften", "", second_look="flagged", teacher_codes=codes)
    return Verdict("unsafe", ruling.reason_code, second_look="flagged", teacher_codes=codes)


def screen(image_data_uri: str, client: VisionChatClient, attempts: int = 2, *, second=None,
           point: str = "door") -> Verdict:
    """The second reader first, when there is one, then the four verdicts; `point` is the door or the way out.

    A picture the second reader stops is not sent on to the four-verdict model at all. One it only
    flags comes in as "soften" at least, whatever the four verdicts call it, with its codes.
    """
    if point not in POINTS:
        raise ValueError(f"the studio screens at {POINTS}, not at {point!r}")
    looked = _second_look(image_data_uri, second, point)
    if looked is not None and not looked.may_proceed:
        return looked
    first = _four_verdicts(image_data_uri, client, attempts, LOOK_DEADLINE_S if point == "door" else None)
    if looked is None:
        return first
    verdict = "soften" if (first.verdict, looked.verdict) == ("allow", "soften") else first.verdict
    return replace(first, verdict=verdict, second_look=looked.second_look, teacher_codes=looked.teacher_codes)


def _four_verdicts(image_data_uri: str, client: VisionChatClient, attempts: int = 2,
                   deadline: float | None = None) -> Verdict:
    """Screen one image, and never refuse a child on one unstable answer.

    A verdict that lets the drawing through is taken as it comes: it costs one
    call, and the rest of the studio is what checks the result.

    A verdict that STOPS the child is asked a second time, and stands only if the
    second look agrees. Found in a live run: a child's scribble came back as "a
    digital graphic icon, not a child's drawing" and the child was told to go and
    show a real drawing — and the same image had passed the same filter an hour
    earlier. A filter that is unstable on a refusal is worse than a slow one,
    because the cost of its mistake falls on the child least able to argue.

    The second call costs nothing in the common case, because the common case is
    a drawing and a drawing is allowed on the first look.
    """
    first = _look_once(image_data_uri, client, attempts, deadline)
    if first.may_proceed:
        return first
    second = _look_once(image_data_uri, client, attempts, deadline)
    if second.may_proceed:
        return second
    return first


def _look_once(image_data_uri: str, client: VisionChatClient, attempts: int,
               deadline: float | None = None) -> Verdict:
    """One reading of the image. Raises rather than guessing when it will not answer.

    A filter that fails open is worse than one that fails loudly, so an
    unreadable answer is refused here instead of becoming an "allow".
    """
    last: Exception | None = None
    for _ in range(attempts):
        try:
            reply = _within(deadline, lambda: client.chat(
                SAFETY_PROMPT,
                [image_data_uri],
                system=JUDGE_SYSTEM,
                max_tokens=12000,
            ))
            payload = json.loads(_strip_fences(reply.text))
            if not isinstance(payload, dict):
                raise ValueError("not an object")
            verdict = str(payload.get("verdict", "")).lower()
            if verdict not in VERDICTS:
                # Never the model's words: this message becomes a ledger note and reaches the page.
                raise ValueError("unknown verdict")
            return Verdict(
                verdict=verdict,
                reason=str(payload.get("reason", "")),
                text_found=_written(payload.get("text_found")),
            )
        except (json.JSONDecodeError, ValueError) as error:
            last = error
    raise ModelRefused(f"the safety filter could not read an answer in {attempts} tries: {last}")


def _written(found) -> tuple[str, ...]:
    """What the screen says is written on the drawing, in whatever shape the model gave it. A lone string is one
    piece of writing, not a row of letters that redaction would skip, and null is none (code review)."""
    if found is None:
        return ()
    if not isinstance(found, (list, tuple)):
        found = [found]
    return tuple(str(item) for item in found if item is not None)


def _within(deadline: float, call):
    """The call's answer, or ModelUnavailable once `deadline` seconds pass without one; None waits it out.

    The call itself is left to finish on its own thread; nothing waits for it. On the plan a
    call costs nothing extra, and the StepFun client lets go of it by its own time limit.
    """
    if deadline is None:
        return call()
    pool = ThreadPoolExecutor(max_workers=1)
    try:
        return pool.submit(call).result(timeout=deadline)
    except NoAnswerYet:
        raise ModelUnavailable(f"the safety look gave no answer within {deadline:.0f} s") from None
    finally:
        pool.shutdown(wait=False)


def redact(text: str, found: tuple[str, ...]) -> str:
    """Remove anything written on the drawing from text about to be shown.

    The feedback prompt already forbids repeating a name. This is the
    deterministic half, because a rule the model merely agreed to is not a
    guarantee.
    """
    cleaned = text
    for written in sorted(found, key=len, reverse=True):
        piece = written.strip()
        if len(piece) > 1:
            cleaned = cleaned.replace(piece, "")
    return " ".join(_close_the_gap(cleaned).split())


# Quote marks left standing around nothing, in both alphabets, plus the Chinese
# phrases that introduce them. Real drawings came back reading
# "the orange house marked with" and "the blue characters" followed by an empty
# pair of quotes, because the writing was removed and its punctuation was not.
_LEFTOVERS = (
    ('\u201c\u201d', ""),
    ('\u300c\u300d', ""),
    ('\u2018\u2019', ""),
    ('""', ""),
    ("''", ""),
    ("()", ""),
    ("\uff08\uff09", ""),
)


def _close_the_gap(text: str) -> str:
    """Tidy what removing a name leaves behind.

    Deleting the words is the safety property; deleting the empty quotes they
    sat inside is what stops a child being read a sentence with a hole in it.
    """
    cleaned = text
    for pair, replacement in _LEFTOVERS:
        while pair in cleaned:
            cleaned = cleaned.replace(pair, replacement)
    # A possessive left hanging off a name that is no longer there.
    for orphan in (" 's", " \u2019s", " s'"):
        cleaned = cleaned.replace(orphan, "")
    for stray in ("\u7684\uff0c", " ,", " \u3002", " .", " \uff1f", " !"):
        cleaned = cleaned.replace(stray, stray.strip())
    return cleaned


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Screen an image before the studio sees it")
    parser.add_argument("image", help="path to the image")
    parser.add_argument("--slot", default="vlm.director")
    parser.add_argument("--profile", default="cloud")
    parser.add_argument("--second-slot", help="the slot of NVIDIA's safety model, asked before the four verdicts")
    parser.add_argument("--second-only", action="store_true", help="ask the second reader alone; no other model is built or called")
    parser.add_argument("--point", choices=POINTS, default="door")
    arguments = parser.parse_args(argv)
    if arguments.second_only and not arguments.second_slot:
        parser.error("--second-only needs --second-slot")

    load_dotenv()
    profile = load_profile(arguments.profile)
    second = build_safety_reader(resolve(arguments.second_slot, profile)) if arguments.second_slot else None
    started = time.monotonic()
    if arguments.second_only:
        result = _second_look(to_data_uri(arguments.image), second, arguments.point)
    else:
        client = build_client(resolve(arguments.slot, profile))
        result = screen(to_data_uri(arguments.image), client, second=second, point=arguments.point)
    print(f"{result.ledger_note}: {result.reason} ({time.monotonic() - started:.1f}s)")
    if result.text_found:
        print(f"writing on the page ({len(result.text_found)} pieces) will be redacted")


if __name__ == "__main__":
    main()
