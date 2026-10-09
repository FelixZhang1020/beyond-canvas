"""StepFun First, the studio's only deployment.

This file was tests/test_three_deployments.py until API First and Local First were
archived (operator decision; studio/profiles/archive/README.md). The
tests that exercise machinery StepFun First still uses were kept and pointed at
it; the ones that only compared deployments went with the archive, and are in
commit 35b4204. The last section proves the archive holds.
"""
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock
import json
import re
import httpx
import pytest
from studio.core.deployments import build_runtime, DEPLOYMENTS, model_options
from studio.core.slots import load_profile, SlotConfig
from studio.core import deployment_checks
from studio.providers.choices import MeshChoices
from studio.core.errors import ModelRefused


@pytest.fixture(autouse=True)
def credentials(monkeypatch):
    monkeypatch.setenv('STEPFUN_API_KEY', 'test')
    monkeypatch.setenv('REPLICATE_API_KEY', 'test')
    monkeypatch.delenv('BEYOND_CANVAS_MACHINE', raising=False)


def test_the_showpiece_drives_and_judges_on_stepfun_apart_from_the_class_chat():
    """The temple showpiece is a StepFun Agentic Skills showcase (operator). On vlm.studio it went to
    Qwen with the class chat, and its live runs were driven and judged by Qwen for two days."""
    from studio.server.serve_showpiece import PROFILE, QUICK, SLOT
    from studio.showpiece import catalog
    slot = load_profile(PROFILE)[SLOT]
    assert (slot.provider, slot.model) == ('stepfun', 'step-3.7-flash') and SLOT != 'vlm.studio'
    judge = catalog.TOOLS[('shot-judge', 'judge')]
    assert catalog.quick_args(judge, {}, {**catalog.QUICK, **QUICK})['slot'] == SLOT, 'its pictures are judged there too'


@pytest.mark.parametrize('name', list(DEPLOYMENTS))
def test_roles_and_configured_choices_are_real_runtime_routes(name):
    runtime = build_runtime(name)
    assert runtime.deployed is True
    assert runtime.portrait.extra['scene_format'] == 'glb'
    assert set(runtime.portrait.client.slots) == {'trellis2'}  # Pixal3D archived
    # No echo model for the quick line (operator): it said the child's words back and the
    # reply said them again. The studio's fixed line is spoken instead (studio/conversation/bridge.py).
    assert 'chat.bridge' not in runtime.clients
    # No Step 3.7 Flash in anything a person waits for (operator): the chat, its checks, the
    # drawing's screen, the teacher review and the drafts are Qwen on the Spark, thinking off. Step stands
    # behind each only while Qwen is away for the Spark's clip (tests/conversation/test_front_voice.py).
    for slot in ('vlm.studio', 'vlm.director', 'safety.image', 'vlm.teacher', 'vlm.creation'):
        assert runtime.clients[slot].model == 'qwen3.6-35b-a3b', slot
    assert runtime.clients['vlm.studio'] is not runtime.clients['vlm.director']
    slots = load_profile(name)
    # 3D and the clip on the hosted DGX Spark; bought where StepFun sells one.
    # The clip used to be on Replicate, while the Mac + 4090 (5B only) ran it.
    # The FLUX still picture was retired, so no picture slot is left; Pixal3D, the
    # second 3D choice, was archived with it, so TRELLIS.2 is the one 3D model.
    assert slots['mesh.portrait'].provider == 'localmesh' and 'mesh.alternative' not in slots
    assert 'image.edit' not in slots and 'image.alternative' not in slots
    assert slots['video.animation'].provider == 'localvideo'
    assert slots['tts.studio'].provider == 'stepfun'
    # A child's recorded voice goes to StepFun. Changing this line is a privacy decision.
    assert slots['speech.in'].provider == 'stepfun'


def test_mesh_choice_never_invokes_other_model_on_failure():
    router = MeshChoices([SlotConfig('mesh.portrait','cloudmesh','trellis2',{'task':'to_mesh'}),
                          SlotConfig('mesh.alternative','cloudmesh','pixal',{'task':'to_mesh'})])
    primary = Mock(side_effect=ModelRefused('failed'))
    backup = Mock()
    router.slots['trellis2'].client.make = primary
    router.slots['pixal'].client.make = backup
    with pytest.raises(ModelRefused): router.make({'model_choice':'trellis2'})
    backup.assert_not_called()
    router.make({'model_choice':'pixal'})
    assert primary.call_count == 1 and backup.call_count == 1


