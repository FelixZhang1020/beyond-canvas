"""Words reach the page while the model writes them (operator).

The teacher watched "model working, 6 seconds" over every report and reply, then
got the whole text at once. Now a text model streams whenever the harness is
listening for a stage the page shows, and the page is sent the text so far.
These read as the promises that change makes: who streams, who does not, what
the page is told, and that the finished call is the same call it always was.
"""
import json
from concurrent.futures import ThreadPoolExecutor

import httpx
import pytest

from studio.core import harness as harness_module
from studio.server import textstream
from studio.core.errors import EmptyCompletion, ModelUnavailable
from studio.core.harness import Harness, Stage, Transition
from studio.core.ledger import Ledger
from studio.providers import streaming
from studio.providers.llamacpp import LlamaCppClient
from studio.providers.stepfun import StepFunClient
from studio.server.stream import Stream


def sse(*pieces, finish="stop", usage=None, reasoning=()):
    """A streamed answer shaped as StepFun sent it: thinking first, then the words."""
    lines = [{"model": "step-3.7-flash", "choices": [{"delta": {"role": "assistant", "content": ""}}]}]
    lines += [{"choices": [{"delta": {"content": "", "reasoning_content": r}}]} for r in reasoning]
    lines += [{"choices": [{"delta": {"content": p}}]} for p in pieces]
    lines.append({"choices": [{"delta": {"content": ""}, "finish_reason": finish}]})
    lines.append({"choices": [], "usage": usage or {"prompt_tokens": 39, "completion_tokens": 95}})
    return "".join(f"data: {json.dumps(line, ensure_ascii=False)}\n\n" for line in lines) + "data: [DONE]\n\n"


def stepfun(handler):
    return StepFunClient("step-3.7-flash", api_key="k", client=httpx.Client(transport=httpx.MockTransport(handler)))


def streamed(text):
    return httpx.Response(200, text=text, headers={"content-type": "text/event-stream"})


# The providers ---------------------------------------------------------------

def test_a_stream_is_read_back_into_the_answer_a_plain_call_would_have_given():
    heard = []
    payload = streaming.read(sse("太阳", "很亮。", reasoning=("We need",)).splitlines(), heard.append, "m")
    assert heard == ["太阳", "太阳很亮。"], "the listener gets the whole text so far, never a piece"
    assert payload["choices"][0]["message"]["content"] == "太阳很亮。"
    assert payload["choices"][0]["finish_reason"] == "stop"
    assert payload["usage"]["completion_tokens"] == 95
    assert payload["model"] == "step-3.7-flash"


def test_stepfun_streams_only_when_someone_is_listening():
    bodies = []

    def answer(request):
        body = json.loads(request.content)
        bodies.append(body)
        if body.get("stream"):
            return streamed(sse("A ", "bear."))
        return httpx.Response(200, json={"choices": [{"message": {"content": "A bear."}, "finish_reason": "stop"}],
                                         "usage": {"prompt_tokens": 1, "completion_tokens": 2}})

    client, heard = stepfun(answer), []
    assert client.chat("hi").text == "A bear."
    with textstream.listening(heard.append):
        result = client.chat("hi")
    assert "stream" not in bodies[0], "a call nobody watches is made exactly as before"
    assert bodies[1]["stream"] is True and bodies[1]["stream_options"] == {"include_usage": True}
    assert heard == ["A ", "A bear."]
    assert (result.text, result.input_tokens, result.output_tokens) == ("A bear.", 39, 95)


def test_a_streamed_answer_that_ran_out_of_room_is_still_refused():
    client = stepfun(lambda request: streamed(sse(finish="length", reasoning=("thinking",))))
    with textstream.listening(lambda text: None), pytest.raises(EmptyCompletion):
        client.chat("hi")


def test_a_busy_endpoint_is_still_a_busy_endpoint_when_streaming():
    client = stepfun(lambda request: httpx.Response(429, text="slow down"))
    with textstream.listening(lambda text: None), pytest.raises(ModelUnavailable, match="429"):
        client.chat("hi")


