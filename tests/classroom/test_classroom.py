"""One class held in memory: what it keeps, what it forgets, and what it tells the page.

These tests are the page contract read back as assertions. The properties worth
holding are the ones a demo cannot show: that ending a class actually deletes
the drawings, that a verdict is decided once rather than re-rolled per beat,
and that the events the page renders are the same decisions the ledger records.
"""

import json

import pytest

from studio.classroom.classroom import Classroom
from studio.conversation.words import split_question

DRAWING = "skills/art-feedback/evals/files/dog-sun.png"

ALLOW = '{"verdict": "allow", "reason": "a drawing", "text_found": []}'
GOOD = (
    "I see a yellow sun with pointy triangle rays. I notice two figures below it. "
    "What is happening between them?"
)
GROUNDED = '{"grounded": ["yellow sun", "two figures"]}'
CLEAN = '{"presumptive": []}'
INSIDE = '{"world": true, "why": "asks what is happening in the picture"}'
NOTHING_INVENTED = '{"invented": []}'
FOLLOWS = '{"question_issues": [], "why": "follows the child"}'
CLASS = {"language": "en", "entrance": "colour"}


class Scripted:
    """Replays canned replies and remembers what it was asked."""

    def __init__(self, replies):
        self.replies = list(replies)
        self.prompts = []
        self.images = []

    def chat(self, prompt, images=(), *, system=None, max_tokens=None):
        from studio.providers.base import ChatResult

        if '{"same"' in prompt:
            # The who-said-it judge runs beside the rubric's, in whatever order the threads reach this client, so
            # it neither takes a scripted reply nor moves the prompts a test counts: it always hears the child's he
            # or she kept where they put it.
            return ChatResult(text='{"same": true}', input_tokens=10, output_tokens=10, reasoning_tokens=0,
                              cost_usd=0.0, latency_s=0.0, provider="fake", model="fake")
        self.prompts.append(prompt)
        self.images.append(list(images))
        if not self.replies:
            raise AssertionError("Scripted ran out of replies")
        return ChatResult(
            text=self.replies.pop(0), input_tokens=10, output_tokens=10,
            reasoning_tokens=0, cost_usd=0.0, latency_s=0.0, provider="fake", model="fake",
        )


@pytest.fixture
def room(tmp_path):
    """A classroom whose two slots share one scripted client."""
    def build(replies, editor=None):
        client = Scripted(replies)
        classroom = Classroom(tmp_path / "ledger.jsonl", clients={"vlm.studio": client, "vlm.director": client},
                              editor=editor)
        # Scripted requests exercise conversation behavior, regardless of other
        # models currently occupying memory on the shared Spark test host.
        classroom.ceiling_gb = float("inf")
        classroom.client = client
        return classroom
    return build


@pytest.fixture
def png():
    return open(DRAWING, "rb").read()


def run(classroom, session_id, drawing_id, options=None):
    """Make a request and collect every event it produces."""
    started = classroom.request(session_id, "art-feedback", [drawing_id], options or {})
    classroom.run_request(started["request_id"])
    return list(classroom.follow(started["request_id"]))


def outputs_of(events):
    return next(data for name, data in events if name == "done").get("outputs")


def test_ending_a_class_deletes_every_drawing_from_disk(room, png):
    classroom = room([])
    session_id = classroom.begin(CLASS)
    classroom.add_drawing(session_id, png)
    folder = classroom.sessions[session_id].folder
    assert list(folder.iterdir()), "the drawing should be on disk while the class runs"
    classroom.end(session_id)
    assert not folder.exists(), "section 1a promises nothing is kept"


def test_a_photo_that_is_not_an_image_is_refused_before_any_model_runs(room):
    classroom = room([])
    session_id = classroom.begin(CLASS)
    with pytest.raises(ValueError):
        classroom.add_drawing(session_id, b"this is not a PNG")


def test_the_opening_reaches_the_page_split_into_words_and_a_question(room, png):
    classroom = room([ALLOW, GOOD, GROUNDED, CLEAN])
    session_id = classroom.begin(CLASS)
    drawing_id = classroom.add_drawing(session_id, png)
    outputs = outputs_of(run(classroom, session_id, drawing_id))
    assert outputs["question"] == "What is happening between them?"
    assert outputs["question"] not in outputs["text"]
    assert "yellow sun" in outputs["text"]


