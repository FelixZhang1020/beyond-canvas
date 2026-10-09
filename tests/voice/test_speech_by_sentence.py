"""Classroom speech is made sentence by sentence, so the first is heard in about 2 s.

Measured on the Spark: StepFun made one sentence in 1.8 s and 150
characters in 10-11 s, all of it silence while the page waited for one file.
"""
import base64
import io
import json
import wave

import httpx

from studio.providers.stepfun_voice import StepFunClassroomVoice, sentences


def wav(frames):
    out = io.BytesIO()
    with wave.open(out, 'wb') as f:
        f.setnchannels(1); f.setsampwidth(2); f.setframerate(24000); f.writeframes(frames)
    return out.getvalue()


def test_text_is_split_at_sentence_ends_and_nothing_is_lost():
    text = '我看见一只小熊。它戴着红帽子！你觉得它要去哪里？'
    assert sentences(text) == ['我看见一只小熊。', '它戴着红帽子！你觉得它要去哪里？']
    assert ''.join(sentences(text)) == text
    assert sentences('哇！') == ['哇！'], 'a short line is still spoken'
    assert sentences('No end mark at all') == ['No end mark at all']


def test_a_long_first_sentence_starts_speaking_at_its_first_comma():
    text = '我看见一只穿蓝衣服的小熊，站在白白的雪地上，头上戴着一顶红红的帽子。你觉得它要去哪里呢？'
    parts = sentences(text)
    assert parts[0] == '我看见一只穿蓝衣服的小熊，'
    assert ''.join(parts) == text


def mp3(tag):
    return b'ID3' + bytes([tag]) * 60


def test_each_sentence_is_its_own_request_and_plays_in_order():
    said, formats = [], []
    def handler(request):
        body = json.loads(request.content)
        said.append(body['input']); formats.append(body['response_format'])
        return httpx.Response(200, content=mp3(len(body['input']) % 250))
    voice = StepFunClassroomVoice('test', httpx.Client(transport=httpx.MockTransport(handler)))
    parts = sentences('第一句话说小熊。第二句话说帽子。第三句话问问题？')
    pieces = list(voice.stream('第一句话说小熊。第二句话说帽子。第三句话问问题？', 'gentle-female'))
    assert sorted(said) == sorted(parts)
    assert pieces == [mp3(len(p) % 250) for p in parts], 'one whole piece per sentence, in order'


def test_the_companion_speaks_a_little_faster_and_the_storybook_keeps_its_pace():
    """Operator: the voice was "too slow", then 2x, 1.5x and 1.2x "too fast", so 1.1x. Measured on the Spark, averaged:
    two sentences took 14.1 s at .95 with "a bit slower" in the instruction, 13.4 s at 1.0 without it."""
    asked = {}
    def handler(request):
        body = json.loads(request.content)
        asked[body['voice'], body['instruction'][:2]] = body['speed']
        return httpx.Response(200, content=mp3(9))
    voice = StepFunClassroomVoice('test', httpx.Client(transport=httpx.MockTransport(handler)))
    list(voice.stream('小熊去哪里？', 'gentle-female'))
    voice.clip('小熊去哪里？', 'soft-child')
    speeds = sorted(asked.values())
    assert speeds == [.95, 1.0], asked
    assert '慢一点' not in voice.instruction


def test_one_piece_is_made_whole_for_a_book_that_keeps_it():
    """Code review: a long sentence asked for through `stream` was split at its comma again, came back
    in two pieces and was never kept (studio/voice/book_voice.py)."""
    import pytest
    from studio.providers.stepfun_voice import VoiceServiceError
    said = []
    def handler(request):
        said.append(json.loads(request.content)['input'])
        return httpx.Response(200, content=mp3(7))
    voice = StepFunClassroomVoice('test', httpx.Client(transport=httpx.MockTransport(handler)))
    long = '小熊拿着一幅画走进教室，大家都围过来看他画的彩虹和太阳。'
    assert voice.clip(long, 'soft-child') == mp3(7) and said == [long]
    page = StepFunClassroomVoice('test', httpx.Client(transport=httpx.MockTransport(
        lambda request: httpx.Response(200, content=b'<html>busy</html>'))))
    with pytest.raises(VoiceServiceError):
        page.clip(long, 'soft-child')


