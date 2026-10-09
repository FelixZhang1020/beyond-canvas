"""The studio's one deployment, StepFun First; existing editing sessions retain their snapshot.

API First and Local First were archived by operator decision. Their
profiles are in studio/profiles/archive/ for reference; asking for either by name is
refused with a sentence that says so, and a saved choice of either opens as StepFun First.
"""
from dataclasses import dataclass
from pathlib import Path
import json
import os
import tempfile

from studio.providers import build_client, build_media_slot, build_safety_reader, is_disabled_stepfun_image_model, key_for
from studio.core.slots import load_profile

# The box a self-hosted slot runs on, as the status board names it. It used to say "4090",
# then chose by BEYOND_CANVAS_MACHINE for a short while; since
# the Mac + 4090 variant was archived, the Spark is the only box.
LOCAL_BOX = 'DGX Spark'


@dataclass(frozen=True)
class Runtime:
    name: str
    profile: str
    clients: dict
    editor: object
    portrait: object
    voice: object
    # Built by build_runtime from a deployment's profile, not put together from a classroom's own
    # clients: only then are the component checks and 3D choices real. A non-empty
    # set of image editors stood in for this until the still picture was retired.
    deployed: bool = False


# English, by operator decision: these name an engineering
# arrangement rather than anything a child or parent reads. There is one now.
DEPLOYMENTS = {'stepfun': 'StepFun First'}
ARCHIVED = {'api': 'API First', 'local-first': 'Local First'}


def unknown(name):
    """The refusal for a deployment that is not offered, naming the archive when it is there."""
    if name in ARCHIVED:
        return ValueError(f'{ARCHIVED[name]} was archived; StepFun First is the only deployment '
                          '(studio/profiles/archive/README.md)')
    return ValueError('Unknown deployment')
ROLE_SLOTS = ('vlm.studio', 'vlm.director', 'safety.image', 'vlm.sketch', 'vlm.creation', 'vlm.teacher')
# Optional. NVIDIA's safety model, asked inside studio-safety before the four verdicts. StepFun First
# names it (operator's go); a profile without the slot runs exactly as before.
SAFETY_READER_SLOT = 'safety.reader'
# Optional. FLUX.2 Klein on the Spark, redrawing a storybook's pages in a picture-book style. A media slot kept
# in `clients` beside the chat clients, so a class's snapshot carries it with nothing else to thread through.
BOOK_SLOT = 'image.book'
# Optional. VoxCPM2 on the Spark, reading a storybook page in the voice of the first answer a child said out
# loud about its drawing (studio/voice/child_voice.py, operator); without it the studio's voice reads.
CHILD_VOICE_SLOT = 'tts.child'