def test_the_first_voice_streams_too_and_leaves_out_its_prefill():
    def answer(request):
        assert json.loads(request.content)["stream"] is True
        return streamed(sse("<think></think>", "Two ", "shapes."))

    client = LlamaCppClient("qwen", options={"assistant_prefill": "<think></think>"},
                            client=httpx.Client(transport=httpx.MockTransport(answer)))
    heard = []
    with textstream.listening(heard.append):
        assert client.chat("hi").text == "Two shapes."
    assert heard == ["", "Two ", "Two shapes."]


def test_a_stop_pressed_while_words_arrive_ends_the_call_there():
    """The class raises from the listener when the teacher presses Stop, and that must
    leave the provider at once rather than be caught as a model failure."""
    class Stopped(Exception):
        pass

    def stop(text):
        raise Stopped()

    client = stepfun(lambda request: streamed(sse("one ", "two ", "three")))
    with textstream.listening(stop), pytest.raises(Stopped):
        client.chat("hi")


def test_the_judges_threads_never_stream():
    """The rule judges run on a thread pool; the listener does not follow them there,
    so a verdict is never sent to the page as if it were the child's words."""
    with textstream.listening(lambda text: None), ThreadPoolExecutor(1) as pool:
        assert pool.submit(textstream.current).result() is None


def test_the_words_shown_are_redacted_like_the_words_kept():
    heard = []
    with textstream.listening(heard.append), textstream.shown_as(lambda text: text.replace("Lily", "")):
        textstream.current()("Lily drew a sun")
    assert heard == [" drew a sun"]
    with textstream.shown_as(str.upper):
        assert textstream.current() is None, "with nobody listening nothing is set up to stream"


# The harness -------------------------------------------------------------------

@pytest.fixture
def ledger(tmp_path):
    return Ledger(tmp_path / "ledger.jsonl")


def writer(*pieces):
    """A skill whose model streams these pieces, as a streaming provider would."""
    def run(inputs):
        listener, text = textstream.current(), ""
        for piece in pieces:
            text += piece
            if listener:
                listener(text)
        return text
    return run


class Watcher:
    def __init__(self, wanted=("teacher-review",)):
        self.heard: list[Transition] = []
        self.wants_text = lambda stage: stage.skill in wanted

    def __call__(self, transition):
        self.heard.append(transition)


def test_the_harness_passes_on_the_words_of_a_stage_the_page_shows(ledger, monkeypatch):
    monkeypatch.setattr(harness_module, "WRITING_EVERY_S", 0)
    watcher = Watcher()
    Harness(ledger, observe=watcher).run([Stage("review", "teacher-review", writer("A ", "fine ", "sun."))], {})
    assert [t.draft for t in watcher.heard if t.status == "writing"] == ["A ", "A fine ", "A fine sun."]


def test_words_go_at_most_every_so_often_and_the_last_always_goes(ledger):
    watcher = Watcher()
    Harness(ledger, observe=watcher).run([Stage("review", "teacher-review", writer(*"abcdefgh"))], {})
    written = [t.draft for t in watcher.heard if t.status == "writing"]
    assert written[0] == "a" and written[-1] == "abcdefgh"
    assert len(written) == 2, "eight pieces in a moment are two updates, not eight"


def test_a_stage_the_page_does_not_show_is_not_streamed(ledger):
    listening = []
    stage = Stage("screen", "studio-safety", lambda inputs: listening.append(textstream.current()) or "allow")
    watcher = Watcher()
    Harness(ledger, observe=watcher).run([stage], {})
    assert listening == [None], "the provider is never asked to stream a safety verdict"
    assert not [t for t in watcher.heard if t.status == "writing"]


def test_a_rewrite_after_a_failed_check_starts_again_from_nothing(ledger, monkeypatch):
    monkeypatch.setattr(harness_module, "WRITING_EVERY_S", 0)
    drafts = iter([writer("Bad ", "line?"), writer("Good ", "line.")])
    stage = Stage("review", "teacher-review", lambda inputs: next(drafts)(inputs),
                  gate=lambda text: ("Good" in text, "rule"))
    watcher = Watcher()
    Harness(ledger, observe=watcher).run([stage], {})
    order = [(t.status, t.draft) for t in watcher.heard if t.status in ("writing", "fail")]
    assert order == [("writing", "Bad "), ("writing", "Bad line?"), ("fail", ""),
                     ("writing", "Good "), ("writing", "Good line.")]


