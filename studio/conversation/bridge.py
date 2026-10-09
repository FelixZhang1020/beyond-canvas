"""The quick line a child hears while the studio is still looking.

Operator. Step 3.7 Flash always thinks before it answers (StepFun's
staff: the model has no non-thinking mode; nine switches tried on the Spark, none
worked), so a reply to a child took 17 s before its first word. The subscription's
`stepaudio-2.5-chat` answers text in about half a second and cannot see pictures.

So the fast model only bridges: it writes one sentence saying the child's own
words back, and the harness adds that the studio is looking again. It is never
asked about the drawing and never sees it. Measured on the Spark, left
to write the whole line it added rhetorical questions, details ("her hair is
sparkly") and once turned the child's "it" into "this cat", so it writes the
echo alone. The real reply, written by
Step 3.7 Flash and passed by the rule judges, follows. The bridge is spoken before
any model judge has read it, which is why it is held to what can be checked at
once: the child's words must be in it, it must be short, it must not ask, and the
word-list rules must pass. Anything else, or any model failure, becomes a fixed line.
"""

from __future__ import annotations

import re
from pathlib import Path

from evalkit.rubric.lexical import rule_1_process_not_person, rule_5_no_comparison, rule_8_no_diminishing
from evalkit.rubric.loop import rule_13_reply_uses_the_childs_words
from evalkit.rubric.structural import rule_10_short_sentences
from studio.core.errors import ModelError
from studio.conversation.words import say

PROMPTS = Path(__file__).parents[1] / "prompts"
# Stage directions the voice model adds on its own, in full-width or ASCII brackets: "(smiling)", "*nods*".
DIRECTIONS = re.compile("[\uff08(\u3010\\[][^\uff09)\u3011\\]]*[\uff09)\u3011\\]]|\\*[^*]*\\*")
QUOTES = "\"'\u201c\u201d\u2018\u2019\u300c\u300d"   # a line it wrapped in quotation marks is still one line
LONGEST = {"zh": 30, "en": 120}   # characters of the echo; the prompt asks for 25 and 15 words
CHECKS = (rule_1_process_not_person, rule_5_no_comparison, rule_8_no_diminishing, rule_10_short_sentences)


def prompt(said: str, language: str) -> str:
    name = "bridge-zh.txt" if language == "zh" else "bridge-en.txt"
    return (PROMPTS / name).read_text(encoding="utf-8").replace("{said}", said.strip())


def fits(text: str, said: str, language: str) -> bool:
    """Whether a bridge may be spoken with no model judge having read it."""
    if not text or len(text) > LONGEST["zh" if language == "zh" else "en"] or re.search("[?\uff1f]", text):
        return False
    if rule_13_reply_uses_the_childs_words(text, said).status != "pass":
        return False
    return all(check(text).status != "fail" for check in CHECKS)


def line(client, said: str, language: str) -> tuple[str, bool]:
    """The bridge to speak, and whether the model wrote its echo (False: the fixed line)."""
    if client is not None and said.strip():
        try:
            echo = DIRECTIONS.sub("", client.chat(prompt(said, language)).text).strip().strip(QUOTES).strip()
        except ModelError:
            echo = ""
        if fits(echo, said, language):
            joiner = "" if language == "zh" else " "
            return echo + joiner + say(language, "bridge_tail"), True
    return say(language, "bridge"), False
