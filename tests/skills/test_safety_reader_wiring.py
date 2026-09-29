"""How NVIDIA's safety model reaches the safety skill: its own slot, its own protocol, one seam.

`studio/classroom/classroom.py` cannot be written until it is split (the size guard refuses it), so the second
reader rides on the screener the classroom already hands to every conversation. These tests hold the
whole path: the slot, the client and the small server it speaks to, the pairing, and the two places
a conversation asks the skill.
"""

import json
import threading
from pathlib import Path

import pytest
from conftest import load_script

from studio.conversation.conversation import Conversation
from studio.core.errors import ModelUnavailable
from studio.core.ledger import Ledger
from studio.providers import build_client, build_safety_reader
from studio.providers.safetyreader import SafetyReaderClient, WithSecondLook
from studio.core.slots import SlotConfig, load_profile
from tests.making.test_animation import Editor
from tests.classroom.test_classroom import ALLOW, DRAWING, Scripted

SERVER = Path("skills/studio-safety/scripts/nemotron_server.py")
VIOLENCE = "User Safety: unsafe\nSafety Categories: Violence"


class Reader:
    def __init__(self, answers):
        self.answers, self.asked = list(answers), []

    def look(self, image, question):
        self.asked.append(question)
        return self.answers.pop(0)


@pytest.fixture
def served():
    """The skill's own server on a free port, with a stand-in for the model behind it."""
    module = load_script(SERVER, "nemotron_server_script")
    seen = []

    def answer(picture: bytes, question: str) -> str:
        seen.append((picture, question))
        return "User Safety: safe"

    server = module.serve(answer, port=0)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{server.server_address[1]}", seen
    server.shutdown()
    server.server_close()


def test_the_spark_plan_gives_the_model_a_slot_of_its_own():
    slot = load_profile("spark")["safety.reader"]
    assert slot.provider == "safetyreader" and slot.model == "Nemotron-3.5-Content-Safety"
    assert slot.options["base_url"] == "http://127.0.0.1:7140" and slot.options["size_gb"] == 11
    assert isinstance(build_safety_reader(slot), SafetyReaderClient)


def test_the_server_and_the_studio_agree_on_the_port():
    """The skill's script runs where the studio package is not installed, so it spells the number itself."""
    from studio.server import ports
    assert load_script(SERVER, "nemotron_server_for_port").PORT == ports.SAFETY_READER_PORT == 7140
    assert ports.SAFETY_READER_PORT in ports.REGISTERED


def test_the_reader_is_not_a_chat_model_and_asking_for_one_says_so():
    slot = SlotConfig("safety.reader", "safetyreader", "Nemotron-3.5-Content-Safety", {})
    with pytest.raises(Exception, match="safety reader"):
        build_client(slot)


def test_a_look_travels_to_the_server_and_the_answer_comes_back(served):
    address, seen = served
    picture = "data:image/png;base64,aGVsbG8="
    reader = SafetyReaderClient("Nemotron-3.5-Content-Safety", {"base_url": address})
    assert reader.look(picture, "Is it fit to be seen?") == "User Safety: safe"
    assert seen == [(b"hello", "Is it fit to be seen?")]


def test_the_server_refuses_what_is_not_a_picture_and_a_question(served):
    import httpx
    address, seen = served
    assert httpx.post(address + "/look", json={"image": "not a picture", "question": "q"}, trust_env=False).status_code == 400
    assert httpx.post(address + "/look", json={"image": "data:image/png;base64,aGVsbG8="}, trust_env=False).status_code == 400
    assert httpx.get(address + "/health", trust_env=False).json() == {"ready": True}
    assert seen == []


def test_a_server_that_is_not_there_is_unavailable_not_a_crash():
    reader = SafetyReaderClient("Nemotron-3.5-Content-Safety", {"base_url": "http://127.0.0.1:9", "timeout_s": 2})
    with pytest.raises(ModelUnavailable):
        reader.look("data:image/png;base64,aGVsbG8=", "q")


