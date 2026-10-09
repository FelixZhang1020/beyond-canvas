"""Rules 12 to 14: the loop, not the comment.

The worked examples in section 5a of the spec are the fixtures here, because
they are the operator's own account of what working looks like.
"""

import pytest

from evalkit.rubric import run_rubric
from evalkit.rubric.loop import (
    rule_11_serves_the_lesson,
    rule_12_opening_hands_over_the_picture,
    rule_12_question_enters_the_process,
    rule_12_question_enters_the_world,
    rule_13_reply_uses_the_childs_words,
    rule_14_machine_never_tells_the_story,
)

# From the spec's first worked example, seven years old.
OPENING_EN = (
    "I see you coloured this animal purple, and the sun's light as pointy triangles. "
    "Two people below are holding hands. What just happened to them?"
)
CHILD_EN = (
    "They are going to find his mother. His mother is lost. This is his brother and "
    "this is him. They walked for a very long time."
)
GOOD_REPLY_EN = "So you drew the road that long because they walked a long time?"

OPENING_ZH = "我看到你把这只动物涂成了紫色，太阳的光画成了尖尖的三角形。他们刚刚发生了什么事？"
CHILD_ZH = "他们要去找他的妈妈。他妈妈丢了。他们走了很久很久。"
GOOD_REPLY_ZH = "所以你把这条路画得这么长，是因为他们走了很久吗？"


@pytest.mark.parametrize("text", [OPENING_EN, OPENING_ZH])
def test_a_question_about_events_passes_rule_12(text):
    assert rule_12_question_enters_the_world(text).status == "pass"


def test_asking_what_was_drawn_fails_rule_12():
    """The spec's named failure: it returns a list of nouns, not a story."""
    result = rule_12_question_enters_the_world("I see orange lines. What did you draw?")
    assert result.status == "fail"
    assert "artifact" in result.evidence


def test_asking_what_this_is_in_chinese_fails_rule_12():
    assert rule_12_question_enters_the_world("我看到橙色的线。这是什么？").status == "fail"


def test_a_colour_opening_may_hand_the_picture_to_the_child_and_a_rung_may_not():
    """Operator: an opening that guessed where the ship was going was "very subjective"; the child
    says what they drew first, and the questions after build on it. After silence, a smaller door."""
    opening = "我看到深蓝色的大船和白色的山。跟我说说，你画了什么呀？"
    assert rule_12_opening_hands_over_the_picture(opening).status == "pass"
    assert rule_12_opening_hands_over_the_picture("I see orange lines. What did you draw?").status == "pass"
    assert rule_12_opening_hands_over_the_picture("我看到橙色的线。这是什么？").status == "fail", "names one shape"
    # Review: found anywhere in the question, the invitation let these through.
    for pointed in ("我看到红色的屋顶。你画了什么颜色的屋顶？", "我看到一个圆圈。这里画的是什么？",
                    "我看到一艘船。你画了什么，是一艘要回家的船？", "I see waves. What did you draw with?"):
        assert rule_12_opening_hands_over_the_picture(pointed).status == "fail", pointed
    assert rule_12_opening_hands_over_the_picture("I see waves. Tell me what you drew today?").status == "pass"

    def rule_12(beat):
        return next(r for r in run_rubric(opening, entrance="colour", beat=beat).results if r.rule == 12)
    assert rule_12("opening").status == "pass"
    assert rule_12("rung").status == "fail"


def test_no_question_at_all_fails_rule_12():
    assert rule_12_question_enters_the_world("I see orange lines and green dots.").status == "fail"


def test_a_question_that_reaches_nowhere_fails_rule_12():
    result = rule_12_question_enters_the_world("I see orange lines. Which colour is that?")
    assert result.status == "fail"


@pytest.mark.parametrize(
    ("reply", "said"), [(GOOD_REPLY_EN, CHILD_EN), (GOOD_REPLY_ZH, CHILD_ZH)]
)
def test_a_reply_echoing_the_child_passes_rule_13(reply, said):
    assert rule_13_reply_uses_the_childs_words(reply, said).status == "pass"


def test_a_reply_that_could_predate_the_child_fails_rule_13():
    """The test that matters: this reply is warm, and it heard nothing."""
    result = rule_13_reply_uses_the_childs_words(
        "What a lovely picture. Would you like to draw another one?", CHILD_EN
    )
    assert result.status == "fail"
    assert "before they spoke" in result.evidence


def test_rule_13_is_skipped_when_the_child_said_nothing():
    """In a class of twenty not every child speaks. Silence is not a failure."""
    assert rule_13_reply_uses_the_childs_words(GOOD_REPLY_EN, "").status == "skip"


def test_a_reply_inventing_nothing_passes_rule_14(fake_client):
    client = fake_client(['{"invented": []}'])
    result = rule_14_machine_never_tells_the_story(GOOD_REPLY_EN, CHILD_EN, client)
    assert result.status == "pass"


