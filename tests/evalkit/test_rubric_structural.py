import pytest

from evalkit.rubric.structural import (
    rule_2_observation_opener,
    rule_9_ends_with_open_question,
    rule_10_short_sentences,
)
from evalkit.rubric.text import detect_lang, sentences

GOOD_EN = (
    "I notice your dog is purple and your sun has pointy triangle rays. "
    "I also see two people holding hands under the sky. "
    "What are your dog and the two people doing together?"
)
GOOD_ZH = (
    "我注意到你画的小狗是紫色的，太阳的光芒是尖尖的三角形。"
    "我还看到两个人手拉着手站在天空下面。"
    "跟我讲讲你的小狗和这两个人吧，他们在一起做什么呢？"
)


def test_detect_lang_reads_a_handful_of_chinese_characters():
    assert detect_lang(GOOD_ZH) == "zh"
    assert detect_lang(GOOD_EN) == "en"


def test_sentences_split_on_both_alphabets():
    assert len(sentences(GOOD_EN)) == 3
    assert len(sentences(GOOD_ZH)) == 3


@pytest.mark.parametrize("text", [GOOD_EN, GOOD_ZH])
def test_a_neutral_opener_passes_rule_2(text):
    assert rule_2_observation_opener(text).status == "pass"


def test_an_evaluative_opener_fails_rule_2():
    result = rule_2_observation_opener("What a beautiful painting! I see a purple dog. Why?")
    assert result.status == "fail"


def test_an_evaluative_word_inside_the_opener_fails_rule_2():
    result = rule_2_observation_opener("I see a beautiful purple dog. What is it doing there?")
    assert result.status == "fail"
    assert "beautiful" in result.evidence


def test_a_chinese_evaluative_opener_fails_rule_2():
    assert rule_2_observation_opener("你的画真漂亮。我看到小狗。你想说什么呢？").status == "fail"


@pytest.mark.parametrize("text", [GOOD_EN, GOOD_ZH])
def test_an_open_question_passes_rule_9(text):
    assert rule_9_ends_with_open_question(text).status == "pass"


def test_no_question_at_all_fails_rule_9():
    assert rule_9_ends_with_open_question("I see a purple dog. I see a sun.").status == "fail"


def test_an_english_yes_no_question_fails_rule_9():
    assert rule_9_ends_with_open_question("I see a purple dog. Is that your pet?").status == "fail"


def test_a_chinese_yes_no_question_fails_rule_9():
    assert rule_9_ends_with_open_question("我看到一只紫色小狗。这是你的宠物吗？").status == "fail"


def test_how_long_and_how_many_are_open_questions():
    """Probe on the Spark: 「他们还要走多久才能找到妈妈？」 was refused as closed."""
    assert rule_9_ends_with_open_question("他们还要走多久才能找到妈妈？").status == "pass"
    assert rule_9_ends_with_open_question("路上一共有多少棵树？").status == "pass"


def test_a_chinese_forced_choice_does_not_pass_as_an_open_question():
    closed = rule_9_ends_with_open_question("小鹿会先接住信，还是先读信上写了什么？")
    assert closed.status == "fail" and "forced choice" in closed.evidence
    assert rule_9_ends_with_open_question("小鹿看到船靠近时会怎么做？").status == "pass"


def test_an_open_question_wearing_a_yes_no_opener_still_passes_rule_9():
    """Measured: the grader failed this real reply, which follows the
    rule. Grammatically it opens yes-or-no; no child answers it with "yes"."""
    result = rule_9_ends_with_open_question(
        "I see orange lines. Can you tell me what you were making?"
    )
    assert result.status == "pass"


def test_a_request_with_no_open_marker_still_fails_rule_9():
    """The fix must not turn every question into a pass."""
    result = rule_9_ends_with_open_question(
        "I see a blank page. Could you send me a photo of it?"
    )
    assert result.status == "fail"


def test_a_short_sentence_passes_rule_10():
    assert rule_10_short_sentences("I see big orange loops. What did your hand do?").status == "pass"


def test_a_long_sentence_fails_rule_10():
    long_text = "I see " + " ".join(["orange"] * 30) + ". What did your hand do?"
    result = rule_10_short_sentences(long_text)
    assert result.status == "fail"
    assert "25" in result.evidence


def test_one_limit_applies_to_everyone_now():
    """Age bands were removed: no sentence gets a longer allowance."""
    long_text = "I see " + " ".join(["orange"] * 28) + ". What did your hand do?"
    assert rule_10_short_sentences(long_text).status == "fail"


def test_a_question_word_hidden_inside_another_word_does_not_pass_rule_9():
    """'who' sits at the front of 'whole', which let a closed question through."""
    result = rule_9_ends_with_open_question("I see a drawing. Is the whole page finished?")
    assert result.status == "fail"


def test_an_evaluative_word_hidden_inside_another_word_does_not_fail_rule_2():
    """'cute' sits inside 'acute', which a sketch critique says often."""
    result = rule_2_observation_opener("I see the acute angle where the two edges meet. What is it?")
    assert result.status == "pass"


def test_a_chinese_question_ending_in_ma_is_closed_even_when_it_asks_where():
    """Replayed class conversation: it passed on its "where"."""
    assert rule_9_ends_with_open_question("那个哥哥知道妈妈现在在什么地方吗？").status == "fail"
    assert rule_9_ends_with_open_question("你能说说他们在做什么吗？").status == "pass"
    assert rule_9_ends_with_open_question("他们在做什么？").status == "pass"