@pytest.mark.parametrize('bad_slot,ready', [('mesh.portrait',False),('video.animation',False),('vlm.director',False)])
def test_every_slot_left_is_required(monkeypatch,bad_slot,ready):
    # Pixal3D was StepFun First's one optional slot until it was archived.
    monkeypatch.setattr(deployment_checks,'check_slot',lambda c: {'slot':c.slot,'model':c.model,'status':'unavailable' if c.slot == bad_slot else 'ready'})
    assert deployment_checks.check_profile('stepfun')['ready'] == ready


@pytest.mark.parametrize('state,expected',[('standby','ready'),('missing','unavailable'),('unknown','unknown')])
def test_gpu_catalog_requires_the_selected_model_state(monkeypatch,state,expected):
    client=Mock();client.__enter__=Mock(return_value=client);client.__exit__=Mock(return_value=False)
    # A GPU service that must report its state (Pixal3D's rule; TRELLIS.2 and Wan may list only their
    # names). StepFun First no longer names Pixal3D (archived), so the slot is written here.
    client.get.return_value=httpx.Response(200,json={'data':[{'id':'pixal','status':state}]},request=httpx.Request('GET','http://localhost'))
    monkeypatch.setattr(httpx,'Client',lambda **kw:client)
    slot=SlotConfig('mesh.alternative','localmesh','pixal',{'task':'to_mesh','base_url':'http://127.0.0.1:7250'})
    result=deployment_checks.check_slot(slot)
    assert result['status']==expected


def response_client(monkeypatch, body):
    client=Mock(); client.__enter__=Mock(return_value=client); client.__exit__=Mock(return_value=False)
    client.get.return_value=httpx.Response(200,json=body,request=httpx.Request('GET','http://localhost'))
    monkeypatch.setattr(httpx,'Client',lambda **kw:client)
    return client


@pytest.mark.parametrize('body,status', [
    ({'data':[{'id':'trellis2','state':'standby','ready':True}]}, 'ready'),
    ({'data':[{'id':'trellis2','state':'standby','ready':False}]}, 'unavailable'),
    ({'data':['bad',{'id':'other','status':'ready'}]}, 'unknown'),
    ([], 'unavailable'),
    ({'data':None}, 'unavailable'),
])
def test_real_gpu_catalog_contract_and_malformed_payload(monkeypatch, body, status):
    response_client(monkeypatch, body)
    assert deployment_checks.check_slot(load_profile('stepfun')['mesh.portrait'])['status'] == status


@pytest.mark.parametrize('slot,model', [('video.animation','wan2.2-i2v-a14b'), ('mesh.portrait','trellis2')])
def test_gpu_health_checks_model_identity(monkeypatch, slot, model):
    """The clip is a GPU-machine slot: the Spark holds the 14B model."""
    response_client(monkeypatch, {'data':[{'id':'wrong-worker'}]})
    assert deployment_checks.check_slot(load_profile('stepfun')[slot])['status'] != 'ready'
    response_client(monkeypatch, {'data':[{'id':model}]})
    assert deployment_checks.check_slot(load_profile('stepfun')[slot])['status'] == 'ready'


def test_missing_required_config_is_not_green(monkeypatch):
    monkeypatch.setattr(deployment_checks,'load_profile',lambda name: {})
    report = deployment_checks.check_profile('stepfun')
    assert not report['ready']
    assert any(c['slot'] == 'vlm.director' and c['status'] == 'unavailable' for c in report['components'])


def test_model_options_use_only_the_report_for_their_own_deployment():
    """The half of this test that pulled a Replicate key went with API First: no
    remaining 3D choice needs a key, because all of them are the GPU machine's. The picture
    choice went with the still picture, and asking for it is refused."""
    report = {'target':'stepfun', 'components':[{'slot':'mesh.portrait.trellis2','model':'trellis2','status':'ready','reason':'catalog'}]}
    assert model_options('stepfun','mesh',report)[0]['status'] == 'ready'
    assert model_options('stepfun','mesh',dict(report, target='elsewhere'))[0]['status'] == 'unknown'
    with pytest.raises(ValueError):
        model_options('stepfun','image',report)


