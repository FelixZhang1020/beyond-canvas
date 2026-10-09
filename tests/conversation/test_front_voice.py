"""Qwen3.6 on the Spark writes the class's chat lines; the studio's own writer is asked whenever it cannot, and
under StepFun First that is the same Qwen, so while it steps aside for a clip the chat waits for it to load again.

Operator decision (docs/measured/chat-speed-and-front-voice.md): a first comment
took about forty seconds from Step 3.7 Flash, which always thinks first, and about one from Qwen3.6 with
its thinking off. The hand-over below is what keeps a class whole whenever the first voice gives no line.
"""

import importlib
import socket
import sys
from pathlib import Path

import pytest

from studio.conversation.conversation import Conversation
from studio.core.errors import ModelUnavailable
from studio.core.ledger import Ledger
from studio.providers.base import ChatResult
from studio.providers.frontvoice import FrontFirst, StandIn, WithFrontVoice
from studio.providers.llamacpp import LlamaCppClient
from studio.core.slots import load_profile

DRAWING = "skills/art-feedback/evals/files/dog-sun.png"
SPARK = Path("deploy/spark").resolve()


class Voice:
    """A writer that remembers what it was asked, and can be away."""

    def __init__(self, name, away=False):
        self.name, self.away, self.prompts = name, away, []

    def chat(self, prompt, images=(), *, system=None, max_tokens=None):
        self.prompts.append(prompt)
        if self.away:
            raise ModelUnavailable(f"{self.name} stepped aside for a clip")
        text = ('{"grounded": ["a", "b"], "presumptive": [], "invented": []}'
                if "annotator" in (system or "") or "Here is a child" in prompt
                else "我看到一只黄色的小狗在太阳下面跑。它要跑去哪里呢？")
        return ChatResult(text, 1, 1, 0, 0.0, 0.0, "fake", self.name)


def talk(tmp_path, qwen, step):
    conversation = Conversation(DRAWING, Ledger(tmp_path / "ledger.jsonl"), entrance="colour", language="zh",
                                studio=WithFrontVoice(step, qwen), director=Voice("judge"))
    conversation.verdict = type("V", (), {"may_proceed": True, "verdict": "allow", "text_found": ()})()
    return conversation


def test_the_opening_is_written_by_the_first_voice_and_step_is_not_asked(tmp_path):
    qwen, step = Voice("qwen"), Voice("step")
    talk(tmp_path, qwen, step).open()
    assert qwen.prompts, "the first voice wrote the opening"
    assert step.prompts == [], "Step 3.7 Flash is not asked to write while the first voice answers"


def test_while_the_first_voice_is_away_step_writes_the_same_line(tmp_path):
    qwen, step = Voice("qwen", away=True), Voice("step")
    talk(tmp_path, qwen, step).open()
    assert step.prompts and step.prompts[0] == qwen.prompts[0], "the very same call went to Step"


def test_everything_else_the_studio_client_does_stays_with_step():
    qwen, step = Voice("qwen"), Voice("step")
    studio = WithFrontVoice(step, qwen)
    studio.chat("write a storybook page")
    assert step.prompts == ["write a storybook page"] and qwen.prompts == []
    assert studio.name == "step", "the studio client is otherwise unchanged"


def test_a_first_voice_with_nothing_listening_falls_back_at_once():
    """The real path when Qwen is paused: its port refuses, and the class hears Step instead."""
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        port = probe.getsockname()[1]
    qwen = LlamaCppClient("qwen3.6-35b-a3b", {"base_url": f"http://127.0.0.1:{port}", "timeout_s": 5})
    step = Voice("step")
    assert FrontFirst(qwen, step).chat("hello").model == "step"


def test_each_hand_over_to_step_is_said_in_the_log_without_the_words(capsys):
    FrontFirst(Voice("qwen", away=True), Voice("step")).chat("the child said the dog ran away")
    said = capsys.readouterr().err
    assert "first voice gave no line (ModelUnavailable)" in said and "dog" not in said


def test_stepfun_first_names_the_first_voice_with_its_thinking_off():
    slot = load_profile("stepfun")["vlm.front"]
    assert (slot.provider, slot.model) == ("llamacpp", "qwen3.6-35b-a3b")
    assert slot.options["base_url"] == "http://127.0.0.1:7160"
    body = LlamaCppClient(slot.model, slot.options)._body("hi", (), None, None)
    assert body["chat_template_kwargs"] == {"enable_thinking": False}
    assert "chat_template_kwargs" not in LlamaCppClient("other", {})._body("hi", (), None, None)