# What the page is told ---------------------------------------------------------

def page_hears(skill, *transitions):
    from studio.core.harness import Stage as S
    stream, stage = Stream(), S("beat", skill, lambda inputs: None)
    observe = stream.observer("r1")
    for status, draft in transitions:
        observe(Transition(stage, status, draft=draft))
    stream.finish()
    return [data.get("partial") for _, data in stream.follow() if data.get("partial")], observe


def test_the_observation_and_the_question_arrive_apart_as_done_will_send_them():
    partials, _ = page_hears("art-feedback", ("writing", "我看见一只熊。"), ("writing", "我看见一只熊。它在做什么？"))
    assert partials == [
        {"text": "我看见一只熊。", "question": "", "writing": True, "revised": False},
        {"text": "我看见一只熊。", "question": "它在做什么？", "writing": True, "revised": False},
    ]


def test_words_written_after_a_failed_check_are_marked_as_a_rewrite():
    partials, _ = page_hears("teacher-review", ("writing", "First."), ("fail", ""), ("writing", "Second."))
    assert [(p["text"], p["revised"]) for p in partials] == [("First.", False), ("Second.", True)]


def test_a_story_outline_is_shown_as_its_passages_not_its_json():
    written = '[{"drawing_id": "a", "text": "小熊出门了。"}, {"drawing_id": "b", "text": "它看见\\"太'
    partials, _ = page_hears("story-outline", ("writing", '[{"drawing_id": "a"'), ("writing", written))
    assert partials == [{"text": '小熊出门了。\n\n它看见"太', "writing": True, "revised": False}]


def test_only_the_skills_whose_words_the_page_shows_are_streamed():
    partials, observe = page_hears("studio-safety", ("writing", '{"verdict": "allow"}'))
    assert partials == []
    wanted = {skill: observe.wants_text(Stage("x", skill, lambda inputs: None))
              for skill in ("art-feedback", "teacher-review", "scene-description", "story-outline",
                            "studio-safety", "painting-to-figure", "sketch-to-3d")}
    assert [skill for skill, yes in wanted.items() if yes] == [
        "art-feedback", "teacher-review", "scene-description", "story-outline"]


# Through a class ----------------------------------------------------------------

def test_a_teacher_review_in_a_class_reaches_the_page_while_it_is_written(tmp_path, monkeypatch):
    """The whole path, as a class runs it: the class's own watcher (which stops a request
    the teacher cancelled) must still ask for the words, or nothing streams at all."""
    from pathlib import Path
    from studio.classroom.classroom import Classroom
    from studio.classroom.portfolio import Portfolio
    from studio.providers.base import ChatResult

    monkeypatch.setattr(harness_module, "WRITING_EVERY_S", 0)
    report = "画面以明亮的黄色太阳和蓝色背景形成清晰的色彩对照，主体轮廓在背景中显得突出。" * 8
    listened = {}

    class Model:
        def __init__(self, name, reply):
            self.name, self.reply = name, reply

        def chat(self, prompt, images=(), **kwargs):
            listener = textstream.current()
            listened[self.name] = listener is not None
            if listener:
                for end in range(40, len(self.reply) + 40, 40):
                    listener(self.reply[:end])
            return ChatResult(self.reply, 2, 3, 0, 0, 0, "test", "test")

    screen = Model("screen", '{"verdict":"allow","reason":"drawing","text_found":[]}')
    room = Classroom(tmp_path / "ledger.jsonl", clients={"vlm.studio": screen, "vlm.director": screen,
                                                        "vlm.teacher": Model("teacher", report)},
                     portfolio=Portfolio(tmp_path / "portfolio.sqlite3"))
    sid = room.begin({"language": "zh", "entrance": "colour"})
    did = room.add_drawing(sid, Path("skills/art-feedback/evals/files/dog-sun.png").read_bytes())
    rid = room.request(sid, "teacher-review", [did], {})["request_id"]
    room.run_request(rid)
    events = list(room.follow(rid))
    room.end(sid)
    written = [data["partial"]["text"] for name, data in events if (data.get("partial") or {}).get("writing")]
    assert written and written[-1] == report and len(written[0]) < len(report)
    assert listened == {"screen": False, "teacher": True}, "the safety look is never streamed"
    assert next(data for name, data in events if name == "done")["outputs"]["text"] == report