def build_runtime(name):
    if name not in DEPLOYMENTS:
        raise unknown(name)
    from studio.providers.stepfun_voice import StepFunClassroomVoice
    from studio.providers.choices import lazy_slot, MeshChoices
    from studio.providers.media import MediaSlot
    slots = load_profile(name)
    # No image.edit: the FLUX still picture was retired (operator; Wan makes the
    # real animation), so a missing picture model can never keep a class from opening.
    # No mesh.alternative either: Pixal3D was archived too, so TRELLIS.2 is the one 3D model.
    required = ROLE_SLOTS + ('video.animation', 'mesh.portrait', 'tts.studio')
    if any(n not in slots for n in required):
        raise ValueError('Incomplete deployment profile')
    clients = {n: build_client(slots[n]) for n in ROLE_SLOTS}
    if 'vlm.figure' in slots:   # the 3D figure's own writer, with more time than a draft; else vlm.creation
        clients['vlm.figure'] = build_client(slots['vlm.figure'])
    if 'chat.bridge' in slots:   # the quick line while the studio looks; without it, the fixed line
        clients['chat.bridge'] = build_client(slots['chat.bridge'])
    if 'vlm.figure.look' in slots:   # the toy's check, judged apart from the writing; else the writer again
        clients['vlm.figure.look'] = build_client(slots['vlm.figure.look'])
    if BOOK_SLOT in slots:   # the storybook's picture-book pages; without it, the originals only
        clients[BOOK_SLOT] = build_media_slot(slots[BOOK_SLOT])
    if CHILD_VOICE_SLOT in slots:
        from studio.providers.remotevoice import RemoteChildVoice
        clients[CHILD_VOICE_SLOT] = RemoteChildVoice(slots[CHILD_VOICE_SLOT].options)
    if 'vlm.standin' in slots:   # Step 3.7 Flash takes the class over while Qwen is away for the Spark's clip (operator)
        from studio.providers.frontvoice import StandIn
        standin = build_client(slots['vlm.standin'])
        for waited_on in ('vlm.studio', 'vlm.director', 'safety.image', 'vlm.teacher', 'vlm.creation'):
            clients[waited_on] = StandIn(clients[waited_on], standin)
    if 'vlm.front' in slots:   # the first voice on the Spark; vlm.studio writes whenever it is away
        from studio.providers.frontvoice import FrontFirst, WithFrontVoice
        front = build_client(slots['vlm.front'])
        clients['vlm.studio'] = WithFrontVoice(clients['vlm.studio'], front)
        # The teacher review, the scene description and the story outline too (operator): every
        # word written for the child or the teacher. The checks answer from their own slots: Qwen's
        # (judges, safety), the toy figure's look Step's.
        for writer in ('vlm.teacher', 'vlm.creation'):
            clients[writer] = FrontFirst(front, clients[writer])
    if SAFETY_READER_SLOT in slots:
        from studio.providers.safetyreader import WithSecondLook
        clients['safety.image'] = WithSecondLook(clients['safety.image'], build_safety_reader(slots[SAFETY_READER_SLOT]))
    mesh = MediaSlot(MeshChoices([slots['mesh.portrait']]), 'to_mesh', {}, {'scene_format': 'glb'})
    # The tts.studio slot decides where speech is bought, not just what it
    # sounds like. This used to be built with no configuration at
    # all, so the voice always used the module's default address — which was
    # invisible while there was only one address to use.
    speech = slots['tts.studio'].options
    voice = StepFunClassroomVoice(base_url=speech.get('base_url'),
                                  included_in_plan=bool(speech.get('included_in_plan')))
    video = lazy_slot(slots['video.animation'])
    # No DashScope key, no online clip: the Spark's own is then the class's, open whatever the profile says.
    # Closing it keeps our shared node's memory for a class; a copy of the project on someone else's box, a
    # judge's say, still makes its clips there with no second key (operator).
    online_key = os.environ.get(key_for(slots['video.online'].provider), '').strip() if 'video.online' in slots else ''
    if online_key:   # the teacher's quick choice, 5 s from Wan 3.0 online (operator)
        from dataclasses import replace
        from studio.providers.choices import ClipChoices, LazyMediaClient
        video = replace(video, client=ClipChoices(video.client, LazyMediaClient(slots['video.online']),
                                                  spark_open=not slots['video.animation'].options.get('closed_to_teachers')))
    return Runtime(name, name, clients, video, mesh, voice, deployed=True)


def build_stepfun():
    return build_runtime('stepfun')


def component_identity(config):
    # whispercpp is here because hearing became a profile slot and
    # the deployment that used it (Local First, now archived) ran it on the 4090. Without it the status
    # board called a service on the operator's own box an API, which is the same
    # error as printing the internal router name cloudmesh as though it were a
    # vendor. A whispercpp slot pointed at this Mac would need the label split by
    # port; no shipping deployment does that today. llamacpp and safetyreader joined later: Qwen and
    # NVIDIA's safety model run on the Spark, and the board had been calling them an API.
    local = config.provider in ('localimage', 'localmesh', 'localvideo', 'remotevoice', 'whispercpp',
                                'llamacpp', 'safetyreader')
    sources = {'trellis2': 'https://huggingface.co/microsoft/TRELLIS.2-4B',
               'pixal': 'https://huggingface.co/TencentARC/Pixal3D',
               'VoxCPM2': 'https://huggingface.co/openbmb/VoxCPM2',
               'wan2.2-ti2v-5b': 'https://huggingface.co/Wan-AI/Wan2.2-TI2V-5B',
               'wan2.2-i2v-a14b': 'https://huggingface.co/Wan-AI/Wan2.2-I2V-A14B-Diffusers'}
    box = LOCAL_BOX
    provider = (box if local else 'fal.ai' if config.provider == 'cloudmesh' and config.model == 'pixal'
                else 'Replicate' if config.provider in ('cloudmesh', 'replicate')
                else 'StepFun' if config.provider == 'stepfun'
                else 'DashScope' if config.provider == 'dashscopevideo' else config.provider)
    return {'provider': provider, 'location': box if local else 'API',
            'source': sources.get(config.model, '') if local else ''}