def test_a_reply_that_adds_story_fails_rule_14(fake_client):
    client = fake_client(['{"invented": ["says the mother was taken by a wolf"]}'])
    result = rule_14_machine_never_tells_the_story(GOOD_REPLY_EN, CHILD_EN, client)
    assert result.status == "fail"
    assert "wolf" in result.evidence


def test_rule_14_is_skipped_when_the_child_said_nothing(fake_client):
    client = fake_client([])
    assert rule_14_machine_never_tells_the_story(GOOD_REPLY_EN, "", client).status == "skip"


def test_the_invention_judge_needs_no_image(fake_client):
    """Rules 3 and 4 judge against a drawing; rule 14 judges against what was said."""
    client = fake_client(['{"invented": []}'])
    rule_14_machine_never_tells_the_story(GOOD_REPLY_EN, CHILD_EN, client)
    assert client.calls[0]["images"] == []


LESSON = "using warm and cool colours next to each other"


def test_feedback_connecting_to_the_lesson_passes_rule_11(fake_client):
    client = fake_client(['{"connected": true, "why": "notices the warm sun beside the cool purple"}'])
    result = rule_11_serves_the_lesson(OPENING_EN, LESSON, client)
    assert result.status == "pass"
    assert "warm sun" in result.evidence


def test_feedback_touching_nothing_of_the_lesson_fails_rule_11(fake_client):
    """Good feedback is not the same as feedback that serves this lesson."""
    client = fake_client(['{"connected": false}'])
    result = rule_11_serves_the_lesson(OPENING_EN, LESSON, client)
    assert result.status == "fail"
    assert "warm and cool" in result.evidence


def test_rule_11_is_skipped_when_no_lesson_intent_was_given(fake_client):
    """The common case: a teacher who typed nothing is not a failing teacher."""
    client = fake_client([])
    assert rule_11_serves_the_lesson(OPENING_EN, "", client).status == "skip"


def test_the_lesson_judge_needs_no_image(fake_client):
    client = fake_client(['{"connected": true, "why": "x"}'])
    rule_11_serves_the_lesson(OPENING_EN, LESSON, client)
    assert client.calls[0]["images"] == []


def test_a_reply_is_not_marked_down_for_naming_no_visual_details(fake_client):
    """Rule 3 cannot pass on a reply that is a question, and a reply should be one.

    Live run: "The tree is your grandma's tree and you climb it. Is
    that the tree with the brown trunk and green leaves?" was refused twice for
    naming zero grounded details, because the grounding judge is told to ignore
    questions. Rule 13 is what grounds a reply.
    """
    client = fake_client(['{"presumptive": []}', '{"invented": []}'])
    report = run_rubric(
        "The tree is your grandma's tree and you climb it. Is that the one with the brown trunk?",
        entrance="colour",
        image_data_uri="data:,x",
        client=client,
        child_said="the tree is my grandma's tree and I climb it",
    )
    by_rule = {result.rule: result for result in report.results}
    assert by_rule[3].status == "skip"
    assert by_rule[13].status == "pass"
    assert report.pass_rate == 1.0


def test_an_opening_still_has_to_name_two_real_details(fake_client):
    client = fake_client(['{"grounded": ["yellow sun"]}', '{"presumptive": []}'])
    report = run_rubric(
        "I see a yellow sun. What is happening here?",
        entrance="colour",
        image_data_uri="data:,x",
        client=client,
    )
    assert {result.rule for result in report.failures} == {3}


def test_a_reply_that_only_hands_the_sentence_back_fails():
    """Live run: the model replied with the child's sentence, verbatim,
    in the child's own first person, and every rule passed it."""
    said = "the tree is my grandma's tree and I climb it"
    result = rule_13_reply_uses_the_childs_words(said, said)
    assert result.status == "fail"
    assert "nothing of its own" in result.evidence


def test_a_reply_that_adds_one_thought_of_its_own_passes():
    said = "the tree is my grandma's tree and I climb it"
    result = rule_13_reply_uses_the_childs_words(
        "So the tree is grandma's. What can you see when you climb up there?", said
    )
    assert result.status == "pass"
# --- Marker gaps, found by a live run ------------------------------------------
# Both questions below are what their entrance asks for, and both were marked
# down because the marker list did not carry the words the model chose.

def test_asking_what_would_happen_passes_rule_12():
    """A question about the unseen, and the strongest kind the spec names.
    'happening' and 'happened' were listed; the bare stem was not."""
    result = rule_12_question_enters_the_world(
        "I see orange rings and three green dots. What would happen if I stepped through that space?"
    )
    assert result.status == "pass", result.evidence


def test_asking_what_is_hidden_passes_rule_12():
    """The unseen is one of the six kinds of world question in section 5a."""
    result = rule_12_question_enters_the_world(
        "I see a round shape covered in lines. What is hiding under the fuzzy skin?"
    )
    assert result.status == "pass", result.evidence


