"""A reply reaches the child whole: its quotes closed, its question marked and asked once, no sentence said twice.

Every broken line here was shown on the class page while ten showcase classes were filled with
eight rounds of chat each; about one reply in four needed taking back. The strings are those replies, as the
page received them (studio/conversation/words.py, studio/conversation/chat_beats.py).
"""

from studio.conversation.chat_beats import (HEARD_AT_MOST, _asked, _finished, _last_words, _said_once,
                                            _without_closed_questions)
from studio.conversation.gates import Gates
from studio.conversation.words import answered_turn, split_question


def test_a_closing_quote_stays_with_the_words_it_closes():
    """The question used to start with the quote's closing mark and a line break."""
    reply = "“因为它的鳍还太小了，它才出生没几天。”\n哥哥姐姐们停下来等它，那它们在水里等它的时候，谁在帮它挡水流呢？"
    text, question = split_question(reply)
    assert text == "“因为它的鳍还太小了，它才出生没几天。”"
    assert question == "哥哥姐姐们停下来等它，那它们在水里等它的时候，谁在帮它挡水流呢？"


def test_a_straight_closing_quote_stays_with_its_words_too():
    reply = '"原来公主是想请老鼠们吃奶酪呀！那我也不扔雪球了，我去帮公主搬桌子。"\n那个举旗子的士兵往城门那里跑，公主看到了什么？'
    text, question = split_question(reply)
    assert text.endswith('搬桌子。"')
    assert question == "那个举旗子的士兵往城门那里跑，公主看到了什么？"


def test_a_last_question_left_without_its_mark_gets_it_back():
    """Shown with no question at all: the check only knew a question by the mark at its end."""
    reply = "雪球打在城墙上，啪的一声变成了一朵雪花。那个举旗子的士兵跳起来躲的时候，那雪花会怎么飘"
    assert _finished(reply) == reply + "？"
    assert split_question(_finished(reply))[1] == "那个举旗子的士兵跳起来躲的时候，那雪花会怎么飘？"
    assert _finished("那棵小松树长出来了吗").endswith("？"), "a closed question is still a question"


def test_a_last_statement_left_without_its_mark_gets_a_full_stop():
    assert _finished("小狐狸接住了篮子") == "小狐狸接住了篮子。"


def test_a_finished_reply_is_left_as_it_is():
    for reply in ("它藏在最红的地方。", "它藏在哪里？", "你说：“它躲起来了。”", "", "小狐狸划走了……", "它在唱歌～"):
        assert _finished(reply) == reply


def test_a_soft_statement_without_its_mark_is_not_made_a_question():
    """Code review: a teacher's soft statement ends in the same words a question does."""
    for said in ("它还没长大呢", "他什么都不怕", "小熊一动不动", "它哪里也不去", "这里没什么变化"):
        assert _finished(said) == said + "。", said
    for asked in ("那雪花呢", "它会去哪里呢", "你觉得会不会下雪"):
        assert _finished(asked) == asked + "？", asked


def test_a_reply_left_on_a_comma_ends_on_a_full_stop_instead():
    assert _finished("小狐狸划走了，") == "小狐狸划走了。"


def test_an_english_question_left_without_its_mark_gets_it_back():
    assert _finished("The boat reached the house. Who is waiting there") == (
        "The boat reached the house. Who is waiting there?")
    assert _finished("The boat reached the house") == "The boat reached the house."


def test_an_opening_straight_quote_stays_with_its_own_sentence():
    from studio.conversation.words import parts
    assert parts('他说完了。"下雪啦！"她喊。') == ["他说完了。", '"下雪啦！"', "她喊。"]


def test_once_its_mark_is_back_a_second_closed_question_is_taken_out():
    """The reply asked twice, and only the first had its mark, so neither check saw two questions."""
    reply = "因为它身上也有红点点，红点和红点混在一起就看不出来了。它躲在最红的地方，谁都能找到它吗？它藏在哪里"
    assert _without_closed_questions(_finished(reply)) == (
        "因为它身上也有红点点，红点和红点混在一起就看不出来了。它藏在哪里？")


def test_the_words_said_back_break_between_clauses_never_inside_one():
    """「你说：“……明天还要来找帕丁顿一起”」 cut the child off mid-phrase."""
    assert _last_words("她在想，这是她过得最好玩的一个下雪天，明天还要来找帕丁顿一起玩。") == (
        "这是她过得最好玩的一个下雪天，明天还要来找帕丁顿一起玩")
    assert _last_words("她不用打开，小老鼠晚上会自己来，轻轻推开盖子拿走奶酪，再留下一颗小松果当谢谢。") == (
        "轻轻推开盖子拿走奶酪，再留下一颗小松果当谢谢")
    assert len(_last_words("它" * 50 + "。")) == HEARD_AT_MOST, "one clause too long is still cut"