def test_a_blocked_drawing_stays_blocked_without_asking_the_model_again(room, png):
    """Re-screening the same bytes would be re-rolling a verdict until it changes."""
    photo = '{"verdict": "block", "reason": "a photograph", "text_found": []}'
    classroom = room([photo, photo])
    session_id = classroom.begin(CLASS)
    drawing_id = classroom.add_drawing(session_id, png)
    first = run(classroom, session_id, drawing_id)
    second = run(classroom, session_id, drawing_id)
    for events in (first, second):
        stopped = next(data for name, data in events if data.get("status") == "stopped")
        assert stopped["reason_code"] == "photo_not_drawing"
    assert len(classroom.client.prompts) == 2, (
        "two looks the first time, because a refusal must not rest on one; and none "
        "the second time, because the verdict is remembered"
    )


def test_a_stopped_run_also_sends_done_so_the_page_closes_its_stream(room, png):
    blank = '{"verdict": "empty", "reason": "blank", "text_found": []}'
    classroom = room([blank, blank])
    session_id = classroom.begin(CLASS)
    drawing_id = classroom.add_drawing(session_id, png)
    names = [name for name, _ in run(classroom, session_id, drawing_id)]
    assert names[-1] == "done", "without it the page reports a model outage over a kind refusal"


def test_a_refusal_is_in_the_class_language(room, png):
    blank = '{"verdict": "empty", "reason": "blank", "text_found": []}'
    classroom = room([blank, blank])
    session_id = classroom.begin({**CLASS, "language": "zh"})
    drawing_id = classroom.add_drawing(session_id, png)
    stopped = next(d for _, d in run(classroom, session_id, drawing_id) if d.get("status") == "stopped")
    assert not stopped["message"].isascii(), "a Chinese class hears Chinese"


def test_a_reply_uses_the_opening_the_child_actually_heard(room, png):
    """The second beat needs the first. Only something held open remembers it."""
    said = "the dog ran away from the house"
    reply = "So the dog ran away from your house. Where was he going?"
    classroom = room([ALLOW, GOOD, GROUNDED, CLEAN, reply, CLEAN, NOTHING_INVENTED, FOLLOWS])
    session_id = classroom.begin(CLASS)
    drawing_id = classroom.add_drawing(session_id, png)
    run(classroom, session_id, drawing_id)
    outputs = outputs_of(run(classroom, session_id, drawing_id, {"transcript": said}))
    assert outputs["beat"] == "reply"
    reply_prompt = classroom.client.prompts[4]
    assert GOOD in reply_prompt, "the reply prompt should carry the opening"
    assert said in reply_prompt, "and the words the child actually said"
    assert classroom.client.images[4], "the reply sees the drawing, so it can link the words to it"


class Routed(Scripted):
    """Writers from one queue; each judge answered by the key its prompt asks for.

    Judges run side by side, so a single queue hands their answers out in whatever order the
    threads reach it. Routing by what the prompt asks for keeps each answer with its judge.
    """

    ANSWERS = {'"verdict"': ALLOW, '"grounded"': GROUNDED, '"presumptive"': CLEAN,
               '"invented"': NOTHING_INVENTED, '{"world"': INSIDE, '{"same"': '{"same": true}'}

    def __init__(self, writes, questions=()):
        super().__init__(writes)
        self.questions = list(questions)
        self.judged = []

    def chat(self, prompt, images=(), *, system=None, max_tokens=None):
        from studio.providers.base import ChatResult

        if '"question_issues"' in prompt:
            text = self.questions.pop(0) if self.questions else FOLLOWS
        else:
            text = next((answer for key, answer in self.ANSWERS.items() if key in prompt), None)
        if text is None:
            return super().chat(prompt, images, system=system, max_tokens=max_tokens)
        self.judged.append(prompt)
        return ChatResult(text=text, input_tokens=10, output_tokens=10, reasoning_tokens=0,
                          cost_usd=0.0, latency_s=0.0, provider="fake", model="fake")


@pytest.fixture
def routed(tmp_path):
    def build(writes, questions=()):
        client = Routed(writes, questions)
        classroom = Classroom(tmp_path / "ledger.jsonl", clients={"vlm.studio": client, "vlm.director": client})
        classroom.ceiling_gb = float("inf")
        classroom.client = client
        return classroom
    return build


