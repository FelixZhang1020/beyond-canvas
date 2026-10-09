import json
from pathlib import Path

import httpx
import pytest

from studio.classroom.classroom import Classroom
from studio.core.deployments import Runtime, restore_selection
from studio.core.errors import ModelUnavailable
from studio.providers.stepfun import StepFunMediaClient
from studio.providers.stepfun_voice import StepFunClassroomVoice
from studio.core.slots import load_profile


@pytest.fixture
def room(tmp_path):
    obj = object()
    room = Classroom(tmp_path / 'ledger', clients={'vlm.studio': obj, 'vlm.director': obj})
    yield room
    room.close()


def target():
    # Not marked deployed: a deployed runtime's first class runs the real component checks.
    return Runtime('stepfun', 'stepfun', {'vlm.studio': object(), 'vlm.director': object()},
                   object(), object(), object())


def test_switch_pins_even_drawings_not_yet_opened_and_roundtrips(room, monkeypatch, tmp_path):
    import studio.core.deployments as dep
    new = target()
    monkeypatch.setattr(dep, 'build_stepfun', lambda: new)
    before = room._runtime()
    first = room.begin({'language': 'zh', 'entrance': 'colour'})
    room.deployment_path = tmp_path / 'selection.json'
    room.switch_deployment('stepfun')
    second = room.begin({'language': 'zh', 'entrance': 'colour'})
    assert room.sessions[first].runtime.clients is before.clients
    assert room.sessions[first].runtime.editor is None
    assert room.session_capabilities(first)['video'] is False
    assert room.session_capabilities(second)['video'] is True
    assert json.loads(room.deployment_path.read_text())['deployment'] == 'stepfun'
    room.switch_deployment('current')
    assert room.clients is before.clients
    assert room.sessions[second].runtime.clients is new.clients
    assert room.session_capabilities(first)['deployment'] == 'current'


def test_failure_and_arbitrary_profile_paths_do_not_change_runtime(room, monkeypatch, tmp_path):
    import studio.core.deployments as dep
    def fail():
        raise ModelUnavailable('Unavailable')
    monkeypatch.setattr(dep, 'build_stepfun', fail)
    original = room.clients
    with pytest.raises(ModelUnavailable):
        room.switch_deployment('stepfun')
    with pytest.raises(ValueError):
        room.switch_deployment('../../private')
    assert room.clients is original and room.deployment == 'current'
    monkeypatch.setattr(dep, 'build_stepfun', target)
    room.deployment_path = tmp_path  # Directory cannot replace a state file.
    with pytest.raises(OSError):
        room.switch_deployment('stepfun')
    assert room.clients is original and room.deployment == 'current'


def test_restart_and_explicit_current_override(room, tmp_path, monkeypatch):
    import studio.core.deployments as dep
    monkeypatch.setattr(dep, 'build_stepfun', target)
    state = tmp_path / 'selection.json'
    state.write_text('{"deployment":"stepfun"}')
    restore_selection(room, state)
    assert room.deployment == 'stepfun'
    room.switch_deployment('current')
    state.write_text('{"deployment":"stepfun"}')
    restore_selection(room, state, 'current')
    assert json.loads(state.read_text())['deployment'] == 'current'


def test_stepfun_profile_keeps_review_request_config_distinct_and_has_no_picture_slot():
    slots = load_profile('stepfun')
    # No Step 3.7 Flash in anything a person waits for (operator): Qwen on the Spark,
    # thinking off, capped to what its 16384-token window can answer.
    for slot in ('vlm.studio', 'vlm.director', 'safety.image', 'vlm.teacher', 'vlm.creation'):
        assert (slots[slot].provider, slots[slot].model) == ('llamacpp', 'qwen3.6-35b-a3b'), slot
        assert slots[slot].options['chat_template_kwargs'] == {'enable_thinking': False}, slot
        assert slots[slot].options['most_tokens'] <= 4000, slot
    assert slots['vlm.teacher'] is not slots['vlm.creation']
    # The FLUX still picture was retired; the clip is what painting-to-animation makes.
    assert 'image.edit' not in slots
    assert slots['video.animation'].options['task'] == 'to_video'