def model_options(profile, kind, report=None):
    slots = load_profile(profile)
    # Only the 3D choice is offered: the picture choice went with the still picture.
    if kind != 'mesh':
        raise ValueError('Unknown media kind')
    names = ('mesh.portrait', 'mesh.alternative')
    options = []
    for n in names:
        if n not in slots: continue
        c = slots[n]
        unavailable = is_disabled_stepfun_image_model(c.model)
        key = key_for(c.provider)
        if c.provider == 'cloudmesh' and c.model == 'pixal':
            missing = not (os.environ.get('FALAI_API_KEY') or os.environ.get('FAL_KEY'))
        else:
            missing = bool(key and not os.environ.get(key))
        label = c.options.get('label', {'trellis2': 'TRELLIS.2', 'pixal': 'Pixal3D'}.get(c.model, c.model))
        options.append(dict(id=c.options.get('choice', c.model), label=label,
                            model=c.model, default=n == names[0], status='unavailable' if unavailable or missing else 'unknown',
                            reason='retired' if unavailable else 'credentials' if missing else 'not_checked',
                            **component_identity(c)))
        component_slot = 'mesh.portrait.' + c.model
        if not unavailable and not missing and report and report.get('target') == profile:
            checked = next((item for item in report.get('components', [])
                            if item.get('slot') == component_slot and item.get('model') == c.model), None)
            if checked is not None:
                options[-1].update(status=checked['status'], reason=checked.get('reason', 'not_checked'))
    return options


CREDENTIALLED = ROLE_SLOTS + ('video.animation', 'mesh.portrait', 'tts.studio')


def missing_keys(profile):
    """The keys a profile's class needs that this machine lacks; .env.example says where each one comes from."""
    slots = load_profile(profile)
    required = {key_for(slots[n].provider) for n in CREDENTIALLED if n in slots} - {''}
    return sorted(key for key in required if not os.environ.get(key))


def describe(classroom):
    """List the deployments the studio offers: StepFun First alone.

    `available` says the credentials it needs are present. It is not a
    reachability claim: a deployment whose media runs on the GPU box needs no
    key at all, so it reports available while the box is switched off. Only
    `deployment_checks` probes a service, and applying a selection is gated on it.

    Until the archive each option also carried `identical_to`, naming another
    option it resolved to component for component; with one option there is
    nothing to be identical to, and it went with the other two.
    """
    options = []
    for name, label in DEPLOYMENTS.items():
        missing = missing_keys(name)
        options.append({'id': name, 'name': label, 'available': not missing, 'missing': missing})
    return {'selected': classroom.deployment, 'scope': 'new_sessions',
            'persistent': classroom.deployment_path is not None, 'options': options,
            'legacy': classroom.deployment == 'current'}


def save_selection(path, name):
    if name not in DEPLOYMENTS and name != 'current':
        raise unknown(name)
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix='.deployment-', dir=path.parent)
    try:
        with os.fdopen(fd, 'w') as file:
            json.dump({'deployment': name}, file)
        os.replace(temporary, path)
    finally:
        Path(temporary).unlink(missing_ok=True)


def restore_selection(classroom, path, override=None):
    classroom.deployment_path = Path(path)
    selected = override
    if selected is None and classroom.deployment_path.exists():
        selected = json.loads(classroom.deployment_path.read_text()).get('deployment')
        # A machine that last chose an archived deployment opens on the one that
        # is left, rather than refusing to start over a choice nobody can make now.
        if selected in ARCHIVED:
            selected = 'stepfun'
    if selected:
        classroom.switch_deployment(selected)