def test_speech_is_sent_at_a_speech_bitrate_and_as_it_came_when_that_fails():
    """Operator ("go ahead"): StepFun's MP3 is 128 kbit/s, 105 KB for 6.5 s of speech, and at a slow
    moment on the link a press waited 32 s for its first sentence. At 48 kbit/s a sentence is 2.6 times smaller."""
    import shutil
    import subprocess
    import pytest
    if shutil.which('ffmpeg') is None:
        pytest.skip('ffmpeg makes the smaller MP3; the Spark has it')
    loud = subprocess.run(['ffmpeg', '-v', 'error', '-f', 'lavfi', '-i', 'sine=frequency=220:duration=4:sample_rate=24000',
                           '-ac', '1', '-b:a', '128k', '-f', 'mp3', 'pipe:1'], capture_output=True, check=True).stdout
    sent = []
    voice = StepFunClassroomVoice('test', httpx.Client(transport=httpx.MockTransport(
        lambda request: httpx.Response(200, content=sent[0] if sent else loud))))
    small = voice.clip('小熊拿着一幅画走进教室，大家都围过来看。', 'soft-child')
    assert small[:3] == b'ID3' or small[:2] >= b'\xff\xe0'
    assert len(small) < len(loud) / 2, f'{len(small)} bytes from {len(loud)}'
    rate = subprocess.run(['ffprobe', '-v', 'error', '-show_entries', 'stream=bit_rate', '-of', 'csv=p=0', 'pipe:0'],
                          input=small, capture_output=True, check=True).stdout.decode().strip()
    assert rate == '48000'
    sent.append(mp3(9))   # something ffmpeg cannot read goes to the page as it came, never as no sound at all
    assert voice.clip('小熊拿着一幅画走进教室。', 'soft-child') == mp3(9)


def test_a_node_that_cannot_start_ffmpeg_sends_the_voice_as_it_came(monkeypatch):
    """Code review: only a missing ffmpeg or a timeout fell back; a busy node's EAGAIN got through."""
    from studio.providers.stepfun_voice import smaller
    from studio.voice import audio_in

    def busy(*args, **kwargs):
        raise BlockingIOError(11, 'Resource temporarily unavailable')
    monkeypatch.setattr(audio_in.subprocess, 'run', busy)
    assert smaller(mp3(5), '48k') == mp3(5)
    # The child's voice keeps the failure as it is: made unreadable, one busy moment would pass for a recording the
    # Spark cannot copy and read that drawing's pages in the studio's voice for ten minutes (code review).
    import pytest
    with pytest.raises(BlockingIOError):
        audio_in.as_mp3(b'RIFF', '64k')


def test_classroom_speech_travels_as_mp3_because_raw_sound_outran_the_relay():
    """Raw sound needs 64 KB a second and the relay delivered 29, so the page played
    in bursts. MP3 is a quarter of that, and each sentence arrives whole before it plays."""
    formats = []
    def handler(request):
        formats.append(json.loads(request.content)['response_format'])
        return httpx.Response(200, content=mp3(1))
    voice = StepFunClassroomVoice('test', httpx.Client(transport=httpx.MockTransport(handler)))
    assert voice.compressed is True
    list(voice.stream('小熊要去河边钓鱼。', 'gentle-female'))
    assert formats == ['mp3']


def test_the_page_is_sent_mp3_events_and_a_cached_replay_sends_them_again():
    from studio.voice.speech import SpeechSession
    voice = StepFunClassroomVoice('test', httpx.Client(transport=httpx.MockTransport(
        lambda request: httpx.Response(200, content=mp3(7)))))
    speech = SpeechSession()
    for _ in range(2):
        events = list(speech.stream(voice, '小熊要去河边钓鱼。', 'gentle-female'))
        assert [e['type'] for e in events] == ['format', 'mp3', 'done']
        assert base64.b64decode(events[1]['data']) == mp3(7)


def test_something_that_is_not_mp3_is_refused_rather_than_played_as_noise():
    import pytest
    from studio.providers.stepfun_voice import VoiceServiceError
    voice = StepFunClassroomVoice('test', httpx.Client(transport=httpx.MockTransport(
        lambda request: httpx.Response(200, content=wav(b'\0\0' * 100)))))
    with pytest.raises(VoiceServiceError):
        list(voice.stream('小熊要去河边钓鱼。', 'gentle-female'))