def test_a_later_reply_knows_the_whole_conversation(routed, png):
    first = "So the boat goes to the house. What happens when it arrives?"
    second = "So the traveller saw the lamp by the door. What does he want to tell the lamp?"
    classroom = routed([GOOD, first, second])
    sid = classroom.begin(CLASS)
    did = classroom.add_drawing(sid, png)
    run(classroom, sid, did)
    run(classroom, sid, did, {"transcript": "the boat goes to the house"})
    result = outputs_of(run(classroom, sid, did, {"transcript": "the traveller saw the lamp"}))
    assert result["question"] == "What does he want to tell the lamp?"
    writer = classroom.client.prompts[-1]
    assert "What happens when it arrives?" in writer, "the writer is shown the question it asked before"
    assert "the boat goes to the house" in writer, "and what the child said before"
    invention = [prompt for prompt in classroom.client.judged if '"invented"' in prompt][-1]
    assert "the boat goes to the house" in invention, (
        "a story the child told two turns ago is theirs, not the machine's invention"
    )


def test_a_reply_refused_every_time_gives_the_child_their_own_words_and_a_question(routed, png):
    """Operator: a child should never see "something went wrong" in the middle of their story."""
    happy = "So the boat goes to the house, and the captain is so happy. Who is waiting there?"
    classroom = routed([GOOD, happy, happy, happy, happy])
    sid = classroom.begin(CLASS)
    did = classroom.add_drawing(sid, png)
    run(classroom, sid, did)
    result = outputs_of(run(classroom, sid, did, {"transcript": "the boat goes to the house"}))
    shown = " ".join(str(result.get(key, "")) for key in ("text", "question"))
    assert "the boat goes to the house" in shown and "happy" not in shown
    assert result["question"] == "And then what happened?"


def test_a_question_that_makes_up_part_of_the_story_is_refused_on_every_attempt(routed, png):
    """Code review: it was refused once and shown on the next attempt."""
    presumes = "So the boat goes to the house. Why did the captain decide to leave?"
    invented = '{"question_issues": ["it states an event, activity or feeling the child never gave as if it happened"]}'
    classroom = routed([GOOD, presumes, presumes, presumes], questions=[invented, invented, invented])
    sid = classroom.begin(CLASS)
    did = classroom.add_drawing(sid, png)
    run(classroom, sid, did)
    result = outputs_of(run(classroom, sid, did, {"transcript": "the boat goes to the house"}))
    shown = " ".join(str(result.get(key, "")) for key in ("text", "question"))
    assert "captain" not in shown, "the made-up question never reaches the child"
    assert result["question"] == "And then what happened?"


def test_a_first_comment_refused_every_time_gives_the_studios_own_look_and_ask(routed, png):
    """The class page: a teacher got "something went wrong" for a first comment."""
    diminishing = "I see a messy little scribble. What is happening in it?"
    classroom = routed([diminishing, diminishing, diminishing, diminishing])
    sid = classroom.begin(CLASS)
    did = classroom.add_drawing(sid, png)
    result = outputs_of(run(classroom, sid, did))
    shown = " ".join(str(result.get(key, "")) for key in ("text", "question"))
    assert "messy" not in shown and "scribble" not in shown
    assert "I can see your picture." in shown and result["question"] == "Tell me, what did you draw?"


def test_a_smaller_question_refused_every_time_gives_the_studios_own(routed, png):
    diminishing = "Is it just a messy scribble?"
    classroom = routed([GOOD, diminishing, diminishing, diminishing, diminishing])
    sid = classroom.begin(CLASS)
    did = classroom.add_drawing(sid, png)
    run(classroom, sid, did)
    result = outputs_of(run(classroom, sid, did, {"rung": 2}))
    assert result["beat"] == "rung-2"
    shown = " ".join(str(result.get(key, "")) for key in ("text", "question"))
    assert "Which part of the picture would you like to talk about first?" in shown and "messy" not in shown


def test_a_question_the_judge_dislikes_buys_one_more_attempt(routed, png):
    repeated = "So the boat goes to the house. Where is the boat going?"
    revised = "So the boat goes to the house. Who is waiting there?"
    stale = '{"question_issues": ["asks again where the boat goes"]}'
    classroom = routed([GOOD, repeated, revised], questions=[stale])
    sid = classroom.begin(CLASS)
    did = classroom.add_drawing(sid, png)
    run(classroom, sid, did)
    result = outputs_of(run(classroom, sid, did, {"transcript": "the boat goes to the house"}))
    assert result["question"] == "Who is waiting there?"
    assert len(classroom.client.prompts) == 3, "the opening, the attempt sent back, and the one shown"


