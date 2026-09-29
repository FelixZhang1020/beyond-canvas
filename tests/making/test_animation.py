"""Clips are real media jobs: bounded inputs, no paid retries, no chat planner.

These ran against the FLUX still picture until it was retired; the guarantees
belong to the clip now, so the fake editor makes a real one-second H.264 clip.
"""
import functools
import io
import json
import subprocess
import tempfile
from pathlib import Path

import httpx
import pytest
from PIL import Image

from studio.making import animation
from studio.conversation.conversation import Conversation
from studio.core.errors import ModelUnavailable
from studio.core.ledger import Ledger
from studio.providers.media import MediaResult, MediaSlot
from tests.classroom.test_classroom import Scripted, ALLOW, DRAWING


@functools.cache
def a_clip() -> bytes:
    with tempfile.TemporaryDirectory() as folder:
        path = Path(folder) / 'clip.mp4'
        subprocess.run(['ffmpeg', '-v', 'error', '-f', 'lavfi', '-i', 'color=c=blue:s=64x64:r=24',
                        '-t', '1', '-c:v', 'libx264', '-pix_fmt', 'yuv420p', str(path)], check=True, timeout=20)
        return path.read_bytes()


class Editor:
    def __init__(self, content=None, error=None):
        self.content = a_clip() if content is None else content
        self.error, self.calls = error, []

    def make(self, inputs):
        self.calls.append(inputs)
        if self.error:
            raise self.error
        return MediaResult(urls=[], content=self.content, provider='fake', model='fake', price_usd=.002)

    def slot(self):
        return MediaSlot(self, 'to_video', {}, {})


# The clip check's answer when the clip added nothing to the painting.
CLEAN = '{"found": []}'
# Five decoded frames screened, then one look at them beside the original.
ONE_CLIP = [ALLOW] * 5 + [CLEAN]


def talk(tmp_path, editor, replies=None):
    studio = Scripted([])
    # One screen of the drawing, then each new clip's frames and its check.
    judge = Scripted(replies if replies is not None else [ALLOW, *ONE_CLIP, *ONE_CLIP])
    return Conversation(DRAWING, Ledger(tmp_path / 'ledger.jsonl'), entrance='colour',
                        studio=studio, director=judge, editor=editor.slot()), studio, judge


@pytest.mark.parametrize("creature", ["animal", "bird", "person", "dog", "raises its head"])
def test_a_clip_with_no_words_from_the_child_asks_only_for_what_is_already_painted(tmp_path, creature):
    """Every clip made without the child's words used to ask for "one foreground animal" to raise
    its head. Measured overnight: the painting of a house by a canal has no animal, and the
    clip came back with a hand holding a brush reaching in from the bottom of the frame."""
    editor = Editor()
    conversation, _studio, _judge = talk(tmp_path, editor)
    assert conversation.animate('', 'no words').ok
    assert creature not in editor.calls[0]['instruction'].lower()


def test_cache_and_changed_words_use_the_video_model_without_chat_planning(tmp_path):
    editor = Editor()
    conversation, studio, judge = talk(tmp_path, editor)
    first = conversation.animate('抬起一只手', 'first')
    assert first.ok and first.plan['kind'] == 'video'
    assert first.plan['video_url'].startswith('data:video/mp4;base64,')
    assert len(editor.calls) == 1 and len(judge.prompts) == 7
    assert '抬起一只手' in editor.calls[0]['instruction']
    assert editor.calls[0]['image'].startswith('data:image/png;base64,')
    cached = conversation.animate(' 抬起一只手 ', 'replay')
    assert cached.plan == first.plan
    assert len(editor.calls) == 1 and len(judge.prompts) == 7
    assert conversation.animate('轻轻点头', 'changed').ok
    assert len(editor.calls) == 2 and len(judge.prompts) == 13
    assert studio.prompts == []
    assert [e.cost_usd for e in conversation.ledger.entries() if e.stage == 'animation'] == [.002, 0, .002]
    ledger = (tmp_path / 'ledger.jsonl').read_text()
    assert 'base64' not in ledger and '抬起' not in ledger and '轻轻点头' not in ledger


def test_paid_request_error_never_resubmits_and_does_not_log_vendor_payload(tmp_path):
    editor = Editor(error=ModelUnavailable('secret signed URL and private child words'))
    conversation, _, _ = talk(tmp_path, editor)
    beat = conversation.animate('', 'outage')
    assert not beat.ok and beat.reason_code == 'model_unavailable'
    assert len(editor.calls) == 1
    assert 'secret' not in (tmp_path / 'ledger.jsonl').read_text()


