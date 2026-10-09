"""A judge's objection stands only on words that are really there (evalkit/rubric/quotes.py).

The replies are the seven whose verdicts were known when Qwen3.6, thinking off, became the class's
judge and refused every good one.
"""

import json

from evalkit.rubric.assisted import rule_4_non_presumptive
from evalkit.rubric.loop import rule_14_machine_never_tells_the_story
from evalkit.rubric.quotes import ends_in_the_question, standing

CHILD = "他们要去找他的妈妈。他妈妈丢了。这个是他哥哥，这个是他。\n紫色的是他们的小狗，小狗鼻子很灵，能闻到妈妈的味道。"
OPENING = "我看到你把这只动物涂成了紫色，下面两个人手拉着手。"
GOOD = "紫色的是他们的小狗，它的鼻子很灵。它闻到味道之后，会带着哥哥和弟弟去哪里？"
INVENTED = "路上特别热，哥哥心里一定又累又害怕，他们接下来要去哪里？"


def objection(words, why="", source=""):
    return {"words": words, "why": why, "source": source}


def test_an_objection_to_words_the_line_never_said_is_dropped():
    # The judge copied its prompt's example about a reply with no mushroom in it.
    assert standing([objection("紫色的蘑菇", "calls the purple blob a mushroom")], GOOD, CHILD,
                    questions_are_fine=False) == []


def test_the_childs_own_words_are_never_an_objection():
    assert standing([objection("他们的小狗")], GOOD, CHILD, questions_are_fine=False) == []


def test_a_question_invents_nothing_but_a_statement_before_its_comma_does():
    assert ends_in_the_question("它闻到味道之后，会带着哥哥和弟弟去哪里", GOOD)
    assert ends_in_the_question("去哪里？", GOOD)
    assert not ends_in_the_question("哥哥心里一定又累又害怕", INVENTED)
    kept = standing([objection("哥哥心里一定又累又害怕", "gives the brother feelings")], INVENTED, CHILD,
                    questions_are_fine=True)
    assert kept == ["gives the brother feelings (哥哥心里一定又累又害怕)"]


def test_words_asked_first_and_stated_after_are_still_an_objection():
    """Code review: only the first place the words appeared was looked at."""
    line = "它会飞吗？它会飞到月亮上。"
    kept = standing([objection("会飞", "says it flies")], line, CHILD, questions_are_fine=True)
    assert kept == ["says it flies (会飞)"]
    assert standing([objection("会飞")], "它会飞吗？它要去哪里？", CHILD, questions_are_fine=True) == []


def test_a_source_the_child_really_gave_clears_the_words_and_a_made_up_one_does_not():
    line = "哥哥牵着弟弟走了很久。"
    theirs = CHILD + "\n" + OPENING
    assert standing([objection("哥哥牵着弟弟", source="两个人手拉着手")], line, theirs,
                    questions_are_fine=True) == []
    assert standing([objection("哥哥牵着弟弟", source="他们牵着手唱歌")], line, theirs,
                    questions_are_fine=True) == ["哥哥牵着弟弟"]


def test_a_description_from_an_older_judge_is_taken_at_its_word():
    assert standing(["calls the purple blob a mushroom"], GOOD, CHILD, questions_are_fine=False) == [
        "calls the purple blob a mushroom"]
    assert standing("a lone string", GOOD, CHILD, questions_are_fine=False) == ["a lone string"]
    assert standing(None, GOOD, CHILD, questions_are_fine=False) == []


def test_rule_4_refuses_a_misnamed_shape_and_passes_a_copied_example(fake_client):
    misnamed = "路上特别热，旁边那只紫色的小猫也热坏了。它们接下来要去哪里？"
    said = json.dumps({"presumptive": [objection("紫色的小猫", "calls the purple blob a cat")]})
    client = fake_client([said, '{"fine": false, "because": "the child never named it"}'])
    assert rule_4_non_presumptive(misnamed, "data:,x", client, child_said=CHILD).status == "fail"
    assert '"紫色的小猫"' in client.calls[1]["prompt"] and client.calls[1]["images"] == ["data:,x"]
    copied = json.dumps({"presumptive": [objection("紫色的蘑菇", "calls the purple blob a mushroom")]})
    assert rule_4_non_presumptive(GOOD, "data:,x", fake_client([copied]), child_said=CHILD).status == "pass"