# The code review ---------------------------------------------------------------

def test_a_name_on_the_drawing_is_never_shown_in_part_while_it_is_written():
    """"Alice S" reached the page, and its replay, before "Alice Smith" was whole enough to remove."""
    from types import SimpleNamespace
    from studio.conversation.conversation import Conversation, _load_skill
    talk = Conversation.__new__(Conversation)
    talk.verdict = SimpleNamespace(text_found=("Alice Smith",))
    talk.safety = _load_skill("safety_skill", "skills/studio-safety/scripts/safety.py")
    reply = "What a bright sun, Alice Smith! Who is holding the kite?"
    heard = []
    with textstream.listening(heard.append):
        kept = talk._redacting(writer(*reply))({})
    assert "Alice" not in kept and heard[-1] == kept
    after_sun = [text.split("sun,", 1)[1].lstrip() for text in heard if "sun," in text]
    assert after_sun and not [text for text in after_sun if text.startswith("A")], "part of the name was shown"
    assert any(text.startswith("What a bright sun,") for text in heard), "the words before the name still stream"


def test_the_ending_held_back_is_only_ever_the_start_of_something_found():
    assert textstream.unfinished_cut("the sun is Ali", ("Alice Smith",)) == "the sun is "
    assert textstream.unfinished_cut("the sun is Alex", ("Alice Smith",)) == "the sun is Alex"
    assert textstream.unfinished_cut("a sun", ("A",)) == "a sun", "a one-letter find is not redacted, so not held"


def test_a_stream_that_stops_before_it_says_it_is_finished_is_an_outage():
    """A connection that closed cleanly partway through handed back half an answer as a whole one."""
    cut = sse("太阳", "很亮。").split("data: ")
    no_end = "data: ".join(cut[:4])      # the words, but no finish reason and no closing line
    with pytest.raises(ModelUnavailable, match="before its answer was finished"):
        streaming.read(no_end.splitlines(), lambda text: None, "m")
    closed_without_done = sse("太阳").replace("data: [DONE]\n\n", "")
    assert streaming.read(closed_without_done.splitlines(), lambda text: None, "m")["choices"][0]["finish_reason"] == "stop"


def test_two_found_strings_that_overlap_are_both_still_removed_while_written():
    """Code review: cutting before the redaction turned "Hello Alice Smith" into "Hello Alice"."""
    from types import SimpleNamespace
    from studio.conversation.conversation import Conversation, _load_skill
    talk = Conversation.__new__(Conversation)
    talk.verdict = SimpleNamespace(text_found=("Alice Smith", "Smithson"))
    talk.safety = _load_skill("safety_skill", "skills/studio-safety/scripts/safety.py")
    heard = []
    with textstream.listening(heard.append):
        talk._redacting(writer("Hello Alice Smith"))({})
    assert all("Alice" not in text for text in heard), heard


def test_the_words_of_a_books_scene_say_which_drawing_they_are_about():
    """Operator: while a book was written the page could not tell which picture a scene was for."""
    from studio.server.stream import Stream
    from studio.core.harness import Stage, Transition
    stream = Stream()
    observe = stream.observer("r1")
    stage = Stage("scene-description-d7fe5251374b", "scene-description", lambda inputs: "")
    observe(Transition(stage, "writing", draft="A dog by a blue house."))
    name, data = stream.updates[-1]
    assert data["stage"] == "scene-description" and data["name"] == "scene-description-d7fe5251374b"