def test_the_class_runtime_carries_the_first_voice_on_the_studio_client():
    from studio.core.deployments import build_runtime
    from studio.server import ports
    studio = build_runtime("stepfun").clients["vlm.studio"]
    assert isinstance(studio, WithFrontVoice) and studio.front.front.model == "qwen3.6-35b-a3b"
    assert ports.FRONT_VOICE_PORT == 7160 and ports.FRONT_VOICE_PORT in ports.REGISTERED



def test_the_teacher_review_and_the_creation_drafts_are_written_by_the_first_voice_too():
    """Operator: every word written for the child or the teacher. The
    writer behind the first voice and the checks are Qwen too: no Step in anything a person waits for,
    until Qwen is away (the stand-in, below)."""
    from studio.core.deployments import build_runtime
    clients = build_runtime("stepfun").clients
    for writer in ("vlm.teacher", "vlm.creation"):
        assert isinstance(clients[writer], FrontFirst), writer
        assert clients[writer].front.model == "qwen3.6-35b-a3b" and clients[writer].model == "qwen3.6-35b-a3b"
    for check in ("vlm.director", "safety.image"):
        assert clients[check].model == "qwen3.6-35b-a3b", check
    for check in ("vlm.director", "safety.image", "vlm.figure", "vlm.figure.look"):
        assert not isinstance(clients[check], (FrontFirst, WithFrontVoice)), check


def test_while_qwen_is_away_step_stands_in_for_the_chat_its_judges_and_the_screen():
    """Operator: while Qwen has stepped aside for the Spark's clip, Step 3.7 Flash takes the class over
    rather than the chat stopping for the twenty minutes the clip and the reload take. It is behind every
    Qwen slot a person waits for, and behind the first voice's own hand-over."""
    from studio.core.deployments import build_runtime
    clients = build_runtime("stepfun").clients
    for name in ("vlm.director", "safety.image", "vlm.studio"):
        slot = clients[name].studio if name == "vlm.studio" else clients[name].first if name == "safety.image" else clients[name]
        assert isinstance(slot, StandIn) and slot.first.model == "qwen3.6-35b-a3b", name
        assert slot.standin.model == "step-3.7-flash" and slot.model == "qwen3.6-35b-a3b", "settings read as Qwen's"
    assert isinstance(clients["vlm.studio"].front.behind, StandIn), "the first voice hands over to Qwen, then Step"
    # NVIDIA's second look rides outside the stand-in, so the door and the way out keep it, and the clip's
    # wait for Qwen still reaches Qwen's own client through the stand-in (conversation.py reads both off the screener).
    screen = clients["safety.image"]
    assert screen.second.base_url.endswith(":7140") and isinstance(screen.first, StandIn)
    assert screen.first.wait_ready.__self__ is screen.first.first, "wait_ready is Qwen's, not Step's"
    for writer in ("vlm.teacher", "vlm.creation"):
        assert isinstance(clients[writer].behind, StandIn) and clients[writer].behind.standin.model == "step-3.7-flash"
    assert clients["vlm.sketch"].model == "step-3.7-flash" and not isinstance(clients["vlm.sketch"], StandIn)


def test_the_stand_in_answers_only_when_the_first_model_gives_nothing_and_never_a_cancel(capsys):
    from studio.core.errors import ModelCancelled
    qwen, step = Voice("qwen"), Voice("step")
    assert StandIn(qwen, step).chat("judge this").model == "qwen" and step.prompts == []
    qwen, step = Voice("qwen", away=True), Voice("step")
    assert StandIn(qwen, step).chat("judge this").model == "step" and step.prompts == ["judge this"]
    assert "gave no answer (ModelUnavailable)" in capsys.readouterr().err

    class Cancelled(Voice):
        def chat(self, prompt, images=(), *, system=None, max_tokens=None):
            raise ModelCancelled("the teacher pressed stop")
    step = Voice("step")
    with pytest.raises(ModelCancelled):
        StandIn(Cancelled("qwen"), step).chat("judge this")
    assert step.prompts == [], "a cancel is not an answer the stand-in should give"