def test_completed_checks_are_cached_with_monotonic_time(monkeypatch):
    from threading import RLock
    report = {'target':'stepfun','components':[], 'ready':True}
    monkeypatch.setattr(deployment_checks,'check_profile',lambda name:report)
    room=SimpleNamespace(lock=RLock(), ears=None)
    assert deployment_checks.check_deployment(room,'stepfun') is report
    checked, cached = room._component_checks['stepfun']
    assert checked > 0 and cached is report
    # The profile's report is passed through untouched. check_deployment used to
    # append a speech.in of its own, built from the running
    # classroom's ears rather than from the deployment being checked — which the
    # last two assertions here described. That matched only by accident, and once
    # hearing could be bought it probed StepFun's HTTPS endpoint as a local
    # whisper and refused every switch. speech.in is a profile slot now.
    assert report['ready']
    assert report['components'] == []


def test_mesh_choice_preserves_mapping_and_has_immutable_lazy_config():
    config=SlotConfig('mesh.portrait','cloudmesh','trellis2',{'task':'to_mesh','fields':{'image':'image_url'},'extra':{'seed':42}})
    router=MeshChoices([config])
    config.options['extra']['seed']=99
    make=Mock()
    router.slots['trellis2'].client.make=make
    router.make({'image':'fixture','model_choice':'trellis2'})
    assert make.call_args.args[0]['image_url']=='fixture'
    assert router.slots['trellis2'].client.config.options['extra']['seed']==42
    with pytest.raises(ModelRefused): router.make({'model_choice':[]})


# The 4090 voice client below served Local First only. No deployment builds it
# since the archive; the module and its tests stay so it can come back whole.

def wav_bytes(frames=10):
    import io, wave
    data=io.BytesIO()
    with wave.open(data,'wb') as wav:
        wav.setnchannels(1); wav.setsampwidth(2); wav.setframerate(24000)
        wav.writeframes(b'\x00\x01'*frames)
    return data.getvalue()


@pytest.mark.parametrize('payload,valid', [(wav_bytes(),True),(wav_bytes()[:-2],False),(wav_bytes(0),False),(b'bad',False)])
def test_remote_voice_rejects_empty_and_truncated_wav_before_playback(payload,valid):
    from studio.providers.remotevoice import RemoteClassroomVoice
    from studio.providers.stepfun_voice import VoiceServiceError
    voice=RemoteClassroomVoice({'base_url':'http://127.0.0.1:7280'},httpx.Client(transport=httpx.MockTransport(lambda r:httpx.Response(200,content=payload))))
    if valid:
        assert b''.join(voice.stream('synthetic text')) == b'\x00\x01'*10
    else:
        with pytest.raises(VoiceServiceError): next(voice.stream('synthetic text'))


def test_remote_voice_cancelled_before_request_does_not_submit():
    from studio.providers.remotevoice import RemoteClassroomVoice
    handler=Mock()
    voice=RemoteClassroomVoice({'base_url':'http://127.0.0.1:7280'},httpx.Client(transport=httpx.MockTransport(handler)))
    assert list(voice.stream('synthetic text',cancelled=lambda:True)) == []
    handler.assert_not_called()


def test_remote_voice_retries_past_a_busy_worker_queue(monkeypatch):
    # media_server.py answers 503 worker queue full while another line is still
    # generating; a second line queued right behind it should not just fail.
    import studio.providers.remotevoice as remotevoice
    monkeypatch.setattr(remotevoice.time, 'sleep', lambda seconds: None)
    from studio.providers.remotevoice import RemoteClassroomVoice
    calls = []
    def handle(request):
        calls.append(request)
        if len(calls) < 3:
            return httpx.Response(503, json={'error': 'worker queue full'})
        return httpx.Response(200, content=wav_bytes())
    voice = RemoteClassroomVoice({'base_url': 'http://127.0.0.1:7280'}, httpx.Client(transport=httpx.MockTransport(handle)))
    assert b''.join(voice.stream('synthetic text')) == b'\x00\x01' * 10
    assert len(calls) == 3