def test_skipping_the_newest_idea_is_scored_but_buys_no_rewrite(routed, png):
    """Qwen says it of nearly every reply (probe): a rewrite each time doubled the wait."""
    first = "So the boat goes to the house. Who is waiting there?"
    skips = ('{"question_issues": ["skips the most meaningful NEW thing in the latest answer to ask '
             'about a nearby object or a routine next action"]}')
    classroom = routed([GOOD, first], questions=[skips])
    sid = classroom.begin(CLASS)
    did = classroom.add_drawing(sid, png)
    run(classroom, sid, did)
    result = outputs_of(run(classroom, sid, did, {"transcript": "the boat goes to the house"}))
    assert result["question"] == "Who is waiting there?"
    assert len(classroom.client.prompts) == 2, "the opening and the reply, and no second attempt"


def test_a_child_is_never_left_without_a_reply_over_a_disliked_question(routed, png):
    """Operator: the rounds that felt broken ended in the hiccup line over taste."""
    first = "So the boat goes to the house. Where is the boat going?"
    again = "So the boat goes to the house. Where does the boat go next?"
    stale = '{"question_issues": ["asks where the boat goes, which the child said"]}'
    classroom = routed([GOOD, first, again], questions=[stale, stale])
    sid = classroom.begin(CLASS)
    did = classroom.add_drawing(sid, png)
    run(classroom, sid, did)
    result = outputs_of(run(classroom, sid, did, {"transcript": "the boat goes to the house"}))
    assert result["question"] == "Where does the boat go next?", "the rewrite is shown, not refused"


def test_a_reply_without_a_question_is_a_reply(routed, png):
    """Section 5a: none at all is fine once the child has said something whole."""
    whole = "So the dog barked and led them to their mum under the big tree, at the end of your long road."
    classroom = routed([GOOD, whole])
    sid = classroom.begin(CLASS)
    did = classroom.add_drawing(sid, png)
    run(classroom, sid, did)
    result = outputs_of(run(classroom, sid, did, {"transcript":
                                                  "the dog barked and led them to their mum under the big tree"}))
    assert result["beat"] == "reply" and not result["question"]
    assert not any('"question_issues"' in prompt for prompt in classroom.client.judged), (
        "a reply with no question is not sent to the question's judge"
    )


def test_a_forced_choice_is_rewritten_in_a_chinese_class(routed, png):
    choice = "小狗跑走了。它是去找妈妈，还是去找朋友？"
    open_one = "小狗跑走了。它想去哪里？"
    classroom = routed(["我看到一只黄色的太阳，下面有两个人。他们在做什么？", choice, open_one])
    sid = classroom.begin({"language": "zh", "entrance": "colour"})
    did = classroom.add_drawing(sid, png)
    run(classroom, sid, did)
    result = outputs_of(run(classroom, sid, did, {"transcript": "小狗跑走了"}))
    assert result["question"] == "它想去哪里？"


def test_a_yes_or_no_question_is_rewritten_in_a_chinese_class(routed, png):
    """Live on the Spark: five replies in five asked 是不是 or 吗, and the judge let them by."""
    closed = "它只能等小主人回来开门。它是不是在专心地等着？"
    open_one = "它只能等小主人回来开门。小主人开门的时候，它会做什么？"
    classroom = routed(["我看到一只黄色的太阳，下面有两个人。他们在做什么？", closed, open_one])
    sid = classroom.begin({"language": "zh", "entrance": "colour"})
    did = classroom.add_drawing(sid, png)
    run(classroom, sid, did)
    result = outputs_of(run(classroom, sid, did, {"transcript": "它只能等小主人回来开门"}))
    assert result["question"] == "小主人开门的时候，它会做什么？"


def test_a_closed_question_is_reworded_on_its_own(routed, png):
    """Probe on the Spark: rewriting the whole reply only asked 吗 again."""
    closed = "小狗跑走了，它是去找妈妈吗？"
    classroom = routed(["我看到一只黄色的太阳，下面有两个人。他们在做什么？", closed, "小狗跑走了，它要去哪里找妈妈？"])
    sid = classroom.begin({"language": "zh", "entrance": "colour"})
    did = classroom.add_drawing(sid, png)
    run(classroom, sid, did)
    result = outputs_of(run(classroom, sid, did, {"transcript": "小狗跑走了"}))
    assert (result["text"] + result["question"]).endswith("它要去哪里找妈妈？")
    assert "小狗跑走了，它是去找妈妈吗？" in classroom.client.prompts[-1], "the reply is handed back to fix its question"
    assert not classroom.client.images[-1], "rewording a question does not read the picture again"