def test_the_words_said_back_are_never_a_scrap_or_a_broken_word():
    long_then_short = "我把梨子暗面最深的地方又加深了一点现在它和影子分开了一看就是两个东西，好。"
    assert _last_words(long_then_short) == long_then_short[:HEARD_AT_MOST], "not just the last word"
    said = _last_words("the boat goes to the house and then it goes all the way back home again")
    assert said == "the boat goes to the house and" and not said.endswith(" ")


def test_a_sentence_said_twice_in_a_row_is_said_once():
    doubled = "它在看桥上的灯，它要划到桥那边去找它的好朋友小兔子。它要划到桥那边去找它的好朋友小兔子。"
    assert _said_once(doubled) == "它在看桥上的灯，它要划到桥那边去找它的好朋友小兔子。"
    doubled = ("绳子是从桥栏杆中间放下来的，就在那盏灯下面。小狐狸接住篮子，开心得差点把船弄翻了。"
               "小狐狸接住篮子，开心得差点把船弄翻了。小狐狸接住篮子的时候，小兔子在桥上看到了什么？")
    assert _said_once(doubled).count("开心得差点把船弄翻了") == 1
    assert _said_once(doubled).endswith("小兔子在桥上看到了什么？")


def test_the_same_sentence_said_again_in_other_words_is_said_once():
    """The class page (operator): the child's party and penguins came back three times, worded three ways."""
    tripled = ("到了南极之后，他们在游轮上看企鹅和鲸鱼，还要开 party。他们会在南极开 party，还要看企鹅和鲸鱼。"
               "他们在游轮上看企鹅和鲸鱼，还要开 party。")
    assert _said_once(tripled) == "到了南极之后，他们在游轮上看企鹅和鲸鱼，还要开 party。"
    assert _said_once("They watched the penguins and the whales. They watched the whales and the penguins.") \
        == "They watched the penguins and the whales."
    # Their words, then what the drawing shows of them, then a question that reuses their words: all kept.
    kept = ("风把帕丁顿的帽子都快吹掉了，它只好一只手按着帽子。我看你把帕丁顿的手画在帽子上，好像真的在努力按着帽子。"
            "它按着帽子的时候，还会遇到谁呢？")
    assert _said_once(kept) == kept


def test_a_short_echo_is_left_alone():
    assert _said_once("好。好。") == "好。好。"


def test_a_reply_with_nothing_said_twice_keeps_its_line_breaks():
    reply = "你把颈窝压深了。\n\n你觉得头颈的衔接会不会显得更结实？"
    assert _said_once(reply) == reply


def test_the_questions_already_asked_are_read_from_the_conversation():
    history = ("Companion: 我看到城堡的拱门像一个大嘴巴。\n你觉得他们要把礼物送到哪里去呢？",
               "Child: 送给城堡里的公主！",
               "Companion: 礼物是送给公主的。\n小老鼠推着轮子，它们想做什么？",
               "Companion: 城堡里的士兵拿好了剑。")
    assert _asked(history) == ("你觉得他们要把礼物送到哪里去呢？", "小老鼠推着轮子，它们想做什么？")


class _Judged(Gates):
    """A colour conversation whose model judges pass everything, so only the studio's own checks decide."""

    entrance = "colour"

    def _gate(self, text, child_said="", **_):
        self._report = None
        return True, "clean"


def test_a_question_the_companion_already_asked_is_written_again():
    """The sketch class: the same question two rounds running, which no judge there reads."""
    asked = ("这样处理之后，你觉得五官的比例会不会显得更舒服一点？",)
    gate = _Judged()._reply_gate("脸不那么紧了。", "", "", asked=asked)
    ok, why = gate("脸不那么紧了，五官看着更自然。这样处理之后，你觉得五官的比例会不会显得更舒服一点？")
    assert not ok and "already asked" in why
    ok, _ = gate("脸不那么紧了，五官看着更自然。下一张你想先画哪一部分？")
    assert ok
    assert _Judged()._reply_gate("脸不那么紧了。", "", "")("五官看着更自然。")[0], "a reply may ask nothing"