def test_remote_voice_gives_up_after_repeated_busy_and_reports_the_real_reason(monkeypatch):
    import studio.providers.remotevoice as remotevoice
    monkeypatch.setattr(remotevoice.time, 'sleep', lambda seconds: None)
    from studio.providers.remotevoice import RemoteClassroomVoice
    from studio.providers.stepfun_voice import VoiceServiceError
    handler = Mock(return_value=httpx.Response(503, json={'error': 'worker queue full'}))
    voice = RemoteClassroomVoice({'base_url': 'http://127.0.0.1:7280'}, httpx.Client(transport=httpx.MockTransport(handler)))
    with pytest.raises(VoiceServiceError, match='worker queue full'):
        next(voice.stream('synthetic text'))
    assert handler.call_count == remotevoice.BUSY_RETRIES


def test_remote_voice_does_not_retry_a_non_busy_failure(monkeypatch):
    import studio.providers.remotevoice as remotevoice
    monkeypatch.setattr(remotevoice.time, 'sleep', lambda seconds: None)
    from studio.providers.remotevoice import RemoteClassroomVoice
    from studio.providers.stepfun_voice import VoiceServiceError
    handler = Mock(return_value=httpx.Response(422, json={'error': 'invalid bounded media request'}))
    voice = RemoteClassroomVoice({'base_url': 'http://127.0.0.1:7280'}, httpx.Client(transport=httpx.MockTransport(handler)))
    with pytest.raises(VoiceServiceError, match='invalid bounded media request'):
        next(voice.stream('synthetic text'))
    assert handler.call_count == 1


def test_image_string_timeout_and_blank_instruction():
    from studio.providers.localimage import LocalImageClient
    calls=[]
    def handle(request):
        calls.append(request)
        return httpx.Response(200,content=b'image',headers={'content-type':'image/png'})
    client=LocalImageClient('flux',{'base_url':'http://127.0.0.1:7270','timeout_s':'300'},httpx.Client(transport=httpx.MockTransport(handle)))
    client.make({'image':'data:image/png;base64,AA==','instruction':'move'})
    assert len(calls)==1
    with pytest.raises(ModelRefused): client.make({'image':'data:image/png;base64,AA==','instruction':'   '})
    assert len(calls)==1


@pytest.mark.parametrize('body,expected',[({'owner':'wan-video','name':'wan-2.2-i2v-a14b'},'ready'),
    ({'owner':'other','name':'wan-2.2-i2v-a14b'},'unknown'),
    ({'name':'wan-2.2-i2v-a14b'},'unknown')])
def test_official_directory_identity_is_checked_without_version(monkeypatch,body,expected):
    """Replicate's official models have no version to pin, so the owner and name are the identity.
    StepFun First stopped buying its clip there; the check is kept, and read here
    through the archived Mac + 4090 profile, which is the last one that used it."""
    client=response_client(monkeypatch,body)
    archived = load_profile('studio/profiles/archive/stepfun-mac-4090.yaml')
    assert deployment_checks.check_slot(archived['video.animation'])['status']==expected
    assert client.get.call_args.args[0]=='https://api.replicate.com/v1/models/wan-video/wan-2.2-i2v-a14b'


def test_official_profiles_have_no_fake_version_and_wan_waits_long_enough():
    for c in load_profile('stepfun').values():
        if c.provider == 'replicate' and c.model.startswith(('black-forest-labs/','wan-video/')):
            assert c.options['official'] is True
            assert 'version' not in c.options
    # 900, not 600, and a floor rather than an equality: one clip measured 631 s
    # wall and cleared the old ceiling by under thirty seconds.
    assert load_profile('stepfun')['video.animation'].options['timeout_s'] >= 900


def test_speech_cache_never_reuses_another_provider_with_the_same_voice_id():
    from studio.voice.speech import SpeechSession
    class Voice:
        voice='gentle-female'
        model='shared-model-label'
        sample_rate=24000
        base_url=''
        def __init__(self, pcm): self.pcm,self.calls=pcm,0
        def validate_voice(self, voice): return voice
        def stream(self,text,voice_id,cancelled):
            self.calls+=1
            yield self.pcm
    speech=SpeechSession()
    first,second=Voice(b'\x01\x00'),Voice(b'\x02\x00')
    a=list(speech.stream(first,'same text','gentle-female'))
    cached=list(speech.stream(first,'same text','gentle-female'))
    b=list(speech.stream(second,'same text','gentle-female'))
    assert first.calls==second.calls==1
    assert cached[0]['cached'] is True and b[0]['cached'] is False
    assert next(e['data'] for e in a if e['type']=='pcm') != next(e['data'] for e in b if e['type']=='pcm')