def test_a_reply_asking_two_questions_is_reworded_to_one(routed, png):
    two = "小狗跑走了。它会找到妈妈吗？它要去哪里？"
    classroom = routed(["我看到一只黄色的太阳，下面有两个人。他们在做什么？", two, "小狗跑走了。它要去哪里？"])
    sid = classroom.begin({"language": "zh", "entrance": "colour"})
    did = classroom.add_drawing(sid, png)
    run(classroom, sid, did)
    result = outputs_of(run(classroom, sid, did, {"transcript": "小狗跑走了"}))
    assert result["question"] == "它要去哪里？"
    assert "more than one question" in classroom.client.prompts[-1]


def test_when_two_questions_stay_the_open_one_is_kept(routed, png):
    stubborn = "小狗跑走了。它会找到妈妈吗？它要去哪里？"
    classroom = routed(["我看到一只黄色的太阳，下面有两个人。他们在做什么？", stubborn, stubborn, stubborn])
    sid = classroom.begin({"language": "zh", "entrance": "colour"})
    did = classroom.add_drawing(sid, png)
    run(classroom, sid, did)
    result = outputs_of(run(classroom, sid, did, {"transcript": "小狗跑走了"}))
    assert (result["text"], result["question"]) == ("小狗跑走了。", "它要去哪里？")


def test_a_question_that_will_not_open_is_left_out(routed, png):
    """Section 5a: none at all is fine once the child has said something."""
    classroom = routed(["我看到一只黄色的太阳，下面有两个人。他们在做什么？",
                        "小狗跑走了，它跑得很快。它是去找妈妈吗？", "小狗跑走了，它跑得很快。是去找妈妈吗？",
                        "小狗跑走了，它跑得很快。它找到了吗？"])
    sid = classroom.begin({"language": "zh", "entrance": "colour"})
    did = classroom.add_drawing(sid, png)
    run(classroom, sid, did)
    result = outputs_of(run(classroom, sid, did, {"transcript": "小狗跑走了"}))
    assert result["beat"] == "reply" and not result["question"]
    assert "它跑得很快" in result["text"]


def test_a_smaller_question_knows_what_the_child_said(routed, png):
    reply = "So the purple one is your dog. Where is the dog going?"
    rung = "Is the dog running to the house, or to the tree?"
    classroom = routed([GOOD, reply, rung])
    sid = classroom.begin(CLASS)
    did = classroom.add_drawing(sid, png)
    run(classroom, sid, did)
    run(classroom, sid, did, {"transcript": "the purple one is my dog"})
    result = outputs_of(run(classroom, sid, did, {"rung": 2}))
    assert result["beat"] == "rung-2"
    assert "the purple one is my dog" in classroom.client.prompts[-1]
    assert classroom.client.images[-1], "a smaller question sees the drawing again"
    naming = [prompt for prompt in classroom.client.judged if '"presumptive"' in prompt][-1]
    assert "the purple one is my dog" in naming, "the child's name for the dog is theirs to use"


def test_a_rung_is_asked_when_the_child_said_nothing(room, png):
    # A rung is graded by rule 12 like any question, so a rung whose words the marker
    # list does not hold is put to the judge as well: hence INSIDE between the two.
    rung = "Is it daytime or night time in your picture?"
    classroom = room([ALLOW, GOOD, GROUNDED, CLEAN, rung, INSIDE, CLEAN])
    session_id = classroom.begin(CLASS)
    drawing_id = classroom.add_drawing(session_id, png)
    run(classroom, session_id, drawing_id)
    outputs = outputs_of(run(classroom, session_id, drawing_id, {"rung": 2}))
    assert outputs["beat"] == "rung-2"


def test_the_ledger_the_page_reads_is_the_ledger_on_disk(room, png):
    classroom = room([ALLOW, GOOD, GROUNDED, CLEAN])
    session_id = classroom.begin(CLASS)
    drawing_id = classroom.add_drawing(session_id, png)
    events = run(classroom, session_id, drawing_id)
    from_events = [data["ledger"] for _, data in events if data.get("ledger")]
    from_file = classroom.ledger_lines(session_id)
    assert len(from_file) == len(from_events)
    assert [line["stage"] for line in from_file] == ["studio-safety", "art-feedback"]
    assert all(line["gate"] == "pass" for line in from_file)


