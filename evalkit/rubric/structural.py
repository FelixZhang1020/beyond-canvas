from __future__ import annotations

from evalkit.rubric.lexicons import (
    CLOSED_QUESTION_MARKERS_ZH,
    EVALUATIVE_WORDS,
    INVITATIONS_ZH,
    OBSERVATION_OPENERS,
    OPEN_MARKERS,
    YES_NO_OPENERS_EN,
)
from evalkit.rubric.report import RuleResult
from evalkit.rubric.text import detect_lang, mentions, sentences

# The phrase lists these rules read live in lexicons.py, which is the one file
# allowed to hold Chinese. Import the names directly rather than the package:
# evalkit/rubric/__init__.py imports this module, so reaching back through the
# package would re-enter it mid-initialisation.

# One limit for everyone, in English words and Chinese characters per sentence.
# The age bands were removed: section 5a says age is not modelled,
# because the operator's split at third grade was an illustration rather than a
# specification. The entrance fork, sketch or colour, replaced both the age split
# and the teacher's switch: whether to critique is decided by the kind of work,
# not by who drew it. This is now a single tunable pair,
# and 25 words sits where the middle band was: loose enough not to fail good
# feedback for an older child, tight enough that a five-year-old can follow it.
SENTENCE_LIMIT_WORDS = 25
SENTENCE_LIMIT_CHARS = 45

RULE_2 = "opens with a neutral observation"
RULE_9 = "ends with an open question"
RULE_10 = "keeps sentences short"


def rule_2_observation_opener(text: str) -> RuleResult:
    """See-Think-Wonder puts seeing first: describe before interpreting."""
    lang = detect_lang(text)
    parts = sentences(text)
    first = parts[0] if parts else ""
    lowered = first.lower()
    if not any(lowered.startswith(opener) for opener in OBSERVATION_OPENERS[lang]):
        return RuleResult(2, RULE_2, "fail", f"does not open with an observation: {first[:60]!r}")
    hit = next((word for word in EVALUATIVE_WORDS[lang] if mentions(lowered, word, lang)), None)
    if hit:
        return RuleResult(2, RULE_2, "fail", f"the opening carries the judgement word {hit!r}")
    return RuleResult(2, RULE_2, "pass", f"opens with {first[:60]!r}")


def rule_9_ends_with_open_question(text: str) -> RuleResult:
    """A closed question ends the exchange; an open one hands it back."""
    lang = detect_lang(text)
    stripped = text.strip()
    if not stripped.endswith(("?", "？")):
        return RuleResult(9, RULE_9, "fail", "the feedback does not end with a question")
    last = sentences(stripped)[-1]
    lowered = last.lower()
    # A question with a prepared A-or-B answer can contain an open marker and
    # still leave no room for the child's own idea. Observed in a colour reply
    # that asked whether the deer would catch a letter or read it first.
    if lang == "zh" and "还是" in last:
        return RuleResult(9, RULE_9, "fail", f"forced choice: {last!r}")
    # A Chinese question that ends in the yes-or-no particle is answered yes or no, whatever it asks about
    # inside: "does the brother know where she is now?" passed on its "where" (replay). Only an
    # invitation to tell stays open, as the English "can you tell me what..." below does.
    if lang == "zh" and last.endswith(CLOSED_QUESTION_MARKERS_ZH) and not any(w in last for w in INVITATIONS_ZH):
        return RuleResult(9, RULE_9, "fail", f"closed yes or no question: {last!r}")
    # An open marker wins over the grammatical opener. "Can you tell me what you
    # were making?" is a yes-or-no question only on paper; no child answers it
    # with "yes". Testing the opener first flagged it closed and cost the model a
    # rule it had actually followed, as measured.
    if any(mentions(lowered, marker, lang, whole=True) for marker in OPEN_MARKERS[lang]):
        return RuleResult(9, RULE_9, "pass", f"ends with {last!r}")
    closed_zh = lang == "zh" and any(mark in last for mark in CLOSED_QUESTION_MARKERS_ZH)
    closed_en = lang == "en" and lowered.startswith(YES_NO_OPENERS_EN)
    if closed_zh or closed_en:
        return RuleResult(9, RULE_9, "fail", f"closed yes or no question: {last!r}")
    return RuleResult(9, RULE_9, "fail", f"the question has no open marker: {last!r}")


def rule_10_short_sentences(text: str) -> RuleResult:
    """Feedback a child cannot follow is feedback that did not happen."""
    lang = detect_lang(text)
    limit = SENTENCE_LIMIT_WORDS if lang == "en" else SENTENCE_LIMIT_CHARS
    for sentence in sentences(text):
        size = len(sentence.split()) if lang == "en" else len(sentence)
        if size > limit:
            return RuleResult(
                10, RULE_10, "fail",
                f"a sentence runs {size} units against the {limit} limit: {sentence[:50]!r}",
            )
    return RuleResult(10, RULE_10, "pass", f"every sentence is within {limit} units")