@pytest.mark.parametrize("body", [b"<html>502 Bad Gateway</html>", b"[1, 2]", b"null", b'{"answer": 7}', b'{"other": "x"}'])
def test_something_else_answering_at_that_address_is_unavailable_not_an_error_in_the_class(body):
    """A stale process, the wrong port after a restart, a proxy's page: a 200 that is not our server's answer."""
    import httpx
    transport = httpx.MockTransport(lambda request: httpx.Response(200, content=body))
    reader = SafetyReaderClient("Nemotron-3.5-Content-Safety", {}, client=httpx.Client(transport=transport))
    with pytest.raises(ModelUnavailable):
        reader.look("data:image/png;base64,aGVsbG8=", "q")


def test_a_deployment_whose_profile_names_the_slot_pairs_it_with_the_screener(monkeypatch, tmp_path):
    from studio.core import deployments
    profile = load_profile("stepfun")
    profile["safety.reader"] = SlotConfig("safety.reader", "safetyreader", "Nemotron-3.5-Content-Safety",
                                          {"base_url": "http://127.0.0.1:7140"})
    monkeypatch.setattr(deployments, "load_profile", lambda name: profile)
    monkeypatch.setenv("STEPFUN_API_KEY", "test-key-for-building-clients")
    paired = deployments.build_runtime("stepfun").clients["safety.image"]
    assert isinstance(paired, WithSecondLook) and isinstance(paired.second, SafetyReaderClient)


def test_every_class_gets_the_second_look_now_the_operator_has_said_so(monkeypatch):
    """No profile used to name the slot, and a test held that no class met the model until the
    operator said so. He has said so: StepFun First, the one deployment, now names it."""
    from studio.core import deployments
    monkeypatch.setenv("STEPFUN_API_KEY", "test-key-for-building-clients")
    slot = load_profile("stepfun")["safety.reader"]
    assert (slot.provider, slot.options["base_url"]) == ("safetyreader", "http://127.0.0.1:7140")
    assert isinstance(deployments.build_runtime("stepfun").clients["safety.image"], WithSecondLook)


def test_a_deployment_without_the_slot_runs_exactly_as_before(monkeypatch):
    from studio.core import deployments
    profile = {name: slot for name, slot in load_profile("stepfun").items() if name != "safety.reader"}
    monkeypatch.setattr(deployments, "load_profile", lambda name: profile)
    monkeypatch.setenv("STEPFUN_API_KEY", "test-key-for-building-clients")
    assert not isinstance(deployments.build_runtime("stepfun").clients["safety.image"], WithSecondLook)


def test_a_conversation_asks_the_second_reader_at_the_door_and_keeps_only_codes(tmp_path):
    reader = Reader([VIOLENCE])
    conversation = Conversation(DRAWING, Ledger(tmp_path / "ledger.jsonl"), entrance="colour", studio=Scripted([]),
                                director=Scripted([]), screener=WithSecondLook(Scripted([ALLOW]), reader))
    verdict = conversation._screen({})
    assert verdict.verdict == "soften" and verdict.teacher_codes == ("violence",) and len(reader.asked) == 1


def test_a_machine_made_picture_flagged_on_the_way_out_is_refused_and_not_made_again(tmp_path):
    editor, reader = Editor(), Reader(["User Safety: safe", VIOLENCE])
    conversation = Conversation(DRAWING, Ledger(tmp_path / "ledger.jsonl"), entrance="colour", studio=Scripted([]),
                                director=Scripted([]), editor=editor.slot(),
                                screener=WithSecondLook(Scripted([ALLOW]), reader))
    beat = conversation.animate("", "flagged-output")
    assert not beat.ok and not beat.plan and len(editor.calls) == 1
    assert "out" in load_script(Path("skills/studio-safety/scripts/nemotron.py"), "rule_for_wiring").QUESTIONS
    assert len(reader.asked) == 2 and reader.asked[0] != reader.asked[1], "the door and the way out ask different questions"
    ledger = (tmp_path / "ledger.jsonl").read_text()
    assert "second-look:violence" in ledger and "Violence" not in ledger