def test_rule_4_lets_a_name_the_child_gave_in_other_words_through_once_asked(fake_client):
    line = "哥哥和弟弟走了很久。"
    said = json.dumps({"presumptive": [objection("哥哥和弟弟", "calls the figures brothers")]})
    client = fake_client([said, '{"fine": true, "because": "the child said his brother and him"}'])
    assert rule_4_non_presumptive(line, "data:,x", client, child_said=CHILD).status == "pass"


def test_rule_4_does_not_refuse_a_name_the_studios_own_opening_gave(fake_client):
    line = "他们走了很久很久。那个紫色的动物在做什么？"
    said = json.dumps({"presumptive": [objection("这只动物", "calls the purple shape an animal")]})
    assert rule_4_non_presumptive(line.replace("那个紫色的动物", "这只动物"), "data:,x", fake_client([said]),
                                  child_said=CHILD, opening=OPENING).status == "pass"
    paraphrased = json.dumps({"presumptive": [objection("那个紫色的动物", "calls the purple shape an animal")]})
    client = fake_client([paraphrased, '{"fine": true, "because": "the first comment called it an animal"}'])
    assert rule_4_non_presumptive(line, "data:,x", client, child_said=CHILD, opening=OPENING).status == "pass"
    assert OPENING in client.calls[1]["prompt"]


def test_rule_14_refuses_an_invented_feeling_and_passes_a_question(fake_client):
    said = json.dumps({"invented": [objection("哥哥心里一定又累又害怕", "gives the brother feelings")]})
    client = fake_client([said, '{"new": true, "child_words": ""}'])
    result = rule_14_machine_never_tells_the_story(INVENTED, CHILD, client, OPENING)
    assert result.status == "fail" and "哥哥心里一定又累又害怕" in result.evidence
    asked = json.dumps({"invented": [objection("它闻到味道之后，会带着哥哥和弟弟去哪里")]})
    assert rule_14_machine_never_tells_the_story(GOOD, CHILD, fake_client([asked]), OPENING).status == "pass"


def test_rule_14_lets_the_childs_story_in_other_words_through_once_asked(fake_client):
    line = "哥哥牵着弟弟走了很久很久。"
    said = json.dumps({"invented": [objection("哥哥牵着弟弟", "makes them brothers holding hands")]})
    client = fake_client([said, '{"new": false, "child_words": "这个是他哥哥，这个是他"}'])
    assert rule_14_machine_never_tells_the_story(line, CHILD, client, OPENING).status == "pass"
    assert "哥哥牵着弟弟" in client.calls[1]["prompt"]


def test_rule_14_shows_the_recheck_the_drawing_so_what_it_plainly_shows_is_not_invented(fake_client):
    """The class page: "the cabin with its light on" refused about a cabin with a lit window."""
    line = "会带去那个亮着灯的小木屋。小船要怎么靠岸？"
    said = json.dumps({"invented": [objection("那个亮着灯的小木屋", "adds that the cabin has a light on")]})
    client = fake_client([said, '{"new": false, "child_words": ""}'])
    result = rule_14_machine_never_tells_the_story(line, "会带去一个漂亮的小木屋", client, OPENING, image="data:,x")
    assert result.status == "pass"
    assert client.calls[0]["images"] == [] and client.calls[1]["images"] == ["data:,x"]


def test_a_recheck_that_gives_no_answer_leaves_the_objection_standing(fake_client):
    said = json.dumps({"invented": [objection("哥哥心里一定又累又害怕", "gives the brother feelings")]})
    client = fake_client([said, "no json", "still none"])
    assert rule_14_machine_never_tells_the_story(INVENTED, CHILD, client, OPENING).status == "fail"
    named = json.dumps({"presumptive": [objection("紫色的小猫", "calls it a cat")]})
    client = fake_client([named, "no json", "still none"])
    assert rule_4_non_presumptive("那只紫色的小猫很热。", "data:,x", client, child_said=CHILD).status == "fail"