@pytest.mark.parametrize('age,expected',[(0,'unavailable'),(61,'unknown')])
def test_session_fresh_report_blocks_a_failed_model_and_stale_report_allows_unknown(monkeypatch,tmp_path,age,expected):
    import time
    from studio.classroom.classroom import Classroom
    from tests.classroom.test_classroom import DRAWING
    room=Classroom(tmp_path/'ledger',clients={'vlm.studio':object(),'vlm.director':object()})
    sid=room.begin({'language':'en','entrance':'sketch'})
    room.sessions[sid].runtime=build_runtime('stepfun')
    did=room.add_drawing(sid,Path(DRAWING).read_bytes())
    room._component_checks={'stepfun':(time.monotonic()-age,{'target':'stepfun','components':[
        {'slot':'mesh.portrait.trellis2','model':'trellis2','status':'unavailable','reason':'connection'}]})}
    try:
        cap=room.session_capabilities(sid)
        assert [m['id'] for m in cap['mesh_models']] == ['trellis2']  # Pixal3D archived
        assert cap['mesh_models'][0]['status']==expected
        assert 'image_edit' not in cap and 'image_models' not in cap  # retired
        if expected=='unavailable':
            with pytest.raises(ValueError,match='unavailable'):
                room.request(sid,'sketch-to-3d',[did],{'model_choice':'trellis2'})
        else:
            assert room.request(sid,'sketch-to-3d',[did],{'model_choice':'trellis2'})['request_id']
    finally: room.close()


def test_a_request_for_the_archived_pixal3d_is_refused_before_anything_runs(tmp_path):
    from studio.classroom.classroom import Classroom
    from tests.classroom.test_classroom import DRAWING
    room=Classroom(tmp_path/'ledger',clients={'vlm.studio':object(),'vlm.director':object()})
    try:
        sid=room.begin({'language':'en','entrance':'sketch'})
        did=room.add_drawing(sid,Path(DRAWING).read_bytes())
        with pytest.raises(ValueError,match='Pixal3D was archived'):
            room.request(sid,'sketch-to-3d',[did],{'model_choice':'pixal'})
        assert room.requests == {}
    finally: room.close()


def test_teacher_reports_are_a_configured_role_in_every_deployment():
    """The teacher report must be reachable through the profile, not around it.

    It used to read a `vlm.teacher` client that no profile defined, so the lookup
    always missed and every report fell through to a hard-coded profile name,
    ignoring whichever deployment the teacher had selected.

    The slot thinks at medium, not high. At high, one live call
    spent its whole 16000-token completion budget on hidden reasoning and
    returned nothing; the report is three calls long and cannot afford that.
    """
    for name in DEPLOYMENTS:
        runtime = build_runtime(name)
        assert 'vlm.teacher' in runtime.clients, name
        assert runtime.clients['vlm.teacher'].options['chat_template_kwargs'] == {'enable_thinking': False}
        assert runtime.clients['vlm.teacher'] is not runtime.clients['vlm.creation']
    checked = {c['slot'] for c in deployment_checks.check_profile('stepfun')['components']}
    assert 'vlm.teacher' in checked


@pytest.mark.parametrize('name', list(DEPLOYMENTS))
def test_every_bought_reading_slot_declares_what_it_costs(name):
    """A ledger line's `cost` is computed from the profile, not returned by StepFun.

    None of the three shipping profiles used to name a price, so every
    class recorded 0.0 for calls that really did spend money — and 0.0 there reads
    as free rather than as "nobody said". The pair is StepFun's own list price,
    sourced in cloud.yaml where it was already written down.
    """
    profile = load_profile(name)
    bought = {slot: config for slot, config in profile.items()
              if config.provider == 'stepfun' and config.model.startswith('step-')}
    assert bought, f"{name} is expected to buy its reading from StepFun"
    for slot, config in bought.items():
        assert float(config.options.get('price_usd_per_m_in', 0)) > 0, f"{name}:{slot} in"
        assert float(config.options.get('price_usd_per_m_out', 0)) > 0, f"{name}:{slot} out"