def test_the_ledger_the_page_reads_holds_no_drawing_and_no_feedback(room, png):
    classroom = room([ALLOW, GOOD, GROUNDED, CLEAN])
    session_id = classroom.begin(CLASS)
    drawing_id = classroom.add_drawing(session_id, png)
    run(classroom, session_id, drawing_id)
    written = json.dumps(classroom.ledger_lines(session_id))
    assert "pointy triangle rays" not in written
    assert "base64" not in written


def test_a_skill_that_is_not_built_says_so_rather_than_pretending(room, png):
    classroom = room([])
    session_id = classroom.begin(CLASS)
    drawing_id = classroom.add_drawing(session_id, png)
    started = classroom.request(session_id, "painting-to-scene", [drawing_id], {})
    classroom.run_request(started["request_id"])
    stopped = next(d for name, d in classroom.follow(started["request_id"]) if name == "done")
    assert "not open" in stopped["message"]


def test_an_unknown_skill_or_drawing_is_refused(room, png):
    classroom = room([])
    session_id = classroom.begin(CLASS)
    drawing_id = classroom.add_drawing(session_id, png)
    with pytest.raises(ValueError):
        classroom.request(session_id, "make-me-a-sandwich", [drawing_id], {})
    with pytest.raises(KeyError):
        classroom.request(session_id, "art-feedback", ["nope"], {})


def test_a_class_cannot_start_without_an_entrance(room):
    """Section 5a: the teacher picks it by hand, and nothing guesses it."""
    classroom = room([])
    with pytest.raises(ValueError):
        classroom.begin({"language": "en"})
    with pytest.raises(ValueError):
        classroom.begin({"language": "en", "entrance": "watercolour"})


@pytest.mark.parametrize(
    "text, question",
    [
        ("I see red. What is it?", "What is it?"),
        ("What is happening here?", ""),
        ("I see red lines.", ""),
    ],
)
def test_splitting_the_question_off_the_end(text, question):
    assert split_question(text)[1] == question


def test_a_clip_reaches_the_page_and_is_forgotten_at_end(room, png):
    from tests.making.test_animation import CLEAN, Editor
    editor = Editor()
    classroom = room([ALLOW] * 6 + [CLEAN], editor=editor.slot())
    session_id = classroom.begin(CLASS)
    drawing_id = classroom.add_drawing(session_id, png)
    started = classroom.request(session_id, "painting-to-animation", [drawing_id], {"hint": "lift one paw"})
    classroom.run_request(started["request_id"])
    outputs = outputs_of(list(classroom.follow(started["request_id"])))
    assert outputs["video_url"].startswith("data:video/mp4;base64,")
    assert "keyframe" not in outputs and "image_model" not in outputs and "choreography" not in outputs
    assert "lift one paw" in editor.calls[0]["instruction"]
    classroom.end(session_id)
    assert started["request_id"] not in classroom.requests


def test_a_request_for_the_retired_still_picture_is_refused_before_anything_runs(room, png):
    """The FLUX still picture was retired; an old page asking for one is told so."""
    from tests.making.test_animation import Editor
    editor = Editor()
    classroom = room([], editor=editor.slot())
    session_id = classroom.begin(CLASS)
    drawing_id = classroom.add_drawing(session_id, png)
    with pytest.raises(ValueError, match="still picture was retired"):
        classroom.request(session_id, "painting-to-animation", [drawing_id], {"hint": "hop", "media_kind": "image"})
    assert editor.calls == [] and classroom.requests == {}


def test_missing_editor_does_not_fall_back_to_chat_choreography(room, png):
    classroom = room([ALLOW])
    session_id = classroom.begin(CLASS)
    drawing_id = classroom.add_drawing(session_id, png)
    started = classroom.request(session_id, "painting-to-animation", [drawing_id], {})
    classroom.run_request(started["request_id"])
    stopped = next(d for name, d in classroom.follow(started["request_id"]) if name == "done")
    assert stopped["reason_code"] == "model_unavailable"
    assert len(classroom.client.prompts) == 1


