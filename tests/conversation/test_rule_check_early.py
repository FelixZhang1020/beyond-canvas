"""In class, a line that has already crossed a red line without a model goes back at once.

Measured with Qwen3.6 writing: a line took under a second to write and 20-60 s to judge,
and a reply that failed rule 13 (it used 1 of the child's 14 words) still waited for every judge
before it was rewritten. The studio's own checks (rules 1, 5, 6, 7, 8 and 13) need no model; when one of
them has already refused the line, the judges are not asked. A benchmark still asks every judge.
"""
from evalkit.rubric import run_rubric
from studio.conversation.conversation import Conversation
from studio.core.ledger import Ledger
from studio.providers.base import ChatResult

DRAWING = "skills/art-feedback/evals/files/dog-sun.png"
IMAGE = "data:image/png;base64,iVBORw0KGgo="
CHILD = "the dog is running to find his friend in the park"
DEAF = "What a lovely picture. What colours did you like best?"   # nothing the child said comes back
HEARD = "The dog is running to find his friend. Which way is the park?"


class Judge:
    """A judge that answers every rule with a pass, and counts how often it was asked."""

    def __init__(self):
        self.asked = 0

    def chat(self, prompt, images=(), *, system=None, max_tokens=None):
        self.asked += 1
        return ChatResult('{"grounded": ["a", "b"], "presumptive": [], "invented": []}',
                          1, 1, 0, 0.0, 0.0, "fake", "judge")


def test_in_class_a_reply_that_did_not_hear_the_child_is_not_sent_to_the_judges():
    judge = Judge()
    report = run_rubric(DEAF, entrance="colour", image_data_uri=IMAGE, client=judge, child_said=CHILD,
                        stop_at_local_red_line=True)
    assert not report.fit_to_show and 13 in {r.rule for r in report.crossed}
    assert judge.asked == 0, "the judges were asked about a line that was already refused"
    assert {r.rule for r in report.results if r.status == "skip" and "not asked" in r.evidence} == {4, 14}


def test_in_class_a_reply_that_passes_the_studios_own_checks_is_still_judged():
    judge = Judge()
    run_rubric(HEARD, entrance="colour", image_data_uri=IMAGE, client=judge, child_said=CHILD,
               stop_at_local_red_line=True)
    assert judge.asked >= 2, "a line the studio's checks passed must still go to the judges"


def test_a_benchmark_still_asks_every_judge_about_a_refused_line():
    judge = Judge()
    run_rubric(DEAF, entrance="colour", image_data_uri=IMAGE, client=judge, child_said=CHILD)
    assert judge.asked >= 2


def test_the_class_gate_asks_for_the_early_stop(tmp_path):
    """Through the conversation's own gate, as a class runs it: the failing reply never reaches Step."""
    judge = Judge()
    talk = Conversation(DRAWING, Ledger(tmp_path / "ledger.jsonl"), entrance="colour", studio=Judge(),
                        director=judge)
    ok, reason = talk._gate(DEAF, CHILD)
    assert not ok and "rule 13" in reason and judge.asked == 0


def test_an_opening_that_crossed_a_red_line_does_not_wait_for_the_question_judge_either():
    """Code review: rule 12 runs its judge in line, before the pooled judges were stopped."""
    judge = Judge()
    # A question no marker recognises, so rule 12 asks its judge whenever it has a client.
    run_rubric("You are so talented. Could the boat sail to the moon?", entrance="colour",
               image_data_uri=IMAGE, client=judge, stop_at_local_red_line=True)
    assert judge.asked == 0, "a judge was asked about an opening already refused for praising talent"
