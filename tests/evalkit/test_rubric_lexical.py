import pytest

from evalkit.rubric.lexical import (
    rule_1_process_not_person,
    rule_5_no_comparison,
    rule_6_no_correction,
    rule_7_no_realism_policing,
    rule_8_no_diminishing,
)

CLEAN_EN = (
    "I notice you chose purple for the dog and pressed hard on the sun's rays. "
    "What made you pick those colours?"
)
CLEAN_ZH = "我注意到你给小狗选了紫色，太阳的光芒画得很用力。你为什么想用这些颜色呢？"

PERSON_PRAISE = [
    "I see a purple dog. You're so talented! What is it doing?",
    "I see a purple dog. You are a real artist. What is it doing?",
    "我看到一只紫色的小狗。你真有天赋！你想说什么呢？",
    "我看到一只紫色的小狗。你真是个小画家。你想说什么呢？",
]
COMPARISONS = [
    "I see a purple dog. This is better than your last one. What is it doing?",
    "我看到一只紫色的小狗。这比其他小朋友画得好。你想说什么呢？",
]
CORRECTIONS = [
    "I see a purple dog. It should have four legs. What is it doing?",
    "I see a purple dog. You forgot the tail. What is it doing?",
    "我看到一只紫色的小狗。你忘了画尾巴。你想说什么呢？",
]
REALISM = [
    "I see a purple dog. It looks so realistic. What is it doing?",
    "我看到一只紫色的小狗。画得真像真的。你想说什么呢？",
]
DIMINISHING = [
    "I see a purple dog. It is just a simple sketch. What is it doing?",
    "我看到一只紫色的小狗。有点乱，不过很有趣。你想说什么呢？",
]


@pytest.mark.parametrize("text", [CLEAN_EN, CLEAN_ZH])
def test_clean_feedback_passes_every_phrase_rule(text):
    for check in (
        rule_1_process_not_person,
        rule_5_no_comparison,
        rule_6_no_correction,
        rule_7_no_realism_policing,
        rule_8_no_diminishing,
    ):
        assert check(text).status == "pass", check.__name__


@pytest.mark.parametrize("text", PERSON_PRAISE)
def test_trait_praise_fails_rule_1(text):
    assert rule_1_process_not_person(text).status == "fail"


def test_process_praise_passes_rule_1():
    assert rule_1_process_not_person("I see red loops. You worked hard on them. What next?").status == "pass"


@pytest.mark.parametrize("text", COMPARISONS)
def test_comparison_fails_rule_5(text):
    assert rule_5_no_comparison(text).status == "fail"


@pytest.mark.parametrize("text", CORRECTIONS)
def test_correction_fails_rule_6(text):
    assert rule_6_no_correction(text).status == "fail"


def test_telling_a_child_their_story_is_not_in_the_picture_fails_rule_6():
    """A reply on the Spark, after the child said the mother was under a big tree."""
    said = "小狗一直叫，妈妈就在大树下面。可是我看画里只有哥哥、弟弟和小狗，大树在哪里呢？"
    assert rule_6_no_correction(said).status == "fail"
    assert rule_6_no_correction("The tree isn't in the picture. Where is it?").status == "fail"


def test_telling_a_child_what_they_only_drew_or_did_not_draw_fails_rule_6():
    """The class page, to a child who had said they were stuck."""
    said = "你说你不知道，你想不出来了。可是你只画了球在脚边，小男孩的手在哪里呢？"
    assert rule_6_no_correction(said).status == "fail"
    assert rule_6_no_correction("你没有画小男孩的手，他的手在做什么？").status == "fail"


def test_a_character_who_cannot_see_something_is_not_a_correction():
    assert rule_6_no_correction("我是树上的小鸟，我看不到妈妈，她去哪里了？").status == "pass"


@pytest.mark.parametrize("text", REALISM)
def test_realism_policing_fails_rule_7(text):
    assert rule_7_no_realism_policing(text).status == "fail"


@pytest.mark.parametrize("text", DIMINISHING)
def test_diminishing_words_fail_rule_8(text):
    assert rule_8_no_diminishing(text).status == "fail"


def test_a_failure_quotes_the_offending_phrase():
    result = rule_8_no_diminishing("I see a dog. It is just a simple sketch. What is it?")
    assert "simple" in result.evidence or "just a" in result.evidence


# --- Fragments, found by a live run --------------------------------------------
# Every list below was matched as a bare substring, so a forbidden word buried
# inside an innocent one failed correct feedback. Rule 8 fired three times in
# sixteen live runs on nothing worse than the word "through".

THROUGH = [
    "I see orange rings. What would happen if I stepped through that space?",
    "I see a round shape. The sphere reads as round throughout the form. What is it doing?",
]


@pytest.mark.parametrize("text", THROUGH)
def test_through_is_not_the_diminishing_word_rough(text):
    """'through' and 'throughout' carry 'rough'. Seen in a live run, three times."""
    assert rule_8_no_diminishing(text).status == "pass"


def test_rough_itself_still_fails_rule_8():
    """The fix must not stop the rule catching what it exists for."""
    assert rule_8_no_diminishing("I see a dog. It is a bit rough. What is it?").status == "fail"


def test_roughly_still_fails_rule_8():
    """A word boundary at the front only, so endings the rule means to catch remain."""
    assert rule_8_no_diminishing("I see a dog. It is roughly drawn. What is it?").status == "fail"


def test_scribbles_still_fails_rule_8():
    assert rule_8_no_diminishing("I see scribbles on the page. What are they?").status == "fail"


def test_a_chinese_diminishing_word_still_fails_without_word_boundaries():
    """Chinese is not spaced, so it keeps the substring test it was written for."""
    assert rule_8_no_diminishing("我看到一只小狗。有点乱，不过很有趣。你想说什么呢？").status == "fail"


@pytest.mark.parametrize(
    "text, status",
    [
        ("Is he just arriving, or about to leave?", "pass"),
        ("Only about half of it is shaded.", "pass"),
        ("It is just a scribble.", "fail"),
        ("That is only a start.", "fail"),
    ],
)
def test_a_phrase_ending_in_an_article_needs_the_whole_word(text, status):
    """"just a" matched the front of "just arriving" and failed a rung — on rule
    8, which is a red line, so the child was refused outright.
    An article at the end of a phrase carries no ending worth catching; a stem
    like "rough" does, and keeps the open back that catches "roughly"."""
    assert rule_8_no_diminishing(text).status == status