def _sketch_room_on(profile, tmp_path):
    """A class on a real deployment runtime, with one drawing, and no cache seeded."""
    from studio.classroom.classroom import Classroom
    from tests.classroom.test_classroom import DRAWING
    room = Classroom(tmp_path / 'ledger', clients={'vlm.studio': object(), 'vlm.director': object()})
    sid = room.begin({'language': 'en', 'entrance': 'sketch'})
    room.sessions[sid].runtime = build_runtime(profile)
    room.add_drawing(sid, Path(DRAWING).read_bytes())
    return room, sid


def test_a_stale_pass_still_reads_ready_and_says_it_was_checked_earlier(tmp_path):
    """The expiry above exists so a stale REFUSAL stops blocking a model. It was
    also turning a stale PASS into "unverified", which a teacher read as a warning
    on the 3D picker every time more than a minute had passed since the system
    screen was last opened. Seen live on a working TRELLIS route.
    """
    import time
    room, sid = _sketch_room_on('stepfun', tmp_path)
    room._component_checks = {'stepfun': (time.monotonic() - 61, {'target': 'stepfun', 'components': [
        {'slot': 'mesh.portrait.trellis2', 'model': 'trellis2', 'status': 'ready', 'reason': 'standby'}]})}
    trellis = room.session_capabilities(sid)['mesh_models'][0]
    assert trellis['status'] == 'ready'
    assert trellis['reason'] == 'stale'


def test_the_first_look_after_a_restart_runs_the_check_itself(monkeypatch, tmp_path):
    """After a restart nothing has been checked, and nothing ran a check unless the
    teacher opened the system screen — so every fresh class opened on "unverified".
    The first class to ask now pays for one check; the ones after it read the cache.
    """
    import time
    room, sid = _sketch_room_on('stepfun', tmp_path)
    ran = []

    def fake_check(classroom, name):
        ran.append(name)
        report = {'target': name, 'components': [
            {'slot': 'mesh.portrait.trellis2', 'model': 'trellis2', 'status': 'ready', 'reason': 'standby'}]}
        classroom._component_checks = {name: (time.monotonic(), report)}
        return report
    monkeypatch.setattr(deployment_checks, 'check_deployment', fake_check)
    first = room.session_capabilities(sid)['mesh_models'][0]
    second = room.session_capabilities(sid)['mesh_models'][0]
    assert first['status'] == second['status'] == 'ready'
    assert ran == ['stepfun'], "one check for the first look, none for the second"



# --- StepFun First runs on the subscription -------------------------------

PLAN_URL = 'https://api.stepfun.com/step_plan/v1'


def test_stepfun_first_buys_every_step_model_through_the_subscription():
    """Operator decision: this deployment's whole StepFun bill is the plan.

    Reading, judging, safety, speaking and hearing — ten slots since the 3D figure's
    check was split from its writer (vlm.figure.look) — and the address is
    what decides which account pays. Both endpoints take the same key and answer the same
    way, so a slot left on the old one would work perfectly and quietly spend the balance.
    Hearing is the one exception, below: the plan has no transcription.
    """
    bought = {slot: config for slot, config in load_profile('stepfun').items()
              if config.provider == 'stepfun' and slot != 'speech.in'}
    # chat.bridge joined and later left; five went to Qwen on the Spark;
    # vlm.showpiece joined, the temple showpiece's own StepFun slot; vlm.standin joined, the chat's
    # stand-in while Qwen is away for the Spark's clip (operator).
    assert len(bought) == 6, sorted(bought)
    for slot, config in bought.items():
        assert config.options['base_url'] == PLAN_URL, slot
        assert config.options['included_in_plan'] is True, slot


def test_hearing_is_bought_per_recording_because_the_plan_has_none():
    """step_plan/v1 answers 404 to a transcription, so on the plan every recording
    failed until the operator chose pay-per-use.
    The last line also holds what an older test here did: hearing uses the address
    the profile names, which it used to drop silently."""
    from studio.voice.transcribe import hearing_for

    config = load_profile('stepfun')['speech.in']
    assert config.options['base_url'] == 'https://api.stepfun.com/v1'
    assert config.options['included_in_plan'] is False
    assert hearing_for('stepfun').base_url == 'https://api.stepfun.com/v1'


def test_nothing_but_stepfun_is_handed_a_stepfun_address():
    """The GPU-machine workers and Replicate live in this profile too, and a StepFun
    address given to one of them is a nonsense it might not refuse."""
    for slot, config in load_profile('stepfun').items():
        if config.provider != 'stepfun':
            assert PLAN_URL not in str(config.options.get('base_url', '')), slot
            assert 'included_in_plan' not in config.options, slot