LIVE_EARLIER = "它在看门口那个小球，它想出去玩。\n小主人终于回来了，是个小男孩，他一打开门，小狗就冲出去追那个小球。"
LIVE_SAID = "小男孩把小球扔得好远，小狗跑过去叼回来，还摇尾巴。"
LIVE_REPLY = "你画的小狗摇着尾巴，看起来它把球叼回来一定很开心。\n那个小球滚得那么远，小男孩是往哪里扔的？"


def test_the_live_reply_that_gave_the_dog_a_feeling_is_refused_without_asking_a_model():
    """On the class page: the judge passed it five times in five."""
    from evalkit.rubric import run_rubric
    report = run_rubric(LIVE_REPLY, entrance="colour", child_said=LIVE_SAID, earlier_child_words=LIVE_EARLIER)
    rule_14 = next(r for r in report.results if r.rule == 14)
    assert rule_14.status == "fail" and "开心" in rule_14.evidence
    assert report.crossed, "a red line: the child never sees it"


def test_a_feeling_the_child_gave_or_the_reply_only_asks_about_is_not_refused():
    from evalkit.rubric.loop import rule_14_names_no_feeling
    assert rule_14_names_no_feeling("小狗很开心，它接下来去哪里？", "小狗叼回球，好开心。").status == "pass"
    assert rule_14_names_no_feeling("小狗叼回了球。它心里开心吗，还是想再玩？", LIVE_SAID).status == "pass"
    assert rule_14_names_no_feeling("小狗叼回了球，它这时候心里在想什么？", LIVE_SAID).status == "pass"
    assert rule_14_names_no_feeling("哥哥很害怕，他们要去哪里？", LIVE_SAID).status == "fail"
    assert rule_14_names_no_feeling("The dog must be so happy. Where did the ball go?",
                                    "the dog brought the ball back").status == "fail"


def test_the_storys_characters_are_not_called_you_unless_the_child_said_we():
    """A replayed class conversation: "where will you go first?" of two brothers."""
    from evalkit.rubric.loop import rule_14_without_a_model
    reply = "紫色的小狗鼻子很灵，能闻到妈妈的味道。你们打算先往哪里走？"
    assert rule_14_without_a_model(reply, "紫色的是他们的小狗，小狗鼻子很灵。").status == "fail"
    assert rule_14_without_a_model(reply, "我们和小狗一起去找妈妈。").status == "pass"


def test_asking_why_about_a_feeling_nobody_gave_presumes_it():
    """Code review: "why is he so happy?" gives him a feeling from inside a question."""
    from evalkit.rubric.loop import rule_14_names_no_feeling
    assert rule_14_names_no_feeling("小狗叼回了球。它为什么那么开心？", LIVE_SAID).status == "fail"
    assert rule_14_names_no_feeling("小狗叼回了球。它心里觉得怎么样？", LIVE_SAID).status == "pass"
    assert rule_14_names_no_feeling("小狗叼回了球。它为什么跑得那么快？", LIVE_SAID).status == "pass"
    assert rule_14_names_no_feeling("它为什么那么开心？", "小狗叼回球，它好开心。").status == "pass"
    assert rule_14_names_no_feeling("Why is the dog so happy?", "the dog brought the ball back").status == "fail"


def test_a_rung_may_speak_as_a_character_who_says_how_it_feels():
    from evalkit.rubric import run_rubric
    report = run_rubric("我是门口的小狗，我好开心，你愿意陪我玩吗？", entrance="colour", beat="rung",
                        earlier_child_words=LIVE_EARLIER)
    assert next(r for r in report.results if r.rule == 14).status == "skip"


def test_both_prompts_show_an_empty_answer_first_so_a_judge_has_no_example_to_copy():
    from evalkit.rubric.assisted import PRESUMPTION_PROMPT
    from evalkit.rubric.loop import INVENTION_PROMPT
    assert 'Reply exactly like {{"presumptive": []}}' in PRESUMPTION_PROMPT
    assert 'Reply exactly like {{"invented": []}}' in INVENTION_PROMPT