def test_with_qwen_away_the_opening_is_written_and_judged_by_step(tmp_path):
    qwen, step, judge, stepjudge = Voice("qwen", away=True), Voice("step"), Voice("judge", away=True), Voice("stepjudge")
    conversation = Conversation(DRAWING, Ledger(tmp_path / "ledger.jsonl"), entrance="colour", language="zh",
                                studio=WithFrontVoice(StandIn(qwen, step), qwen), director=StandIn(judge, stepjudge))
    conversation.verdict = type("V", (), {"may_proceed": True, "verdict": "allow", "text_found": ()})()
    conversation.open()
    assert step.prompts, "Step wrote the opening"
    assert stepjudge.prompts and judge.prompts, "every judge Qwen could not answer was asked of Step"


def test_while_the_first_voice_is_away_for_a_clip_step_writes_the_review_and_the_drafts():
    """Since two lanes a review or a draft can be asked for while a clip is made, with Qwen stopped for it."""
    for asked in ("teacher review", "scene description", "story outline"):
        qwen, step = Voice("qwen", away=True), Voice("step")
        written = FrontFirst(qwen, step).chat(asked, max_tokens=12000)
        assert written.model == "step" and qwen.prompts == [asked] and step.prompts == [asked]


def test_the_first_voice_is_never_asked_for_more_than_its_window_holds():
    seen = []

    class Qwen(Voice):
        def chat(self, prompt, images=(), *, system=None, max_tokens=None):
            seen.append(max_tokens)
            return super().chat(prompt, images, system=system, max_tokens=max_tokens)
    FrontFirst(Qwen("qwen"), Voice("step")).chat("draft", max_tokens=12000)
    FrontFirst(Qwen("qwen"), Voice("step")).chat("line")
    assert seen == [4000, None]

# On the Spark: the first voice steps aside for a clip ------------------------------------------------


class Box:
    """MemAvailable as measured on the node: 34 GiB free with the 3D model, the first voice and the
    safety reader all loaded, and a clip that got its room only once all three were stopped. The 3D
    model gave back about 16 GiB there, not the 31 once counted for it."""

    FREES = {"beyond-canvas-trellis-resident": 16, "qwen-front": 50, "nemotron-safety": 11}

    def __init__(self, available=34):
        self.free, self.up, self.stopped = available, set(self.FREES), []

    def available(self):
        return self.free

    def run(self, argv, **kwargs):
        if argv[:2] == ["docker", "stop"] and argv[-1] in self.up:
            self.stopped.append(argv[-1])
            self.up.discard(argv[-1])
            self.free += self.FREES[argv[-1]]
        out = "true" if argv[:2] == ["docker", "inspect"] and argv[-1] in self.up else ""
        return type("Done", (), {"returncode": 0, "stdout": out, "stderr": ""})()


@pytest.fixture
def spark(monkeypatch, tmp_path):
    monkeypatch.syspath_prepend(str(SPARK))
    module = importlib.import_module("media_spark")
    waited = []

    def world(available=34):
        box = Box(available)
        monkeypatch.setattr(module, "RESIDENT", tmp_path / "resident")
        monkeypatch.setattr(module.memory_guard, "available_gib", box.available)
        monkeypatch.setattr(module.memory_guard, "total_gib", lambda: 121.69)
        monkeypatch.setattr(module, "trellis_ready", lambda: "beyond-canvas-trellis-resident" in box.up)
        monkeypatch.setattr(module.subprocess, "run", box.run)
        monkeypatch.setattr(module.time, "sleep", waited.append)
        return module, box, waited
    yield world
    sys.modules.pop("media_spark", None)


def test_a_clip_gets_its_room_from_the_3d_model_and_the_first_voice_and_the_first_voice_comes_back(spark):
    module, box, waited = spark()
    assert module.room_for("wan2.2-i2v-a14b")
    assert box.stopped == ["beyond-canvas-trellis-resident", "qwen-front"], "the safety reader is never asked"
    assert len(waited) <= 6, "each stop waits only until the freed memory settles, not 30 s under the lock"
    assert (module.RESIDENT / "front-paused").is_file(), "it loads again only once the clip lifts the pause"
    module.resume_front()
    assert not (module.RESIDENT / "front-paused").exists()


def test_a_3d_job_on_the_loaded_model_leaves_the_first_voice_talking(spark):
    module, box, _ = spark()
    assert module.room_for("trellis2") and box.stopped == []