class _Director:
    """A judge that answers whether a reply kept the child's he or she, and keeps what it was asked."""

    def __init__(self, same=True, fails=False, text=""):
        self.same, self.fails, self.text, self.prompts = same, fails, text, []

    @property
    def asked(self):
        return len(self.prompts)

    def chat(self, prompt, images=(), *, system=None, max_tokens=None):
        from studio.core.errors import ModelError
        from studio.providers.base import ChatResult
        self.prompts.append(prompt)
        if self.fails:
            raise ModelError("the judge is away")
        text = self.text or ('{"same": true}' if self.same
                             else '{"same": false, "meant": "the soldier", "reply_says": "the mice"}')
        return ChatResult(text=text, input_tokens=1, output_tokens=1, reasoning_tokens=0, cost_usd=0.0,
                          latency_s=0.0, provider="fake", model="fake")


# The castle class's turn: what the companion said, then the question the child answered.
SOLDIER_TURN = "城堡里的士兵拿好了剑。\n既然大家都拿好了剑准备排队，那个吹喇叭的士兵自己接下来要做什么？"


def test_a_reply_that_gives_the_childs_he_to_another_character_is_written_again():
    """The castle class: "he runs down to shut the gate", about the soldier the question named,
    came back as the mouse soldiers running down."""
    judged = _Judged()
    judged.director = _Director(same=False)
    gate = judged._reply_gate("他要跑下去把城堡的大门关上。", "", "", answering=SOLDIER_TURN)
    ok, why = gate("老鼠士兵跑下去把城堡的大门关上。")
    assert not ok and judged.director.asked == 1
    assert SOLDIER_TURN in judged.director.prompts[0], "the judge reads the whole turn the child answered"
    assert "老鼠" not in why and "士兵" not in why, "the ledger never carries the conversation's words"
    judged.director = _Director(same=True)
    gate = judged._reply_gate("他要跑下去把城堡的大门关上。", "", "", answering=SOLDIER_TURN)
    assert gate("吹喇叭的士兵跑下去把大门关上。")[0]


def test_the_who_check_asks_only_when_the_child_said_he_she_or_it_and_never_blocks_on_its_own_failure():
    judged = _Judged()
    judged.director = _Director(same=False)
    assert judged._reply_gate("小狐狸划到桥那边去了。", "", "", answering="它要去哪里？")("小狐狸划到桥那边去了。")[0]
    assert judged._reply_gate("其他的老鼠都跑了。", "", "", answering="它要去哪里？")("其他的老鼠都跑了。")[0]
    assert judged._reply_gate("他们都跑了。", "", "", answering="它要去哪里？")("老鼠们都跑了。")[0]
    assert judged.director.asked == 0, "no he, she or it of one character in the child's words: nothing to ask"
    judged.director = _Director(fails=True)
    assert judged._reply_gate("它要回家。", "", "", answering="小狐狸要去哪里？")("小狐狸要回家。")[0]
    judged.director = _Director(text="[]")
    assert judged._reply_gate("它要回家。", "", "", answering="小狐狸要去哪里？")("小狐狸要回家。")[0]


def test_the_who_check_is_not_asked_when_the_last_turn_asked_nothing_or_the_class_is_sketch():
    """Code review: a turn that asked nothing gives the child's he or she no one to be, and the
    sketch entrance has no characters."""
    judged = _Judged()
    judged.director = _Director(same=False)
    assert judged._reply_gate("他要回家。", "", "", answering="")("小狐狸要回家。")[0]
    judged.entrance = "sketch"
    assert judged._reply_gate("它有点歪。", "", "", answering="杯子哪里最难画？")("杯口有点歪。")[0]
    assert judged.director.asked == 0


def test_the_answered_turn_is_the_last_companion_turn_only_when_it_asked():
    history = ("Companion: " + SOLDIER_TURN, "Child: 他要跑下去。")
    assert answered_turn(history, "opening?") == SOLDIER_TURN
    assert answered_turn((), "小狐狸要去哪里？") == "小狐狸要去哪里？", "the first answer is to the opening"
    assert answered_turn(history + ("Companion: 城堡里的士兵拿好了剑。",), "opening?") == ""


def test_the_refusal_names_no_words_and_leaves_no_earlier_report_behind():
    """Code review: the ledger never carries a conversation's words, and a refusal read the last reply's
    rubric report as its own."""
    judged = _Judged()
    judged._report = "the report of an earlier reply"
    gate = judged._reply_gate("脸不那么紧了。", "", "", asked=("你觉得五官的比例会不会更舒服一点?",))
    ok, why = gate("五官看着更自然。你觉得五官的比例会不会更舒服一点？")
    assert not ok, "half-width and full-width marks ask the same question"
    assert "五官" not in why and judged._report is None
