"""The teacher's second clip choice: 5 s from Wan 3.0 on DashScope (10 s on the first day), beside the Spark's own 5 s clip.

Operator, after timing both on one drawing (docs/measured/wan3-online.md): the
teacher chooses each time and is shown how long each takes. These are the promises that choice rests on.
"""
import json
import os
import shutil
import subprocess
from pathlib import Path

import httpx
import pytest

from studio.core.errors import ModelRefused, ModelUnavailable
from studio.providers import dashscopevideo
from studio.providers.choices import ClipChoices, clip_makers, closed_clip_makers
from studio.providers.dashscopevideo import DashScopeVideoClient
from studio.providers.media import MediaSlot
from studio.core.slots import load_profile
from tests.making.test_animation import CLEAN, Editor
from tests.classroom.test_classroom import ALLOW, CLASS, outputs_of, png, room  # noqa: F401  (fixtures)

IMAGE = "data:image/png;base64,iVBORw0KGgo="
LINK = "https://dashscope-result-bj.oss-cn-beijing.aliyuncs.com/clip.mp4"


def dashscope(monkeypatch, answers, link=LINK):
    """DashScope as a stand-in: a job id, then the given states, then the clip at the link."""
    monkeypatch.setenv("DASHSCOPE_API_KEY", "not-a-real-key")
    monkeypatch.setattr(dashscopevideo, "plain", lambda raw: b"plain:" + raw)
    seen, states = [], iter(answers)

    def answer(request):
        seen.append(request)
        if request.method == "POST":
            return httpx.Response(200, json={"output": {"task_id": "t1", "task_status": "PENDING"}})
        if request.url.path.startswith("/api/v1/tasks/"):
            state = next(states)
            return httpx.Response(200, json={"output": {"task_status": state, "video_url": link}})
        return httpx.Response(200, content=b"the clip")

    client = DashScopeVideoClient("wan3.0-video", {"resolution": "480P", "duration_s": 10},
                                  client=httpx.Client(transport=httpx.MockTransport(answer)), sleep=lambda s: None)
    return client, seen


def test_a_clip_is_asked_for_as_measured_and_the_key_never_reaches_the_clip_link(monkeypatch):
    client, seen = dashscope(monkeypatch, ["RUNNING", "SUCCEEDED"])
    made = client.make({"image": IMAGE, "instruction": "the river flows"})
    assert made.content == b"plain:the clip" and made.provider == "dashscopevideo"
    body = json.loads(seen[0].content)
    assert body["model"] == "wan3.0-video"
    assert body["parameters"] == {"resolution": "480P", "ratio": "adaptive", "duration": 10, "prompt_extend": False}
    assert body["input"] == {"prompt": "the river flows", "media": [{"type": "first_frame", "url": IMAGE}]}
    assert seen[0].headers["X-DashScope-Async"] == "enable"
    assert all(r.headers.get("Authorization") == "Bearer not-a-real-key" for r in seen[:-1])
    assert seen[-1].url.host.endswith(".aliyuncs.com") and "Authorization" not in seen[-1].headers


def test_a_clip_link_outside_alibaba_is_not_fetched(monkeypatch):
    client, seen = dashscope(monkeypatch, ["SUCCEEDED"], link="https://example.com/clip.mp4")
    with pytest.raises(ModelRefused):
        client.make({"image": IMAGE, "instruction": "move"})
    assert all("example.com" not in str(r.url) for r in seen)


def test_a_failed_job_is_a_refusal_and_no_key_is_an_outage(monkeypatch):
    client, _ = dashscope(monkeypatch, ["FAILED"])
    with pytest.raises(ModelRefused):
        client.make({"image": IMAGE, "instruction": "move"})
    monkeypatch.delenv("DASHSCOPE_API_KEY")
    with pytest.raises(ModelUnavailable):
        client.make({"image": IMAGE, "instruction": "move"})


# The Spark has no ffmpeg of its own; the studio finds it in this folder, run from a container.
TOOLS = Path(__file__).resolve().parents[2] / "deploy" / "spark" / "bin"