def test_a_storybooks_pictures_fit_beside_everything_and_short_of_room_set_the_3d_model_aside_never_the_first_voice(spark):
    """A book's pages (FLUX.2 Klein 4B, 22 GiB) are drawn while the teacher talks: under the ceiling they fit
    beside the three loaded models; short of room the 3D model steps aside and the chat voice stays; short of
    room even then, the page is refused rather than the voice or the safety reader stopped."""
    module, box, _ = spark()
    assert module.room_for("flux") and box.stopped == []
    module, box, _ = spark(available=20)
    assert module.room_for("flux") and box.stopped == ["beyond-canvas-trellis-resident"]
    module, box, _ = spark(available=5)
    assert not module.room_for("flux") and box.stopped == ["beyond-canvas-trellis-resident"]
    assert {"qwen-front", "nemotron-safety"} <= box.up


def test_the_three_places_that_name_the_first_voice_agree(spark):
    module, _, _ = spark()
    loop, load = (SPARK / "qwen-front.sh").read_text(), (SPARK / "qwen-front-load.sh").read_text()
    assert module.FRONT_NAME == "qwen-front"
    assert "NAME=qwen-front\n" in load and "docker wait qwen-front " in loop and "front-paused" in loop
    assert "--port 7160" in load and "qwen-front.sh" in (SPARK / "start.sh").read_text()
    # An exit on its own keeps its log: once it exited with status 0 mid-class and nothing said why.
    assert "docker run -d --name" in load and "--rm" not in load.split("docker run")[1].split("\n")[0]
    assert "docker logs --tail 100 qwen-front" in loop and "qwen-front-last-exit.log" in loop


# After a clip, a job waiting for the GPU goes before the three reloads ---------------------------------


def _keeper(tmp_path, script):
    """Run a line of keeper-common.sh with RESIDENT in a scratch folder; the exit status is its answer."""
    import subprocess
    common = SPARK / "keeper-common.sh"
    return subprocess.run(["sh", "-c", f'RESIDENT="{tmp_path}"; . "{common}"; {script}'], capture_output=True).returncode


def test_a_keeper_leaves_the_lock_alone_while_a_live_job_waits_and_clears_a_dead_ones_note(tmp_path):
    import os
    (tmp_path / "waiting-live").write_text(str(os.getpid()))
    assert _keeper(tmp_path, "job_waiting") == 0
    (tmp_path / "waiting-live").unlink()
    (tmp_path / "waiting-dead").write_text("999999")
    assert _keeper(tmp_path, "job_waiting") == 1 and not (tmp_path / "waiting-dead").exists()


def test_a_job_says_it_is_waiting_for_as_long_as_it_runs_and_no_longer(spark, tmp_path):
    module, _, _ = spark()
    original = module.SparkHandler.__mro__[1]
    seen = []

    def base_generate(self, job, model):
        seen.append(sorted(p.name.split("-")[0] for p in module.RESIDENT.glob("waiting-*")))
        return "made"

    kept, original.generate = original.generate, base_generate
    try:
        handler = object.__new__(module.SparkHandler)
        handler.disconnected = lambda: False
        assert module.SparkHandler.generate(handler, tmp_path, "wan2.2-i2v-a14b") == "made"
    finally:
        original.generate = kept
    assert seen == [["waiting"]] and not list(module.RESIDENT.glob("waiting-*"))


def test_all_three_keepers_step_back_for_a_waiting_job_and_adopt_a_model_already_loaded():
    for keeper, container in (("safety-reader.sh", "nemotron-safety"), ("qwen-front.sh", "qwen-front"),
                              ("trellis-resident.sh", "beyond-canvas-trellis-resident")):
        text = (SPARK / keeper).read_text()
        assert "keeper-common.sh" in text and "job_waiting" in text and f"already_up {container}" in text
        assert "load_under_lock" in text and 'flock "$MEDIA/gpu.lock"' not in text, keeper
    assert "-lt 38" in (SPARK / "trellis-resident-load.sh").read_text(), "its load needs the room a 3D job peaks at"


def test_after_a_draft_is_refused_the_teachers_next_press_is_written_by_step():
    """Operator: two Qwen scene descriptions for a book were refused as not matching the drawing, and
    pressing again only asked Qwen again. With a refusal carried, the next draft goes to Step directly."""
    from studio.providers.frontvoice import without_front
    qwen, step = Voice("qwen"), Voice("step")
    writer = FrontFirst(qwen, step)
    assert writer.chat("first press").model == "qwen"
    with without_front():
        assert writer.chat("second press").model == "step"
    assert qwen.prompts == ["first press"] and step.prompts == ["second press"]
    assert writer.chat("a later, unrefused draft").model == "qwen", "only inside the refusal does Qwen stand aside"
