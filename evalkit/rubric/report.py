from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

Status = Literal["pass", "fail", "skip"]

# The rules whose violation is HARM to the child rather than a flaw in the
# response. Section 3.6 of the requirements calls these 红线 — red lines — and a
# red line cannot be averaged away: one of these failing refuses the whole
# response however well it scores on everything else.
#
#   1  praising the child rather than the choice: the motivation killer the
#      whole product exists to avoid
#   4  asserting what an ambiguous shape is: tells the child their meaning
#      did not come across
#   5  comparing or ranking one child against another
#   6  correcting the work on the colour entrance, which section 3.1 calls
#      harm in so many words
#   7  policing whether the drawing looks real
#   8  diminishing words: simple, messy, childish, just a scribble
#  13  a reply that does not use the child's words, which is a reply that
#      could have been written before they spoke
#  14  inventing the child's story, or correcting it
#
# The rest — opening with an observation, naming two details, ending on an open
# question, sentence length, serving the lesson, the question reaching inside
# the picture — are the quality of the response. They average.
RED_LINES: frozenset[int] = frozenset({1, 4, 5, 6, 7, 8, 13, 14})


@dataclass(frozen=True)
class RuleResult:
    """One rule's verdict on one piece of feedback.

    Evidence quotes the offending words rather than restating the rule, so a
    failure tells the author what to change.
    """

    rule: int
    name: str
    status: Status
    evidence: str


@dataclass(frozen=True)
class RubricReport:
    results: tuple[RuleResult, ...]

    @property
    def scored(self) -> tuple[RuleResult, ...]:
        """Rules that actually ran. Skipped rules must not inflate a score."""
        return tuple(result for result in self.results if result.status != "skip")

    @property
    def failures(self) -> tuple[RuleResult, ...]:
        return tuple(result for result in self.results if result.status == "fail")

    @property
    def crossed(self) -> tuple[RuleResult, ...]:
        """Red lines that failed. One of these refuses on its own."""
        return tuple(result for result in self.failures if result.rule in RED_LINES)

    @property
    def passed(self) -> bool:
        return not self.failures

    @property
    def fit_to_show(self) -> bool:
        """Whether a child may see this at all, before any score is considered."""
        return not self.crossed

    @property
    def pass_rate(self) -> float:
        scored = self.scored
        if not scored:
            return 0.0
        return sum(result.status == "pass" for result in scored) / len(scored)