def test_the_classroom_voice_speaks_through_the_subscription():
    """Speech is bought, so the address is a billing decision like any other.

    The voice used to be built with no configuration at all and always
    used the module default, which was invisible while there was only one address.
    """
    assert build_runtime('stepfun').voice.base_url == PLAN_URL


# --- API First and Local First are archived --------------------------------

ARCHIVE = Path('studio/profiles/archive')


def test_stepfun_first_is_the_only_deployment_offered():
    from studio.core.deployments import describe
    room = SimpleNamespace(deployment='stepfun', deployment_path=None)
    assert DEPLOYMENTS == {'stepfun': 'StepFun First'}
    assert [option['id'] for option in describe(room)['options']] == ['stepfun']


@pytest.mark.parametrize('name,label', [('api', 'API First'), ('local-first', 'Local First')])
def test_asking_for_an_archived_deployment_says_it_was_archived(tmp_path, name, label):
    from studio.core.deployments import save_selection
    with pytest.raises(ValueError, match=f'{label} was archived;'):
        build_runtime(name)
    with pytest.raises(ValueError, match='StepFun First is the only deployment'):
        save_selection(tmp_path / 'deployment.json', name)
    assert not (tmp_path / 'deployment.json').exists()


@pytest.mark.parametrize('saved', ['api', 'local-first'])
def test_a_machine_that_last_chose_an_archived_deployment_opens_on_stepfun_first(tmp_path, saved):
    from studio.core.deployments import restore_selection
    state = tmp_path / 'deployment.json'
    state.write_text(json.dumps({'deployment': saved}))
    switched = []
    room = SimpleNamespace(switch_deployment=switched.append)
    restore_selection(room, state)
    assert switched == ['stepfun']


def test_the_archived_profiles_are_kept_for_reference_and_nothing_loads_them():
    for name in ('api', 'local-first'):
        assert (ARCHIVE / f'{name}.yaml').is_file(), name
        assert not Path(f'studio/profiles/{name}.yaml').exists(), name
        with pytest.raises(FileNotFoundError):
            load_profile(name)
    assert 'StepFun First is the studio\'s only deployment' in (ARCHIVE / 'README.md').read_text()


def test_no_code_still_reaches_for_the_archived_profiles():
    """The showpiece, the photo judge and the teacher-review fallback used api.yaml
    until the archive; a default left pointing at it fails only when that path runs."""
    pointer = re.compile(r"""load_profile\(\s*["'](api|local-first)["']|default=["'](api|local-first)["']"""
                         r"""|PROFILE, SLOT = ["'](api|local-first)["']""")
    found = [f'{path}:{number}' for root in ('studio', 'evalkit', 'skills') for path in Path(root).rglob('*.py')
             for number, line in enumerate(path.read_text(encoding='utf-8').splitlines(), 1) if pointer.search(line)]
    assert found == []


# --- the Mac + 4090 way of running it is archived too -----------------------
#
# One deployment name used to mean two boxes, switched by
# BEYOND_CANVAS_MACHINE: from the Mac, pictures and 3D went to the 4090 over a
# tunnel and the clip was bought from Replicate; on the Spark, everything was made
# there. The operator then moved the whole project to the Spark.

def test_stepfun_first_makes_its_video_on_the_spark_whatever_the_machine_says(monkeypatch):
    monkeypatch.setenv('BEYOND_CANVAS_MACHINE', 'anything')  # read by nothing any more
    video = load_profile('stepfun')['video.animation']
    assert (video.provider, video.model) == ('localvideo', 'wan2.2-i2v-a14b')
    assert video.options['base_url'] == 'http://127.0.0.1:7260'


def test_the_mac_and_4090_variant_is_kept_only_in_the_archive():
    import yaml
    assert not Path('studio/profiles/stepfun-spark.yaml').exists()
    archived = yaml.safe_load((ARCHIVE / 'stepfun-mac-4090.yaml').read_text(encoding='utf-8'))
    assert archived['slots']['video.animation']['provider'] == 'replicate'
    assert 'stepfun-mac-4090.yaml' in (ARCHIVE / 'README.md').read_text(encoding='utf-8')
