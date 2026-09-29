from __future__ import annotations

from collections.abc import Sequence

from evalkit.rubric.lexicons import COMPARISON, CORRECTION, DIMINISHING, PERSON_PRAISE, REALISM
from evalkit.rubric.report import RuleResult
from evalkit.rubric.text import detect_lang, mentions

RULE_1 = "praises the process, not the person"
RULE_5 = "makes no comparison"
RULE_6 = "corrects nothing"
RULE_7 = "does not police realism"
RULE_8 = "uses no diminishing words"


def _forbid_phrases(text: str, table: dict[str, Sequence[str]], rule: int, name: str) -> RuleResult:
    lowered = text.lower()
    lang = detect_lang(text)
    hit = next((phrase for phrase in table[lang] if mentions(lowered, phrase, lang)), None)
    if hit:
        return RuleResult(rule, name, "fail", f"contains the forbidden phrase {hit!r}")
    return RuleResult(rule, name, "pass", "no forbidden phrase present")


def rule_1_process_not_person(text: str) -> RuleResult:
    """Praise for effort survives failure; praise for talent does not."""
    lowered = text.lower()
    for pattern in PERSON_PRAISE[detect_lang(text)]:
        found = pattern.search(lowered)
        if found:
            return RuleResult(1, RULE_1, "fail", f"praises the child, not the work: {found.group(0)!r}")
    return RuleResult(1, RULE_1, "pass", "praise is attached to actions and choices")


def rule_5_no_comparison(text: str) -> RuleResult:
    return _forbid_phrases(text, COMPARISON, 5, RULE_5)


def rule_6_no_correction(text: str) -> RuleResult:
    return _forbid_phrases(text, CORRECTION, 6, RULE_6)


def rule_7_no_realism_policing(text: str) -> RuleResult:
    return _forbid_phrases(text, REALISM, 7, RULE_7)


def rule_8_no_diminishing(text: str) -> RuleResult:
    return _forbid_phrases(text, DIMINISHING, 8, RULE_8)
