"""A reply that repeated none of the child's words gets them said back in front (studio/conversation/chat_beats.py)."""

from evalkit.rubric.loop import rule_13_reply_uses_the_childs_words
from studio.conversation.chat_beats import HEARD_AT_MOST, _heard

ASKED = "听不懂，所以具体要怎么画"
ANSWER = "你可以先找到球体上最亮的地方，再顺着圆的方向一层一层往暗处排线。"


def test_a_reply_to_a_childs_question_that_repeats_none_of_it_gets_their_words_first():
    """The class page: three sends, nine attempts, every one refused on rule 13."""
    assert rule_13_reply_uses_the_childs_words(ANSWER, ASKED).status == "fail"
    said = _heard(ANSWER, ASKED, "zh")
    assert said == "你说：\u201c听不懂，所以具体要怎么画\u201d。" + ANSWER
    assert rule_13_reply_uses_the_childs_words(said, ASKED).status == "pass"


def test_a_reply_that_already_uses_their_words_is_left_alone():
    reply = "具体要怎么画？先找到球体最亮的地方。"
    assert _heard(reply, ASKED, "zh") == reply


def test_only_the_last_sentence_is_said_back_and_never_at_length():
    long_answer = "我画了一只狗。" + "它" * 50 + "。"
    said = _heard("那个房子是谁的？", long_answer, "zh")
    assert "我画了一只狗" not in said
    assert said.count("它") == HEARD_AT_MOST


def test_english_says_it_back_with_a_space():
    said = _heard("Start with the brightest spot on the ball.", "How do I draw the shadow?", "en")
    assert said.startswith("You said: \u201cHow do I draw the shadow\u201d. Start")


def test_the_said_back_line_takes_out_anything_written_on_the_drawing():
    """Code review: the one line no model writes skipped the redactor."""
    from types import SimpleNamespace
    from studio.conversation.chat_beats import ChatBeats
    from studio.conversation.conversation import _load_skill
    safety = _load_skill("safety_skill", "skills/studio-safety/scripts/safety.py")
    talk = SimpleNamespace(language="zh", entrance="colour", safety=safety,
                           verdict=SimpleNamespace(text_found=("林小美",)))
    said = ChatBeats._said_back(talk, "这是林小美的小狗，它在等我。")
    assert "林小美" not in said and "小狗" in said and said.endswith("发生了什么？")
    talk.verdict = None
    assert "林小美" in ChatBeats._said_back(talk, "这是林小美的小狗。"), "nothing written on it, nothing taken out"