def test_stepfun_image_models_are_disabled_without_network():
    client=StepFunMediaClient('step-image-edit-2',{'endpoint':'images/edits'},'test',httpx.Client(transport=httpx.MockTransport(lambda r:pytest.fail('must not submit'))))
    with pytest.raises(ModelUnavailable, match='disabled'): client.make({})


def test_step_voice_returns_mp3_and_cancelled_call_never_synthesizes():
    # MP3, not raw sound (tests/voice/test_speech_by_sentence.py says why).
    sentence=b'ID3'+b'\0'*5000
    calls=[]
    def handler(request):
        calls.append(json.loads(request.content))
        return httpx.Response(200,content=sentence,headers={'content-type':'audio/mpeg'})
    voice=StepFunClassroomVoice('test',httpx.Client(transport=httpx.MockTransport(handler)))
    assert list(voice.stream('你好','gentle-female')) == [sentence]
    assert calls[0]['voice']=='wenrounvsheng'
    assert list(voice.stream('你好','gentle-female',lambda:True))==[]
    assert len(calls)==1


def test_new_stepfun_editor_can_submit_a_clip_without_prior_switch_back(room, monkeypatch):
    import studio.core.deployments as dep
    monkeypatch.setattr(dep, 'build_stepfun', target)
    room.switch_deployment('stepfun')
    sid=room.begin({'language':'zh','entrance':'colour'})
    did=room.add_drawing(sid,Path('skills/art-feedback/evals/files/dog-sun.png').read_bytes())
    request=room.request(sid,'painting-to-animation',[did],{'hint':'抬头'})
    assert room.requests[request['request_id']].options['hint']=='抬头'
    with pytest.raises(ValueError):
        room.request(sid,'painting-to-animation',[did],{'media_kind':'image','hint':'抬头'})


def test_the_startup_banner_names_the_deployment_that_was_actually_restored(room, tmp_path, monkeypatch):
    """The console line is the only thing an operator reads before opening the page.

    It printed `--profile`, whose default is the constant "stepfun", so it said
    StepFun First however the studio had really been started. Seen live:
    started with `--deployment local-first`, the banner said
    profile=stepfun while /api/health said local-first. It prints six lines after
    restore_selection, so the right answer was already sitting on the classroom.
    """
    import studio.core.deployments as dep
    monkeypatch.setattr(dep, 'build_stepfun', target)
    state = tmp_path / 'selection.json'
    restore_selection(room, state, 'stepfun')
    assert room.profile == 'stepfun', "restore must leave the truth on the classroom"

    import inspect, studio.serve
    banner = [line for line in inspect.getsource(studio.serve).splitlines()
              if 'Beyond Canvas studio on' in line]
    assert banner, "the banner line moved; this test guards what it reports"
    assert 'arguments.profile' not in banner[0], (
        "the banner must report the restored deployment, not the --profile flag")


# --- which box the status board names ---------------------------------------
#
# Every self-hosted model used to be labelled "4090", so the
# Spark's own FLUX showed up on the Spark's page as running on the 4090 — the
# one label a demonstration recorded there would get wrong. Since the Mac + 4090
# variant was archived, the Spark is the only box to name.

def test_a_self_hosted_model_is_labelled_the_spark(monkeypatch):
    from studio.core.deployments import component_identity
    from studio.core.slots import load_profile
    monkeypatch.delenv("BEYOND_CANVAS_MACHINE", raising=False)
    slots = load_profile("stepfun")
    for slot in ("video.animation", "mesh.portrait"):
        identity = component_identity(slots[slot])
        assert (identity["provider"], identity["location"]) == ("DGX Spark", "DGX Spark"), slot
    assert component_identity(slots["video.animation"])["source"].endswith("Wan2.2-I2V-A14B-Diffusers")
    assert component_identity(slots["tts.studio"])["provider"] == "StepFun"
