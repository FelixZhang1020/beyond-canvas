"""shot-judge: the agent's eyes. One picture, one intention, one verdict in JSON."""
import json
from pathlib import Path

import pytest
from conftest import load_script

SCRIPT = Path("skills/shot-judge/scripts/judge.py")
SHOT = Path("skills/shot-judge/evals/files/stack-front.jpg")


@pytest.fixture(scope="module")
def module():
    return load_script(SCRIPT, "judge_script")


def test_a_pass_verdict_carries_what_was_seen(module, fake_client):
    reply = json.dumps({"seen": "a stack of boxes on a slab", "visible": True, "centred": True,
                        "readable": True, "verdict": "pass", "change": ""})
    client = fake_client([reply])
    verdict = module.judge(SHOT, "the whole stack, centred", client)
    assert verdict.verdict == "pass" and verdict.parsed and verdict.change == ""
    assert verdict.seen == "a stack of boxes on a slab"
    assert client.calls[0]["images"][0].startswith("data:image/")
    assert "the whole stack, centred" in client.calls[0]["prompt"]


def test_prose_around_the_json_is_tolerated(module, fake_client):
    reply = 'Sure. {"seen": "the ridge is cut off", "visible": true, "centred": false, ' \
            '"readable": true, "verdict": "fail", "change": "move the camera back"} Hope this helps.'
    verdict = module.judge(SHOT, "the ridge beam whole", fake_client([reply]))
    assert verdict.verdict == "fail" and verdict.change == "move the camera back" and verdict.parsed


def test_an_unreadable_answer_is_a_fail_that_says_so(module, fake_client):
    verdict = module.judge(SHOT, "anything", fake_client(["I cannot see the image."]))
    assert verdict.verdict == "fail" and not verdict.parsed
    assert "could not read" in verdict.change


def test_pass_needs_all_three_to_be_true(module):
    parsed = module.parse_verdict('{"visible": true, "centred": false, "readable": true, "verdict": "pass"}')
    assert module.settle(parsed)["verdict"] == "fail"


def test_a_judge_that_thought_its_budget_away_is_asked_once_more_with_room(module, fake_client):
    """The second from-nothing run's first look came back empty after 4,000 tokens of thinking."""
    from studio.core.errors import EmptyCompletion

    inner = fake_client([json.dumps({"seen": "a hall", "visible": True, "centred": True, "readable": True})])

    class Thinker:
        budgets = []

        def chat(self, prompt, images=(), *, system=None, max_tokens=None):
            self.budgets.append(max_tokens)
            if len(self.budgets) == 1:
                raise EmptyCompletion("no text")
            return inner.chat(prompt, images, system=system, max_tokens=max_tokens)

    client = Thinker()
    verdict = module.judge(SHOT, "a hall", client)
    assert verdict.verdict == "pass" and client.budgets == [module.MAX_TOKENS, 2 * module.MAX_TOKENS]