@pytest.mark.skipif(not (shutil.which("ffmpeg") or shutil.which("docker")), reason="no ffmpeg here")
def test_the_online_clip_arrives_as_one_silent_picture_track_of_at_most_ten_seconds(tmp_path, monkeypatch):
    """Wan 3.0's own file has a sound track and runs 10.03 s; the studio's clip checks take neither."""
    if not shutil.which("ffmpeg"):
        monkeypatch.setenv("PATH", f"{TOOLS}:{os.environ['PATH']}")
    raw = tmp_path / "raw.mp4"
    subprocess.run(["ffmpeg", "-v", "error", "-f", "lavfi", "-i", "testsrc=size=160x120:rate=30:duration=10.2",
                    "-f", "lavfi", "-i", "sine=duration=10.2", "-c:v", "libx264", "-c:a", "aac", "-shortest",
                    str(raw)], check=True, cwd=tmp_path)
    made = tmp_path / "made.mp4"
    made.write_bytes(dashscopevideo.plain(raw.read_bytes()))
    info = json.loads(subprocess.check_output(["ffprobe", "-v", "error", "-show_streams", "-show_format",
                                               "-of", "json", str(made)], cwd=tmp_path))
    assert [s["codec_type"] for s in info["streams"]] == ["video"]
    assert float(info["format"]["duration"]) <= 10


def test_the_choice_goes_to_the_maker_the_teacher_picked():
    spark, online = Editor(), Editor()
    choices = ClipChoices(spark, online)
    choices.make({"image": IMAGE, "clip_maker": "online"})
    choices.make({"image": IMAGE})
    assert len(online.calls) == 1 and len(spark.calls) == 1
    assert "clip_maker" not in online.calls[0], "the maker is the studio's word, not the vendor's"
    with pytest.raises(ModelRefused):
        choices.make({"image": IMAGE, "clip_maker": "somewhere"})


def test_the_class_offers_both_with_the_online_one_at_480p_for_five_seconds():
    online = load_profile("stepfun")["video.online"]
    assert (online.provider, online.model) == ("dashscopevideo", "wan3.0-video")
    assert (online.options["resolution"], online.options["duration_s"]) == ("480P", 5)
    assert clip_makers(MediaSlot(ClipChoices(Editor(), Editor()), "to_video", {}, {})) == ["spark", "online"]
    assert clip_makers(Editor().slot()) == ["spark"] and clip_makers(None) == []


def test_a_class_clip_asked_for_online_is_made_online_and_checked_like_any_other(room, png):
    spark, online = Editor(), Editor()
    classroom = room([ALLOW] * 6 + [CLEAN], editor=MediaSlot(ClipChoices(spark, online), "to_video", {}, {}))
    session_id = classroom.begin(CLASS)
    assert classroom.session_capabilities(session_id)["video_makers"] == ["spark", "online"]
    drawing_id = classroom.add_drawing(session_id, png)
    started = classroom.request(session_id, "painting-to-animation", [drawing_id],
                                {"hint": "the river flows", "media_kind": "video", "clip_maker": "online"})
    classroom.run_request(started["request_id"])
    outputs = outputs_of(list(classroom.follow(started["request_id"])))
    assert outputs["clip_maker"] == "online" and outputs["video_url"].startswith("data:video/mp4;base64,")
    assert len(online.calls) == 1 and spark.calls == []


def test_a_class_with_one_clip_maker_refuses_the_online_choice(room, png):
    editor = Editor()
    classroom = room([], editor=editor.slot())
    session_id = classroom.begin(CLASS)
    drawing_id = classroom.add_drawing(session_id, png)
    with pytest.raises(ValueError, match="clip_maker"):
        classroom.request(session_id, "painting-to-animation", [drawing_id], {"hint": "hop", "clip_maker": "online"})
    assert editor.calls == [] and classroom.requests == {}


SYNC = Path(__file__).resolve().parents[2] / "deploy" / "spark" / "sync.sh"


def test_sync_sends_the_dashscope_key_beside_stepfuns_and_no_other_line():
    """Read the way sync.sh reads it, from a .env holding more than those two keys."""
    script = SYNC.read_text()
    start, end = script.index("key_in_env() {"), script.index("}", script.index("key_in_env() {")) + 1
    env = ("OPENROUTER_API_KEY=never-sent\nexport STEPFUN_API_KEY='step-key'\n"
           "DASHSCOPE_API_KEY = \"dash-key\"\nREPLICATE_API_KEY=never-sent\n")
    probe = (f"ENV_FILE=$1\n{script[start:end]}\n"
             "value=$(key_in_env STEPFUN_API_KEY); online=$(key_in_env DASHSCOPE_API_KEY)\n"
             "{ printf 'STEPFUN_API_KEY=%s\\n' \"$value\"\n"
             "  [ -z \"$online\" ] || printf 'DASHSCOPE_API_KEY=%s\\n' \"$online\"; }\n")
    assert "[ -z \"$online\" ] || printf 'DASHSCOPE_API_KEY=%s\\n' \"$online\"; }" in script
    import tempfile
    with tempfile.NamedTemporaryFile("w", suffix=".env", delete=False) as handle:
        handle.write(env)
    try:
        sent = subprocess.run(["sh", "-c", probe, "probe", handle.name], capture_output=True, text=True,
                              check=True).stdout
    finally:
        os.unlink(handle.name)
    assert sent == "STEPFUN_API_KEY=step-key\nDASHSCOPE_API_KEY=dash-key\n"