@pytest.mark.parametrize('content', [b'not a movie', b''])
def test_invalid_output_is_refused_once_without_retry(tmp_path, content):
    editor = Editor(content=content)
    conversation, _, _ = talk(tmp_path, editor)
    assert not conversation.animate('', 'invalid').ok
    assert len(editor.calls) == 1


def test_refused_input_never_reaches_the_video_model(tmp_path):
    editor = Editor()
    blocked = '{"verdict":"block","reason":"private","text_found":[]}'
    conversation, _, _ = talk(tmp_path, editor, [blocked, blocked])
    assert not conversation.animate('', 'blocked').ok
    assert not conversation.animate('', 'blocked-again').ok
    assert not editor.calls


def test_generated_clip_is_screened_and_refusal_never_rerolls(tmp_path):
    editor = Editor()
    blocked = '{"verdict":"unsafe","reason":"private","text_found":[]}'
    conversation, _, _ = talk(tmp_path, editor, [ALLOW, blocked, blocked])
    beat = conversation.animate('', 'unsafe-output')
    assert not beat.ok and not beat.plan
    assert len(editor.calls) == 1 and conversation._animation is None


def test_image_size_is_bounded_and_metadata_is_removed():
    buffer = io.BytesIO()
    Image.new('RGB', (2000, 1000)).save(buffer, format='PNG')
    frame = animation.normalize(buffer.getvalue())
    assert (frame.width, frame.height) == (1280, 640)
    buffer = io.BytesIO()
    Image.new('RGB', (3000, 2000)).save(buffer, format='PNG')
    with pytest.raises(ValueError):
        animation.normalize(buffer.getvalue())


@pytest.mark.parametrize('url', ['http://127.0.0.1/x', 'https://example.com/x',
    'https://replicate.delivery.attacker.test/x', 'https://user:pass@replicate.delivery/x',
    'https://replicate.delivery:9000/x'])
def test_unexpected_output_urls_are_not_fetched(url):
    def reject(_):
        pytest.fail('untrusted URL must not be fetched')
    with httpx.Client(transport=httpx.MockTransport(reject)) as client:
        with pytest.raises(ValueError):
            animation.download(MediaResult(urls=[url]), client=client)


def test_delivery_download_has_no_credentials_and_rejects_redirect_and_oversize(monkeypatch):
    image = Path(DRAWING).read_bytes()
    def request(req):
        assert 'authorization' not in req.headers
        return httpx.Response(200, content=image)
    result = MediaResult(urls=['https://replicate.delivery/example/output.png'])
    with httpx.Client(transport=httpx.MockTransport(request)) as client:
        assert animation.download(result, client=client) == image
        monkeypatch.setattr(animation, 'MAX_DOWNLOAD', 1)
        with pytest.raises(ValueError):
            animation.download(result, client=client)
    with httpx.Client(transport=httpx.MockTransport(lambda _: httpx.Response(302, headers={'location':'http://localhost/x'}))) as client:
        with pytest.raises((ValueError, httpx.HTTPStatusError)):
            animation.download(result, client=client)


def test_prompt_quotes_and_bounds_unicode_instead_of_treating_it_as_instructions():
    editor = Editor()
    animation.generate('data:image/png;base64,x', '抬手🐈' * 250, editor.slot())
    quoted = editor.calls[0]['instruction'].split(animation.VIDEO_PROMPT)[1]
    assert json.loads(quoted) == ('抬手🐈' * 250)[:600]


def test_a_request_for_the_retired_still_picture_is_refused_without_a_model_call():
    """The FLUX still picture was retired. A picture editor handed to the
    animation step is refused, never quietly asked for a picture."""
    editor = Editor()
    with pytest.raises(ModelUnavailable):
        animation.generate('data:image/png;base64,x', 'hop', MediaSlot(editor, 'edit_image', {}, {}))
    assert editor.calls == []


def test_normalized_picture_drops_embedded_metadata():
    import base64
    source = io.BytesIO()
    im = Image.new('RGB', (10, 10))
    exif = Image.Exif()
    exif[270] = 'private image note'
    im.save(source, format='JPEG', exif=exif)
    frame = animation.normalize(source.getvalue())
    with Image.open(io.BytesIO(base64.b64decode(frame.image.split(',')[1]))) as restored:
        assert not restored.getexif()
        assert not restored.info


