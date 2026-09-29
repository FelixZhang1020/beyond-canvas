"""What NVIDIA's safety model said about a picture, and what the studio does about it.

Nemotron 3.5 Content Safety is a second, dedicated reader beside the four-verdict check in
safety.py. It answers in up to three lines (`User Safety`, `Response Safety`, `Safety Categories`),
after a `<think>` trace when it is given a policy of our own. No model is called here: this file
reads that answer and applies the studio's rule, so the rule is tested without the weights. The
model runs on NVIDIA's stock rules (operator: measured as lenient on children's dark
drawings as our own policy, twelve times faster, and trained to flag lifelike gore); `inference_policy()`
is the fallback, kept for the day the stock rules wrongly flag a child's drawing.

The rule (operator). At the door only sexual content stops a drawing; any other flag
lets it in, answered warmly, with a code for the teacher and never the model's words about the
child. On the way out any flag refuses the machine-made picture, which costs one retry. A photo, a
blank page and a name on the page stay the four-verdict check's business.

It does not promise that the model catches harmful pictures. The generated test drawings can only
show that it does not turn a child away.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from studio.core.errors import ModelRefused

POLICY_FILE = Path(__file__).resolve().parent.parent / "references" / "childrens-studio-policy.md"

# What the studio asks beside the picture, at each of the two points.
QUESTIONS = {
    "door": "A teacher has brought this picture to a children's art class. Is it fit to be seen and talked about there?",
    "out": "A machine made this picture from a child's drawing. Is it fit to show to that child and the class?",
}

# The 23 names the model can give (NVIDIA's content-safety taxonomy), each as the code a ledger keeps.
CODES = {
    "violence": "violence", "sexual": "sexual", "criminal planning/confessions": "criminal_planning",
    "guns and illegal weapons": "weapons", "controlled/regulated substances": "controlled_substances",
    "suicide and self harm": "self_harm", "sexual (minor)": "sexual_minor", "hate/identity hate": "hate_identity",
    "pii/privacy": "pii_privacy", "harassment": "harassment", "threat": "threat", "profanity": "profanity",
    "needs caution": "needs_caution", "other": "other", "manipulation": "manipulation",
    "fraud/deception": "fraud_deception", "malware": "malware", "high risk gov decision making": "high_risk_gov",
    "political/misinformation/conspiracy": "political_misinfo", "copyright/trademark/plagiarism": "ip_violation",
    "unauthorized advice": "unauthorized_advice", "illegal activity": "illegal_activity",
    "immoral/unethical": "immoral_unethical",
}
STOPS_A_DRAWING = ("sexual", "sexual_minor")


@dataclass(frozen=True)
class Reading:
    """The model's answer, as codes. Its own words are dropped here and go no further."""

    unsafe: bool
    categories: tuple[str, ...] = ()


@dataclass(frozen=True)
class Ruling:
    """What the studio does. `teacher_codes` is all a teacher or a ledger ever sees of the reading."""

    proceeds: bool
    soften: bool = False
    teacher_codes: tuple[str, ...] = ()
    reason_code: str = ""


def inference_policy() -> str:
    """The policy text the model reads, cut out of the Markdown policy people read."""
    text = POLICY_FILE.read_text(encoding="utf-8")
    return text.split("<!-- policy:start -->")[1].split("<!-- policy:end -->")[0].strip()


def read_answer(reply: str) -> Reading:
    """Read the lines after the thinking. Raises rather than guessing when there is no verdict:
    a filter that fails open is worse than one that fails loudly."""
    if "<think>" in reply and "</think>" not in reply:
        raise ModelRefused("the safety model was still thinking when its answer ended")
    lines = [line.strip() for line in reply.rsplit("</think>", 1)[-1].splitlines()]
    verdict = next((line.split(":", 1)[1].strip().lower() for line in lines if line.lower().startswith("user safety:")), "")
    if verdict not in ("safe", "unsafe"):
        raise ModelRefused("the safety model gave no verdict")   # never its words: this becomes a ledger note
    named = next((line.split(":", 1)[1] for line in lines if line.lower().startswith("safety categories:")), "")
    codes = tuple(dict.fromkeys(CODES.get(name.strip().lower(), "other") for name in named.split(",") if name.strip()))
    return Reading(unsafe=verdict == "unsafe", categories=codes if verdict == "unsafe" else ())


def at_the_door(reading: Reading) -> Ruling:
    """A child's drawing coming in."""
    if not reading.unsafe:
        return Ruling(proceeds=True)
    if any(code in STOPS_A_DRAWING for code in reading.categories):
        return Ruling(proceeds=False, reason_code="nemotron_sexual")
    return Ruling(proceeds=True, soften=True, teacher_codes=reading.categories or ("unspecified",))


def on_the_way_out(reading: Reading) -> Ruling:
    """A machine-made picture about to be shown."""
    if not reading.unsafe:
        return Ruling(proceeds=True)
    return Ruling(proceeds=False, reason_code="nemotron_flagged")
