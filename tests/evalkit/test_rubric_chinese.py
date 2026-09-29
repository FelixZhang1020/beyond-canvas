"""What the first Chinese run found.

The rubric shipped with a bilingual lexicon and had never once been run in
Chinese. Both marker lists had been widened twice on the English side from live
sweeps; the Chinese side of each was written once and never measured. Six real
plaster studies from the art centre found six failures in six questions that
were all correct.

Every question below is verbatim from that run. They are the fixtures the
generated ones could not be: a model's own Chinese, not a translation of an
English test case.
"""

import pytest

from evalkit.rubric.loop import rule_12_question_enters_the_process
from evalkit.rubric.structural import rule_9_ends_with_open_question

OPEN_QUESTIONS_IT_CALLED_CLOSED = [
    "画的时候，哪部分的明暗交界线最难把握？",
    "在画这些几何体时，你调整最多的部分是哪个？",
    "在塑造球体体积感时，你调整明暗交界线位置的过程是怎样的？",
    "在画这些平面时，你觉得自己最难处理的是哪一个部分？",
]

PROCESS_QUESTIONS_IT_CALLED_OFF_TOPIC = [
    "在塑造球体体积感时，你调整明暗交界线位置的过程是怎样的？",
    "在处理颧骨到下颌的体面转折时，你用了什么观察方法？",
]


@pytest.mark.parametrize("question", OPEN_QUESTIONS_IT_CALLED_CLOSED)
def test_a_chinese_open_question_is_not_read_as_closed(question):
    """Every one of these hands the question back to the child."""
    result = rule_9_ends_with_open_question(question)
    assert result.status == "pass", result.evidence


@pytest.mark.parametrize("question", PROCESS_QUESTIONS_IT_CALLED_OFF_TOPIC)
def test_a_chinese_question_about_process_counts_as_one(question):
    """One of these contains the word for "process" and the other the word for
    "method", and both were failed for not asking about process."""
    result = rule_12_question_enters_the_process(question)
    assert result.status == "pass", result.evidence


def test_a_closed_chinese_question_is_still_closed():
    """The widening must not turn the rule off."""
    result = rule_9_ends_with_open_question("这是你画的吗？")
    assert result.status == "fail"


def test_a_question_about_the_picture_is_not_a_question_about_process():
    """The sketch entrance asks how it was made, not what is happening in it."""
    result = rule_12_question_enters_the_process("石膏后面住着谁呢？")
    assert result.status == "fail"


WORLD_QUESTIONS_IT_CALLED_OFF_TOPIC = [
    "这条河要流向哪里？",
    "这只小鸟要飞到什么地方去呢？",
    "房子里住着谁呢？",
]


@pytest.mark.parametrize("question", WORLD_QUESTIONS_IT_CALLED_OFF_TOPIC)
def test_a_chinese_question_about_the_picture_reaches_inside_it(question):
    """The first is verbatim from the run. The English list has carried "where
    is" and "who" from the start; the Chinese list had neither."""
    from evalkit.rubric.loop import rule_12_question_enters_the_world

    result = rule_12_question_enters_the_world(question)
    assert result.status == "pass", result.evidence


# Verbatim from a run where rule 12 refused 15 of 74 closing questions and 14 of
# them were the question the entrance asks for. The marker lists had been widened five
# times by then, each time by a question a person would pass, so these are here to hold
# the judge that replaced the widening rather than to widen them a sixth time.
PROCESS_QUESTIONS_REFUSED_ON_2026_09_15 = [
    "你在画的时候是怎么决定人物和狗的大小的？",
    "你画的时候是怎么想到给怪兽加尖牙的呢？",
    "你在绘制时是如何决定嘴巴位置和形状的？",
    "你是怎么确定眼睛之间的间距的？",
    "你在画这个球的时候是怎么考虑明暗关系的？",
]

WORLD_QUESTIONS_REFUSED_ON_2026_09_15 = [
    "这座桥的那边有什么？",
    "广场上的人在看什么呢？",
    "它翅膀里带着什么呢？",
]