def test_the_ledger_names_a_clip_a_clip(tmp_path):
    """Seen once: a Wan clip's ledger line read "keyframe safety pass". The
    note was composed once for the still-image path and reused for both kinds;
    a judge reading the ledger could not tell which had been made.
    """
    editor = Editor()
    conversation, studio, judge = talk(tmp_path, editor)
    assert conversation.animate('抬起一只手', 'clip').ok
    notes = [e.note for e in conversation.ledger.entries() if e.stage == 'animation']
    assert notes and notes[-1].startswith('clip safety pass'), notes
    assert 'keyframe' not in notes[-1]


def test_a_clip_that_adds_hands_is_held_back_and_the_new_try_starts_elsewhere(tmp_path):
    """Seen once: two human hands holding brushes painted into the corgi's clip. The check
    holds such a clip back, and pressing again must not paint the same clip from the same start."""
    from studio.conversation.words import say
    editor = Editor()
    added = '{"found": ["hands", "tools"]}'
    conversation, _, _ = talk(tmp_path, editor, [ALLOW, *[ALLOW] * 5, added, *ONE_CLIP])
    held = conversation.animate('wag its tail', 'first')
    assert not held.ok and held.plan is None
    assert held.reason_code == 'clip_held_back' and held.refused == say('en', 'clip_held_back')
    notes = [e.note for e in conversation.ledger.entries() if e.stage == 'animation']
    assert notes[-1] == 'clip check fail: hands tools'
    assert 'seed' not in editor.calls[0], 'the first clip keeps the service start that was measured'
    again = conversation.animate('wag its tail', 'again')
    assert again.ok and len(editor.calls) == 2
    assert editor.calls[1]['seed'] == 43


def test_an_answer_written_after_the_reasoning_is_still_read(tmp_path):
    """Measured: the model often reasons in prose first and answers last."""
    editor = Editor()
    reasoned = 'Frames 2 to 4 show a human hand holding a brush at the right edge.\n\n{"found": ["hands", "tools"]}'
    conversation, _, _ = talk(tmp_path, editor, [ALLOW, *[ALLOW] * 5, reasoned])
    held = conversation.animate('', 'reasoned')
    assert held.reason_code == 'clip_held_back'


def test_the_check_can_only_answer_in_its_own_codes(tmp_path):
    """What the check finds becomes a ledger note, so anything outside its list is dropped unread."""
    editor = Editor()
    worded = '{"found": ["a girl called Mia holding a brush"]}'
    conversation, _, _ = talk(tmp_path, editor, [ALLOW, *[ALLOW] * 5, worded])
    assert conversation.animate('', 'worded').ok
    assert 'Mia' not in (tmp_path / 'ledger.jsonl').read_text()


def test_a_check_without_an_answer_lets_the_screened_clip_through_and_says_so(tmp_path):
    editor = Editor()
    conversation, _, _ = talk(tmp_path, editor, [ALLOW, *[ALLOW] * 5, 'not an answer'])
    assert conversation.animate('', 'unanswered').ok
    notes = [e.note for e in conversation.ledger.entries() if e.stage == 'animation']
    assert notes[-1].startswith('clip safety pass; clip check unavailable'), notes


def test_the_check_reads_one_sheet_with_the_original_first():
    import base64
    from studio.conversation.conversation import _load_skill
    from studio.core.images import to_data_uri
    check = _load_skill('clip_check_skill', 'skills/painting-to-animation/scripts/clip_check.py')
    frames = animation.normalize_video(a_clip()).screen_images
    sheet = check.sheet(to_data_uri(DRAWING), frames)
    assert sheet.startswith('data:image/jpeg;base64,')
    with Image.open(io.BytesIO(base64.b64decode(sheet.split(',', 1)[1]))) as board:
        assert board.size == (3 * check.PANEL, 2 * check.PANEL)


def test_the_clip_check_waits_for_a_slow_container_start(monkeypatch):
    """On the Spark every ffprobe and ffmpeg is a fresh container (deploy/spark/bin), 0.28 s on an idle node.
    On a busy night it passed the old 15 and 20 s limits: three clip tests failed "invalid generated media" that
    way, and a class clip checked then would have been thrown away after its eighteen minutes of making."""
    limits, real = [], subprocess.check_output

    def timed(command, **kwargs):
        limits.append(kwargs.get("timeout"))
        return real(command, **kwargs)

    monkeypatch.setattr(animation.subprocess, "check_output", timed)
    animation.normalize_video(a_clip())
    assert len(limits) == 6, "one look at the clip and five frames"
    assert min(limits) >= 120, "each tool gets as long as the online clip's conversion"