def test_the_sparks_clip_is_open_to_teachers_beside_the_online_one_and_a_closed_one_is_refused(monkeypatch):
    """Operator: the Spark's clip was greyed while it meant a silent class; with Step standing in for the chat
    it is a teacher's choice again, and a request naming no maker still goes online. `closed_to_teachers`
    in the profile greys it again, and a closed maker is refused before anything runs."""
    from studio.core.deployments import build_runtime
    monkeypatch.setenv("DASHSCOPE_API_KEY", "not-a-real-key")
    editor = build_runtime("stepfun").editor
    assert set(clip_makers(editor)) == {"spark", "online"} and closed_clip_makers(editor) == []
    spark, online = Editor(), Editor()
    closed = ClipChoices(spark, online, spark_open=False)
    with pytest.raises(ModelRefused):
        closed.make({"image": IMAGE, "clip_maker": "spark"})
    closed.make({"image": IMAGE})
    assert spark.calls == [] and len(online.calls) == 1, "a request that names no maker goes online"


@pytest.mark.parametrize("key", [None, "", "   "])
def test_a_copy_with_no_dashscope_key_makes_its_clips_on_its_own_spark(monkeypatch, key):
    """Operator: a judge's copy has no Alibaba key; with the Spark's clip closed it made none at all."""
    from studio.core.deployments import build_runtime
    if key is None:
        monkeypatch.delenv("DASHSCOPE_API_KEY", raising=False)
    else:
        monkeypatch.setenv("DASHSCOPE_API_KEY", key)
    editor = build_runtime("stepfun").editor
    assert clip_makers(editor) == ["spark"] and closed_clip_makers(editor) == []


def test_a_class_asking_for_the_closed_spark_clip_is_refused_before_anything_runs(room, png):
    spark, online = Editor(), Editor()
    classroom = room([], editor=MediaSlot(ClipChoices(spark, online, spark_open=False), "to_video", {}, {}))
    session_id = classroom.begin(CLASS)
    assert classroom.session_capabilities(session_id)["video_makers_closed"] == ["spark"]
    drawing_id = classroom.add_drawing(session_id, png)
    with pytest.raises(ValueError, match="clip_maker"):
        classroom.request(session_id, "painting-to-animation", [drawing_id], {"hint": "hop", "clip_maker": "spark"})
    assert spark.calls == [] and online.calls == []


def test_a_stopped_online_clip_stops_polling_at_once_and_says_it_was_cancelled(monkeypatch):
    """Code review: it polled on to the end and kept the class's clip slot busy."""
    from studio.core.errors import ModelCancelled
    from studio.providers.gpu_job import cancelled_request
    client, seen = dashscope(monkeypatch, ["RUNNING"] * 50)
    stop = {"now": False}
    original = client._sleep
    client._sleep = lambda s: (stop.update(now=True), original(s))
    token = cancelled_request.set(lambda: stop["now"])
    try:
        with pytest.raises(ModelCancelled):
            client.make({"image": IMAGE, "instruction": "move"})
    finally:
        cancelled_request.reset(token)
    assert len([r for r in seen if r.method == "GET"]) == 0, "no poll after the stop"


def test_a_clip_asked_for_without_a_maker_is_recorded_as_made_by_the_one_that_made_it(room, png):
    """Code review: with the Spark closed it was made online and recorded as "spark"."""
    spark, online = Editor(), Editor()
    classroom = room([ALLOW] * 6 + [CLEAN], editor=MediaSlot(ClipChoices(spark, online, spark_open=False), "to_video", {}, {}))
    session_id = classroom.begin(CLASS)
    drawing_id = classroom.add_drawing(session_id, png)
    started = classroom.request(session_id, "painting-to-animation", [drawing_id], {"hint": "the river flows"})
    classroom.run_request(started["request_id"])
    outputs = outputs_of(list(classroom.follow(started["request_id"])))
    assert outputs["clip_maker"] == "online" and len(online.calls) == 1 and spark.calls == []