class Judging:
    """A director that answers ONE of the two question judges, and keeps what it was asked.

    One field, not both: a judge that answered `process` and `world` alike would score a
    rule wired to the wrong entrance's prompt as a pass, which is the wiring these tests
    are here to hold.
    """

    def __init__(self, field, verdict=True):
        self.field, self.verdict, self.calls = field, verdict, []

    def chat(self, prompt, images=(), *, system=None, max_tokens=None):
        from studio.providers.base import ChatResult

        self.calls.append(prompt)
        answer = "true" if self.verdict else "false"
        return ChatResult(f'{{"{self.field}": {answer}, "why": "judged"}}',
                          1, 1, 0, 0.0, 0.0, "fake", "fake")


@pytest.mark.parametrize("question", PROCESS_QUESTIONS_REFUSED_ON_2026_09_15)
def test_a_process_question_the_markers_miss_is_put_to_the_judge(question):
    """Every one asks how the student decided something, and carries none of the words
    the list holds. A sixth widening would have to guess the seventh."""
    judge = Judging("process")
    result = rule_12_question_enters_the_process(question, client=judge)
    assert result.status == "pass", result.evidence
    assert judge.calls, "the markers missed it and nothing asked the judge"
    assert "OWN WORK" in judge.calls[0], "the sketch entrance asked the wrong judge"


@pytest.mark.parametrize("question", WORLD_QUESTIONS_REFUSED_ON_2026_09_15)
def test_a_world_question_the_markers_miss_is_put_to_the_judge(question):
    from evalkit.rubric.loop import rule_12_question_enters_the_world

    judge = Judging("world")
    result = rule_12_question_enters_the_world(question, client=judge)
    assert result.status == "pass", result.evidence
    assert "world INSIDE the picture" in judge.calls[0], "the colour entrance asked the wrong judge"


def test_the_judge_can_still_refuse_a_question_that_is_off_the_entrance():
    """The fallback is a second opinion, not an amnesty."""
    judge = Judging("process", verdict=False)
    result = rule_12_question_enters_the_process("这幅画里的狗叫什么名字？", client=judge)
    assert result.status == "fail"
    assert judge.calls


@pytest.mark.parametrize("answer", ["false", "no", 0])
def test_a_judge_that_says_no_in_words_is_still_saying_no(answer):
    """Models quote their booleans. A string "false" read as a pass would refuse nothing."""
    import json as json_module

    class Quoting(Judging):
        def chat(self, prompt, images=(), *, system=None, max_tokens=None):
            from studio.providers.base import ChatResult

            self.calls.append(prompt)
            return ChatResult(json_module.dumps({"process": answer}), 1, 1, 0, 0.0, 0.0, "fake", "fake")

    assert rule_12_question_enters_the_process(
        "你是怎么确定眼睛之间的间距的？", client=Quoting("process")).status == "fail"


def test_a_question_the_markers_recognise_costs_no_model_call():
    judge = Judging("process")
    result = rule_12_question_enters_the_process("你调整最多的部分是哪个？", client=judge)
    assert result.status == "pass"
    assert not judge.calls, "the markers matched; asking a model as well is money for nothing"


def test_without_a_judge_the_markers_decide_alone():
    """Offline, and in every test that supplies no client: unchanged behaviour."""
    assert rule_12_question_enters_the_process("你是怎么确定眼睛之间的间距的？").status == "fail"


def test_the_presumption_judge_is_told_a_recognisable_shape_is_not_a_guess():
    """Rule 4 is a red line: a reply that fails it is never shown. On twelve real
    paintings it fired on five, for calling a sun a sun and a house a house —
    while rule 3 requires naming two things that are really there. The judge was
    told what a presumption is and never what one is not."""
    from evalkit.rubric.assisted import PRESUMPTION_PROMPT

    for phrase in ("is a sun", "is a house", "is a bird", "is a dog"):
        assert phrase in PRESUMPTION_PROMPT, phrase


def test_the_presumption_judge_is_told_which_mistake_is_worse():
    from evalkit.rubric.assisted import PRESUMPTION_PROMPT

    assert "the answer is an empty list" in PRESUMPTION_PROMPT
    assert "costs a child their answer" in PRESUMPTION_PROMPT