def test_unavailable_image_credentials_do_not_disable_feedback_classroom(tmp_path, monkeypatch):
    import studio.classroom.classroom as module
    from studio.core.errors import ModelRefused
    client = Scripted([])
    monkeypatch.setattr(module, 'build_client', lambda _: client)
    def unavailable(config):
        if config.slot == 'video.animation':
            raise ModelRefused('image credential missing')
        from studio.providers.media import MediaSlot
        return MediaSlot(None, 'to_mesh', {}, {})
    monkeypatch.setattr(module, 'build_media_slot', unavailable)
    classroom = Classroom(tmp_path / 'ledger.jsonl', profile='local')
    assert classroom.editor is None
    assert classroom.begin(CLASS)
    assert classroom.health()['ok']
    classroom.close()


def test_health_counts_accepted_requests_until_they_finish(room, png):
    classroom = room([])
    session_id = classroom.begin(CLASS)
    drawing_id = classroom.add_drawing(session_id, png)
    started = classroom.request(session_id, "painting-to-animation", [drawing_id], {})
    assert classroom.health()["active_requests"] == 1
    classroom.cancel(session_id, started["request_id"])
    assert classroom.health()["active_requests"] == 0


def test_the_ledger_line_carries_the_cost_the_contract_names(room, png):
    """The page contract lists `cost` in every ledger line, beside `tokens`.

    It was never emitted. The value existed all along — the harness reads it off
    the meters into Entry.cost_usd — so the ledger view a judge is meant to read
    showed what a request spent in tokens and stayed silent about money.
    """
    classroom = room([ALLOW, GOOD, GROUNDED, CLEAN])
    session_id = classroom.begin(CLASS)
    drawing_id = classroom.add_drawing(session_id, png)
    run(classroom, session_id, drawing_id)
    lines = classroom.ledger_lines(session_id)
    assert lines, "a run with two stages should write two lines"
    assert all("cost" in line for line in lines)


def test_a_sentence_written_twice_is_shown_once_and_its_unmarked_question_is_still_asked(routed, png):
    """The class page: the child's sentence came back twice, and a question with no mark vanished."""
    doubled = ("So the boat goes to the house, all the way down the long road. "
               "So the boat goes to the house, all the way down the long road. Who is waiting there")
    classroom = routed([GOOD, doubled])
    sid = classroom.begin(CLASS)
    did = classroom.add_drawing(sid, png)
    run(classroom, sid, did)
    result = outputs_of(run(classroom, sid, did, {"transcript": "the boat goes to the house"}))
    assert result["text"] == "So the boat goes to the house, all the way down the long road."
    assert result["question"] == "Who is waiting there?"


def test_a_reply_that_asks_again_what_the_companion_already_asked_is_written_again(routed, png):
    """Seen in a sketch class, the same question two rounds running; the rule is one for both."""
    first = "So the boat goes to the house. What happens when it arrives?"
    again = "So the traveller saw the lamp by the door. What happens when it arrives?"
    fresh = "So the traveller saw the lamp by the door. What does he want to tell the lamp?"
    classroom = routed([GOOD, first, again, fresh])
    sid = classroom.begin(CLASS)
    did = classroom.add_drawing(sid, png)
    run(classroom, sid, did)
    run(classroom, sid, did, {"transcript": "the boat goes to the house"})
    result = outputs_of(run(classroom, sid, did, {"transcript": "the traveller saw the lamp"}))
    assert result["question"] == "What does he want to tell the lamp?"


def test_when_every_attempt_asks_again_the_child_hears_their_words_and_no_question_twice(routed, png):
    """Code review: the studio's own fallback question must not become the repeat it was avoiding."""
    first = "So the boat goes to the house. What happens when it arrives?"
    again = "So the traveller saw the lamp by the door. What happens when it arrives?"
    fallback_again = "So the traveller came home. And then what happened?"
    classroom = routed([GOOD, first] + [again] * 4 + [fallback_again] * 4)
    sid = classroom.begin(CLASS)
    did = classroom.add_drawing(sid, png)
    run(classroom, sid, did)
    run(classroom, sid, did, {"transcript": "the boat goes to the house"})
    second = outputs_of(run(classroom, sid, did, {"transcript": "the traveller saw the lamp"}))
    assert second["question"] == "And then what happened?", "their words and the studio's one open question"
    third = outputs_of(run(classroom, sid, did, {"transcript": "the traveller came home"}))
    shown = " ".join(str(third.get(key, "")) for key in ("text", "question"))
    assert "the traveller came home" in shown and "And then what happened?" not in shown