class Waiting(Reader):
    """A reader that can say whether it is back, and remembers who asked it to wait."""

    def __init__(self, answers):
        super().__init__(answers)
        self.waited = []

    def wait_ready(self, seconds):
        self.waited.append(seconds)
        return True


def _second_look_of_the_made_picture(tmp_path):
    from studio.server.stream import ledger_line
    made = [e for e in Ledger(tmp_path / "ledger.jsonl").entries() if e.stage == "animation"]
    return ledger_line(made[-1], "r")["second_look"]


def test_a_made_picture_that_passes_records_what_the_second_look_said(tmp_path):
    reader = Waiting(["User Safety: safe"] * 12)
    conversation = Conversation(DRAWING, Ledger(tmp_path / "ledger.jsonl"), entrance="colour", studio=Scripted([]),
                                director=Scripted([]), editor=Editor().slot(),
                                screener=WithSecondLook(Scripted([ALLOW] * 12), reader))
    assert conversation.animate("", "passing-output").ok
    assert _second_look_of_the_made_picture(tmp_path) == "clear"


def test_a_made_picture_the_second_look_could_not_see_goes_on_and_the_record_says_so(tmp_path):
    class GoneAfterTheDoor(Waiting):
        def look(self, image, question):
            if self.asked:
                raise ModelUnavailable("the safety reader stepped aside for a clip")
            return super().look(image, question)

    reader = GoneAfterTheDoor(["User Safety: safe"])
    conversation = Conversation(DRAWING, Ledger(tmp_path / "ledger.jsonl"), entrance="colour", studio=Scripted([]),
                                director=Scripted([]), editor=Editor().slot(),
                                screener=WithSecondLook(Scripted([ALLOW] * 12), reader))
    assert conversation.animate("", "unseen-output").ok, "a look it cannot take stops nothing"
    assert _second_look_of_the_made_picture(tmp_path) == "unavailable"


def test_a_clip_waits_for_the_reader_that_stepped_aside_for_it_and_the_door_never_waits(tmp_path):
    reader = Waiting(["User Safety: safe"] * 12)
    conversation = Conversation(DRAWING, Ledger(tmp_path / "ledger.jsonl"), entrance="colour", studio=Scripted([]),
                                director=Scripted([]), editor=Editor().slot(),
                                screener=WithSecondLook(Scripted([ALLOW] * 12), reader))
    conversation._screen({})
    assert reader.waited == [], "a child's drawing is never held at the door"
    assert conversation.animate("", "a-clip").ok and len(reader.waited) == 1 and reader.waited[0] >= 60


def test_a_reader_that_has_answered_before_is_waited_for_and_one_that_never_has_is_not(served):
    import time as clock
    url, _ = served
    client = SafetyReaderClient("Nemotron-3.5-Content-Safety", {"base_url": url})
    assert client.wait_ready(5)
    never = SafetyReaderClient("Nemotron-3.5-Content-Safety", {"base_url": "http://127.0.0.1:9"})
    started = clock.monotonic()
    assert not never.wait_ready(30) and clock.monotonic() - started < 3, "a reader never seen is not waited for"
    client.look("data:image/png;base64,iVBORw0KGgo=", "is it safe?")
    client.base_url = "http://127.0.0.1:9"
    started = clock.monotonic()
    assert not client.wait_ready(0.5, pause=0.1) and clock.monotonic() - started >= 0.5, "one seen before is waited for"


def test_the_pairing_answers_as_the_four_verdict_client_in_every_other_way():
    first, reader = Scripted([]), Reader([])
    first.model, first.options = "step-3.7-flash", {"reasoning_effort": "high"}
    first.__deepcopy__ = lambda memo: first          # a copy must never become the first client alone
    paired = WithSecondLook(first, reader)
    assert paired.model == "step-3.7-flash" and paired.options is first.options and paired.second is reader
    with pytest.raises(AttributeError):
        paired.__deepcopy__