def test_asking_what_part_was_redrawn_passes_rule_12_on_sketch():
    """The spec's own sketch question, in the words the model actually used."""
    result = rule_12_question_enters_the_process(
        "I see the cast shadow and the highlight. What part of the cast did you redraw the most?"
    )
    assert result.status == "pass", result.evidence


def test_a_question_about_nothing_still_fails_rule_12_on_sketch():
    """Widening the list must not turn every question into a pass."""
    result = rule_12_question_enters_the_process(
        "I see the shadow under the sphere. What colour is your pencil?"
    )
    assert result.status == "fail"


def test_asking_whether_the_child_understands_is_not_a_world_question():
    """'under' sits at the front of 'understand', so it is not on the marker list."""
    result = rule_12_question_enters_the_world("I see orange rings. Do you understand?")
    assert result.status == "fail"


def test_a_world_question_that_opens_like_an_artifact_question_passes_rule_12():
    """Live run: 'What is this character looking at in the distance?'
    was failed as an artifact question, because 'what is this' is a prefix of it.
    A question that reaches into the picture is a world question whatever it
    opens with, the same precedence rule 9 already uses for its yes-or-no openers."""
    result = rule_12_question_enters_the_world(
        "I see a dark shape with two red eyes. What is this character looking at in the distance?"
    )
    assert result.status == "pass", result.evidence


def test_a_bare_artifact_question_still_fails_rule_12():
    """The precedence must not excuse the question the rule exists to catch."""
    assert rule_12_question_enters_the_world("I see orange lines. What is this?").status == "fail"


def test_how_did_you_is_a_process_question_on_sketch():
    """A live run failed three of these. It is the commonest opener the
    model chooses for a process question."""
    for question in (
        "I see the green dots. How did you decide on the placement of the green dots?",
        "I see the cast shadow. How did you approach drawing the cast?",
    ):
        assert rule_12_question_enters_the_process(question).status == "pass", question


@pytest.mark.parametrize(
    "text, status",
    [
        ("我是那只鸟，我能停在你的树上吗？", "pass"),
        ("I am the bird you drew. May I sit in your tree?", "pass"),
        ("I'm the purple creature. Where should I go next?", "pass"),
        ("I am pleased with this drawing.", "fail"),
        ("What did you draw?", "fail"),
    ],
)
def test_the_third_rung_speaks_as_something_in_the_picture(text, status):
    """Section 3.5 calls this the strongest rung and no marker list could ever
    recognise it: a character introducing itself contains none of the words a
    question about events contains. Its own worked example — 我是那只鸟，我能停在
    你的树上吗？ — used to fail the rule meant to reward it."""
    assert rule_12_question_enters_the_world(text).status == status


def test_the_invention_judge_is_told_that_drawing_advice_is_not_story(fake_client):
    """On the sketch entrance the reply is ORDERED to offer one small thing to try.

    In a live run, two of three replies to a child who said the pear's neck
    was hard were refused by this rule, the second for exactly that tip — use a
    light line to fix the proportions first, then darken. Five and a half minutes
    later the child got an answer. Teaching how to draw is not telling the child's
    story, and the judge has to be told so; on the colour entrance, where advice
    IS harm, rule 6 refuses it separately, so nothing leaks through here.
    """
    client = fake_client(['{"invented": []}'])
    rule_14_machine_never_tells_the_story(
        "Try a lighter line for the pear's neck first, then darken.", "The pear's neck was hard.", client
    )
    asked = client.calls[0]["prompt"]
    assert "how to draw" in asked, "the judge is never told that technique advice is not story"
    assert "proportion" in asked and "shading" in asked


def test_the_invention_judge_lists_a_character_turned_into_the_child(fake_client):
    """Live on the Spark: the child said the dog waits for its "little owner", and
    the reply said the dog waits for "you"."""
    client = fake_client(['{"invented": []}'])
    rule_14_machine_never_tells_the_story("The dog waits at the door for you.",
                                          "The dog waits for its little owner.", client)
    asked = client.calls[0]["prompt"]
    assert "calling someone in the child's story" in asked
    assert 'The child talking about themselves ("I", "my") becomes "you"' in asked


def test_the_invention_judge_is_shown_what_the_machine_had_already_said(fake_client):
    """In a live run a reply was refused for "the mice are carrying cannons" —
    a cannon that is in the drawing and that the opening had named a minute earlier.
    The judge only ever saw the child's words and the reply, so anything the studio
    itself had said before the child spoke looked new. It is now told the opening,
    and that nothing already in it counts as new.
    """
    client = fake_client(['{"invented": []}'])
    rule_14_machine_never_tells_the_story(
        "The mice push their cannon towards the castle. Who is leading?",
        "They are going to protect the castle.", client,
        opening="Six grey mice, some with swords, push a cannon towards the pink castle.",
    )
    asked = client.calls[0]["prompt"]
    assert "push a cannon towards the pink castle" in asked
    assert "not new" in asked
